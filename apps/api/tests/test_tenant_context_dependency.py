from __future__ import annotations

import json
from io import StringIO
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from aria_observability import create_event_logger, current_trace_context
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.tenant_context import require_tenant_context
from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.membership_resolution import ActiveMembershipRequired
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext, TenantContextResolver


class StubTokenVerifier:
    provider_name = "test-provider"

    def __init__(self, *, token: str, subject: UUID) -> None:
        self._token = token
        self._subject = subject

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != self._token:
            raise InvalidAccessToken(reason_code="invalid_signature")
        return AuthenticatedIdentity(subject=self._subject)


class StubTenantContextResolver(TenantContextResolver):
    def __init__(
        self,
        context: TenantContext | None = None,
        *,
        error: ActiveMembershipRequired | None = None,
    ) -> None:
        self.context = context
        self.error = error
        self.calls: list[tuple[AuthenticatedIdentity, UUID]] = []
        self.trace_accounts_at_call: list[str | None] = []

    async def execute(
        self,
        identity: AuthenticatedIdentity,
        account_id: UUID,
    ) -> TenantContext:
        self.calls.append((identity, account_id))
        trace = current_trace_context()
        self.trace_accounts_at_call.append(trace.account_id if trace is not None else None)
        if self.error is not None:
            raise self.error
        if self.context is None:
            raise RuntimeError("missing tenant context fixture")
        return self.context


def _tenant_context(subject: UUID, account_id: UUID) -> TenantContext:
    return TenantContext(
        subject_id=subject,
        account_id=account_id,
        membership_id=uuid4(),
        role="admin",
        membership_status="active",
    )


def _app(
    *,
    stream: StringIO,
    token: str,
    subject: UUID,
    resolver: StubTenantContextResolver,
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
        access_token_verifier=StubTokenVerifier(token=token, subject=subject),
        tenant_context_resolver=resolver,
    )

    @app.get("/test/tenant")
    async def tenant_route(
        context: Annotated[TenantContext, Depends(require_tenant_context)],
    ) -> dict[str, str]:
        return {
            "account_id": str(context.account_id),
            "role": context.role,
            "membership_status": context.membership_status,
        }

    return app


def _events(stream: StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.parametrize(
    ("header_value", "reason_code"),
    [(None, "missing"), ("", "empty"), ("not-a-uuid", "invalid_uuid")],
)
def test_missing_empty_or_invalid_account_header_returns_stable_400(
    header_value: str | None,
    reason_code: str,
) -> None:
    stream = StringIO()
    token = "tenant-header-token"
    subject = uuid4()
    resolver = StubTenantContextResolver()
    headers = {"Authorization": f"Bearer {token}"}
    if header_value is not None:
        headers["X-Account-ID"] = header_value
    response = TestClient(
        _app(
            stream=stream,
            token=token,
            subject=subject,
            resolver=resolver,
        )
    ).get("/test/tenant", headers=headers)

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "ACCOUNT_CONTEXT_REQUIRED",
        "message": "A valid account context is required.",
        "retryable": False,
    }
    assert resolver.calls == []
    rejected = next(
        event for event in _events(stream) if event["event_name"] == "tenant.context_rejected"
    )
    assert rejected["reason_code"] == reason_code
    assert rejected["error_code"] == "ACCOUNT_CONTEXT_REQUIRED"
    assert rejected["account_id"] is None
    assert next(
        event for event in _events(stream) if event["event_name"] == "http.request_completed"
    )["account_id"] is None
    assert token not in stream.getvalue()
    if header_value:
        assert header_value not in stream.getvalue()


@pytest.mark.parametrize("reason_code", ["not_found", "invited", "suspended"])
def test_membership_denials_share_one_non_enumerating_403(reason_code: str) -> None:
    stream = StringIO()
    token = "tenant-denial-token"
    subject = uuid4()
    account_id = uuid4()
    resolver = StubTenantContextResolver(
        error=ActiveMembershipRequired(reason_code=reason_code)
    )
    response = TestClient(
        _app(
            stream=stream,
            token=token,
            subject=subject,
            resolver=resolver,
        )
    ).get(
        "/test/tenant",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(account_id),
        },
    )

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "MEMBERSHIP_REQUIRED",
        "message": "An active account membership is required.",
        "retryable": False,
    }
    denied = next(
        event for event in _events(stream) if event["event_name"] == "tenant.membership_denied"
    )
    assert denied["reason_code"] == reason_code
    assert denied["error_code"] == "MEMBERSHIP_REQUIRED"
    assert denied["account_id"] is None
    assert str(account_id) not in stream.getvalue()


def test_active_membership_enriches_trace_only_after_authorization() -> None:
    stream = StringIO()
    token = "tenant-success-token"
    subject = uuid4()
    account_id = uuid4()
    resolver = StubTenantContextResolver(_tenant_context(subject, account_id))
    response = TestClient(
        _app(
            stream=stream,
            token=token,
            subject=subject,
            resolver=resolver,
        )
    ).get(
        "/test/tenant",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(account_id),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "account_id": str(account_id),
        "role": "admin",
        "membership_status": "active",
    }
    assert resolver.calls == [(AuthenticatedIdentity(subject=subject), account_id)]
    assert resolver.trace_accounts_at_call == [None]
    completed = next(
        event for event in _events(stream) if event["event_name"] == "http.request_completed"
    )
    assert completed["account_id"] == str(account_id)
    assert "tenant.context_rejected" not in {
        event["event_name"] for event in _events(stream)
    }
    assert "tenant.membership_denied" not in {
        event["event_name"] for event in _events(stream)
    }


@pytest.mark.parametrize("reason_code", ["invited", "suspended"])
def test_selected_inactive_membership_is_decided_without_bootstrap(
    reason_code: str,
) -> None:
    stream = StringIO()
    token = "inactive-selection-token"
    subject = uuid4()
    account_id = uuid4()
    response = TestClient(
        _app(
            stream=stream,
            token=token,
            subject=subject,
            resolver=StubTenantContextResolver(
                error=ActiveMembershipRequired(reason_code=reason_code)
            ),
        )
    ).get(
        "/test/tenant",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(account_id),
        },
    )

    assert response.status_code == 403
    events = _events(stream)
    assert not any(str(event["event_name"]).startswith("account.bootstrap_") for event in events)
    denied = next(
        event for event in events if event["event_name"] == "tenant.membership_denied"
    )
    assert denied["reason_code"] == reason_code
    assert denied["account_id"] is None
