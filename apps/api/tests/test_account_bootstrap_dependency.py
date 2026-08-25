from __future__ import annotations

import json
from io import StringIO
from typing import Annotated
from uuid import UUID, uuid4

from aria_observability import create_event_logger
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.account_bootstrap import require_bootstrapped_identity
from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapContext,
    AccountBootstrapper,
    ActiveMembershipRequired,
)
from app.modules.identity.application.bootstrap_ports import ResolvedMembership
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken


class StubTokenVerifier:
    provider_name = "test-provider"

    def __init__(self, *, token: str, subject: UUID) -> None:
        self._token = token
        self._subject = subject

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != self._token:
            raise InvalidAccessToken(reason_code="invalid_signature")
        return AuthenticatedIdentity(subject=self._subject)


class StubBootstrapper(AccountBootstrapper):
    def __init__(
        self,
        context: AccountBootstrapContext | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.context = context
        self.error = error
        self.identities: list[AuthenticatedIdentity] = []

    async def execute(self, identity: AuthenticatedIdentity) -> AccountBootstrapContext:
        self.identities.append(identity)
        if self.error is not None:
            raise self.error
        if self.context is None:
            raise RuntimeError("safe injected failure")
        return self.context


def _bootstrap_app(
    *,
    stream: StringIO,
    verifier: StubTokenVerifier,
    bootstrapper: StubBootstrapper,
) -> FastAPI:
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        event_logger=logger,
        access_token_verifier=verifier,
        account_bootstrapper=bootstrapper,
    )

    @app.get("/test/bootstrapped")
    async def bootstrapped(
        context: Annotated[AccountBootstrapContext, Depends(require_bootstrapped_identity)],
    ) -> dict[str, bool]:
        return {"created": context.created}

    return app


def _context(*, subject: UUID, account_id: UUID, created: bool) -> AccountBootstrapContext:
    return AccountBootstrapContext(
        subject=subject,
        active_memberships=(
            ResolvedMembership(
                membership_id=uuid4(),
                account_id=account_id,
                user_id=subject,
                role="owner",
                status="active",
            ),
        ),
        created=created,
    )


def test_valid_jwt_runs_implicit_bootstrap_and_emits_safe_completed_event() -> None:
    stream = StringIO()
    subject = uuid4()
    account_id = uuid4()
    token = "sensitive-bootstrap-jwt"
    profile_data = "sensitive-profile-data"
    bootstrapper = StubBootstrapper(_context(subject=subject, account_id=account_id, created=True))
    client = TestClient(
        _bootstrap_app(
            stream=stream,
            verifier=StubTokenVerifier(token=token, subject=subject),
            bootstrapper=bootstrapper,
        )
    )

    response = client.get(
        "/test/bootstrapped",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"created": True}
    assert bootstrapper.identities == [AuthenticatedIdentity(subject=subject)]
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [event["event_name"] for event in events] == [
        "auth.verification_succeeded",
        "account.bootstrap_started",
        "account.bootstrap_completed",
        "http.request_completed",
    ]
    completed = events[2]
    assert completed["account_id"] is None
    request_completed = events[3]
    assert completed["request_id"] == request_completed["request_id"]
    assert completed["correlation_id"] == request_completed["correlation_id"]
    assert completed["duration_ms"] >= 0
    for forbidden in (token, str(subject), profile_data, "email"):
        assert forbidden not in stream.getvalue().lower()


def test_existing_bootstrap_emits_resolved_without_mutation_event() -> None:
    stream = StringIO()
    subject = uuid4()
    account_id = uuid4()
    token = "existing-user-token"
    bootstrapper = StubBootstrapper(_context(subject=subject, account_id=account_id, created=False))
    response = TestClient(
        _bootstrap_app(
            stream=stream,
            verifier=StubTokenVerifier(token=token, subject=subject),
            bootstrapper=bootstrapper,
        )
    ).get("/test/bootstrapped", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    resolved = next(
        event for event in events if event["event_name"] == "account.bootstrap_resolved"
    )
    request_completed = next(
        event for event in events if event["event_name"] == "http.request_completed"
    )
    assert resolved["request_id"] == request_completed["request_id"]
    assert resolved["correlation_id"] == request_completed["correlation_id"]
    assert resolved["duration_ms"] >= 0
    assert "account.bootstrap_completed" not in [event["event_name"] for event in events]


def test_bootstrap_failure_emits_safe_failed_event() -> None:
    stream = StringIO()
    subject = uuid4()
    token = "failed-bootstrap-token"
    bootstrapper = StubBootstrapper()
    client = TestClient(
        _bootstrap_app(
            stream=stream,
            verifier=StubTokenVerifier(token=token, subject=subject),
            bootstrapper=bootstrapper,
        ),
        raise_server_exceptions=False,
    )

    response = client.get(
        "/test/bootstrapped",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "ACCOUNT_BOOTSTRAP_FAILED",
        "message": "Account bootstrap is temporarily unavailable.",
        "retryable": True,
    }
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    failed = next(event for event in events if event["event_name"] == "account.bootstrap_failed")
    assert failed["error_code"] == "ACCOUNT_BOOTSTRAP_FAILED"
    assert failed["request_id"]
    assert failed["correlation_id"]
    assert failed["duration_ms"] >= 0
    for forbidden in (token, str(subject), "safe injected failure", "profile_data", "email"):
        assert forbidden not in stream.getvalue().lower()


def test_suspended_membership_maps_to_standardized_403_without_deletion_semantics() -> None:
    stream = StringIO()
    subject = uuid4()
    token = "suspended-membership-token"
    bootstrapper = StubBootstrapper(
        error=ActiveMembershipRequired(reason_code="suspended")
    )
    response = TestClient(
        _bootstrap_app(
            stream=stream,
            verifier=StubTokenVerifier(token=token, subject=subject),
            bootstrapper=bootstrapper,
        )
    ).get("/test/bootstrapped", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "MEMBERSHIP_REQUIRED",
        "message": "An active account membership is required.",
        "retryable": False,
    }
    failed = next(
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if json.loads(line)["event_name"] == "account.bootstrap_failed"
    )
    assert failed["reason_code"] == "active_membership_required"
    assert token not in stream.getvalue()
    assert str(subject) not in stream.getvalue()
