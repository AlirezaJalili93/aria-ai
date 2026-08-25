from __future__ import annotations

import json
from io import StringIO
from uuid import UUID, uuid4

from aria_observability import create_event_logger
from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.account_bootstrap import (
    AccountBootstrapContext,
    AccountBootstrapper,
)
from app.modules.identity.application.bootstrap_ports import ResolvedMembership
from app.modules.identity.application.membership_resolution import ActiveMembershipRequired
from app.modules.identity.application.ports import (
    AuthenticatedIdentity,
    AuthProviderUnavailable,
    InvalidAccessToken,
)


class StubVerifier:
    provider_name = "test-provider"

    def __init__(self, token: str, subject: UUID, *, unavailable: bool = False) -> None:
        self._token = token
        self._subject = subject
        self._unavailable = unavailable

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if self._unavailable:
            raise AuthProviderUnavailable(reason_code="jwks_fetch_failed")
        if token != self._token:
            raise InvalidAccessToken(reason_code="invalid_signature")
        return AuthenticatedIdentity(subject=self._subject)


class StubBootstrapper(AccountBootstrapper):
    def __init__(
        self,
        context: AccountBootstrapContext,
        *,
        fail: bool = False,
        inactive: bool = False,
    ) -> None:
        self._context = context
        self._fail = fail
        self._inactive = inactive
        self.calls = 0

    async def execute(self, identity: AuthenticatedIdentity) -> AccountBootstrapContext:
        self.calls += 1
        if self._fail:
            raise RuntimeError("sensitive database detail")
        if self._inactive:
            raise ActiveMembershipRequired(reason_code="suspended")
        assert identity.subject == self._context.subject
        return self._context


def _context(subject: UUID, *, created: bool) -> AccountBootstrapContext:
    return AccountBootstrapContext(
        subject=subject,
        active_memberships=(
            ResolvedMembership(
                membership_id=uuid4(),
                account_id=uuid4(),
                user_id=subject,
                role="owner",
                status="active",
            ),
        ),
        created=created,
    )


def _client(
    *,
    verifier: StubVerifier,
    bootstrapper: StubBootstrapper,
    stream: StringIO | None = None,
) -> TestClient:
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream or StringIO(),
    )
    return TestClient(
        create_app(
            ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
            event_logger=logger,
            access_token_verifier=verifier,
            account_bootstrapper=bootstrapper,
        ),
        raise_server_exceptions=False,
    )


def test_authenticated_bootstrap_command_returns_empty_204_without_tenant_header() -> None:
    subject = uuid4()
    token = "secret-access-token"
    bootstrapper = StubBootstrapper(_context(subject, created=True))
    response = _client(
        verifier=StubVerifier(token, subject), bootstrapper=bootstrapper
    ).post("/api/v1/auth/bootstrap", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert response.content == b""
    assert bootstrapper.calls == 1


def test_repeated_existing_bootstrap_is_idempotent_and_never_conflicts() -> None:
    subject = uuid4()
    token = "repeat-access-token"
    bootstrapper = StubBootstrapper(_context(subject, created=False))
    client = _client(verifier=StubVerifier(token, subject), bootstrapper=bootstrapper)

    responses = [
        client.post("/api/v1/auth/bootstrap", headers={"Authorization": f"Bearer {token}"})
        for _ in range(2)
    ]

    assert [response.status_code for response in responses] == [204, 204]
    assert all(response.content == b"" for response in responses)
    assert bootstrapper.calls == 2


def test_existing_identity_without_active_membership_remains_a_204_command() -> None:
    subject = uuid4()
    token = "inactive-membership-token"
    bootstrapper = StubBootstrapper(_context(subject, created=False), inactive=True)

    response = _client(
        verifier=StubVerifier(token, subject), bootstrapper=bootstrapper
    ).post("/api/v1/auth/bootstrap", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    assert response.content == b""
    assert bootstrapper.calls == 1


def test_bootstrap_command_requires_a_valid_bearer_token() -> None:
    subject = uuid4()
    bootstrapper = StubBootstrapper(_context(subject, created=False))
    client = _client(
        verifier=StubVerifier("valid-token", subject), bootstrapper=bootstrapper
    )

    missing = client.post("/api/v1/auth/bootstrap")
    invalid = client.post(
        "/api/v1/auth/bootstrap", headers={"Authorization": "Bearer invalid-token"}
    )

    for response in (missing, invalid):
        assert response.status_code == 401
        assert response.json()["error"] == {
            "code": "AUTH_REQUIRED",
            "message": "Authentication is required.",
            "retryable": False,
        }
    assert bootstrapper.calls == 0


def test_provider_unavailability_remains_a_retryable_503() -> None:
    subject = uuid4()
    bootstrapper = StubBootstrapper(_context(subject, created=False))
    response = _client(
        verifier=StubVerifier("token", subject, unavailable=True),
        bootstrapper=bootstrapper,
    ).post("/api/v1/auth/bootstrap", headers={"Authorization": "Bearer token"})

    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "AUTH_PROVIDER_UNAVAILABLE",
        "message": "Authentication provider is temporarily unavailable.",
        "retryable": True,
    }


def test_bootstrap_failure_has_a_stable_retryable_envelope_and_safe_log() -> None:
    stream = StringIO()
    subject = uuid4()
    token = "never-log-this-token"
    bootstrapper = StubBootstrapper(_context(subject, created=False), fail=True)
    response = _client(
        verifier=StubVerifier(token, subject),
        bootstrapper=bootstrapper,
        stream=stream,
    ).post("/api/v1/auth/bootstrap", headers={"Authorization": f"Bearer {token}"})

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
    for secret in (token, str(subject), "sensitive database detail", "email", "profile_data"):
        assert secret not in stream.getvalue().lower()


def test_bootstrap_command_is_post_only() -> None:
    subject = uuid4()
    token = "post-only-token"
    bootstrapper = StubBootstrapper(_context(subject, created=False))
    response = _client(
        verifier=StubVerifier(token, subject), bootstrapper=bootstrapper
    ).get("/api/v1/auth/bootstrap", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 405
    assert bootstrapper.calls == 0
