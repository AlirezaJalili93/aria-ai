from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.context.application.context_structuring_job_ports import (
    ContextStructuringActiveJobConflict,
)
from app.modules.context.application.context_structuring_jobs import (
    ContextStructuringAccepted,
    ContextStructuringIdempotencyConflict,
    ContextStructuringPermissionDenied,
    ContextStructuringProjectNotFound,
    ContextStructuringReadySourceRequired,
    ContextStructuringSyntheticFixtureRequired,
    ScheduleContextStructuringCommand,
)
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext


class StubTokenVerifier:
    provider_name = "test-provider"

    def __init__(self, token: str, subject: UUID) -> None:
        self._token = token
        self._subject = subject

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != self._token:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=self._subject)


class StubTenantContextResolver:
    def __init__(self, context: TenantContext) -> None:
        self._context = context

    async def execute(
        self, identity: AuthenticatedIdentity, account_id: UUID
    ) -> TenantContext:
        assert identity.subject == self._context.subject_id
        assert account_id == self._context.account_id
        return self._context


class StubContextStructuringUseCase:
    def __init__(self) -> None:
        self.commands: list[ScheduleContextStructuringCommand] = []
        self.error: Exception | None = None
        job_id = uuid4()
        self.accepted = ContextStructuringAccepted(
            job_id=job_id,
            status_url=f"/api/v1/jobs/{job_id}",
        )

    async def execute(
        self,
        context: TenantContext,
        command: ScheduleContextStructuringCommand,
    ) -> ContextStructuringAccepted:
        del context
        self.commands.append(command)
        if not command.idempotency_key.strip():
            raise ValueError
        if self.error is not None:
            raise self.error
        return self.accepted


def _fixture(
    *,
    enabled: bool = True,
    role: str = "member",
    membership_status: str = "active",
) -> tuple[TestClient, StubContextStructuringUseCase, TenantContext, str]:
    token = "context-structuring-token"
    context = TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role=role,  # type: ignore[arg-type]
        membership_status=membership_status,  # type: ignore[arg-type]
    )
    use_case = StubContextStructuringUseCase()
    app = create_app(
        ApiSettings(
            app_env="test",
            app_version="0.1.0",
            log_level="INFO",
            context_structuring_enabled=enabled,
        ),
        access_token_verifier=StubTokenVerifier(token, context.subject_id),
        tenant_context_resolver=StubTenantContextResolver(context),
        context_structuring_use_case=use_case,  # type: ignore[arg-type]
    )
    return TestClient(app), use_case, context, token


def _headers(context: TenantContext, token: str, *, key: str = "structure-key") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Account-ID": str(context.account_id),
        "Idempotency-Key": key,
    }


@pytest.mark.parametrize("role", ("owner", "admin", "member"))
def test_context_structuring_accepts_exact_empty_command_for_every_active_role(role: str) -> None:
    client, use_case, context, token = _fixture(role=role)
    project_id = uuid4()

    response = client.post(
        f"/api/v1/projects/{project_id}/context-structuring",
        headers=_headers(context, token),
    )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": str(use_case.accepted.job_id),
        "status_url": use_case.accepted.status_url,
    }
    assert use_case.commands[0].project_id == project_id
    assert use_case.commands[0].idempotency_key == "structure-key"


@pytest.mark.parametrize(
    ("content", "content_type"),
    ((b"{}", "application/json"), (b"null", "application/json"), (b"x", "text/plain")),
)
def test_context_structuring_rejects_every_non_empty_body(
    content: bytes, content_type: str
) -> None:
    client, use_case, context, token = _fixture()
    response = client.post(
        f"/api/v1/projects/{uuid4()}/context-structuring",
        headers={**_headers(context, token), "Content-Type": content_type},
        content=content,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert use_case.commands == []


def test_context_structuring_requires_idempotency_key_and_rejects_empty_key() -> None:
    client, _, context, token = _fixture()
    headers = _headers(context, token)
    headers.pop("Idempotency-Key")
    missing = client.post(
        f"/api/v1/projects/{uuid4()}/context-structuring",
        headers=headers,
    )
    empty = client.post(
        f"/api/v1/projects/{uuid4()}/context-structuring",
        headers=_headers(context, token, key=""),
    )
    assert missing.status_code == 422
    assert empty.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_FAILED"
    assert empty.json()["error"]["code"] == "VALIDATION_FAILED"


def test_context_structuring_feature_is_fail_closed_before_scheduling() -> None:
    client, use_case, context, token = _fixture(enabled=False)
    response = client.post(
        f"/api/v1/projects/{uuid4()}/context-structuring",
        headers=_headers(context, token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FEATURE_NOT_ENABLED"
    assert use_case.commands == []


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    (
        (ContextStructuringProjectNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ContextStructuringIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (ContextStructuringActiveJobConflict(), 409, "CONTEXT_STRUCTURING_IN_PROGRESS"),
        (ContextStructuringReadySourceRequired(), 422, "CONTEXT_READY_SOURCE_REQUIRED"),
        (ContextStructuringPermissionDenied(), 403, "MEMBERSHIP_REQUIRED"),
        (ContextStructuringSyntheticFixtureRequired(), 403, "FEATURE_NOT_ENABLED"),
    ),
)
def test_context_structuring_maps_frozen_error_contract(
    error: Exception, status_code: int, code: str
) -> None:
    client, use_case, context, token = _fixture()
    use_case.error = error
    response = client.post(
        f"/api/v1/projects/{uuid4()}/context-structuring",
        headers=_headers(context, token),
    )
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is False


def test_context_structuring_keeps_existing_auth_and_tenant_contracts() -> None:
    client, _, context, token = _fixture()
    path = f"/api/v1/projects/{uuid4()}/context-structuring"
    unauthorized = client.post(path, headers={"X-Account-ID": str(context.account_id)})
    missing_account = client.post(
        path,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "key"},
    )
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "AUTH_REQUIRED"
    assert missing_account.status_code == 400
    assert missing_account.json()["error"]["code"] == "ACCOUNT_CONTEXT_REQUIRED"


def test_hosted_context_structuring_enablement_is_rejected() -> None:
    hosted = {
        "app_version": "0.1.0",
        "log_level": "INFO",
        "public_app_url": "https://app.example.test",
        "api_base_url": "https://api.example.test",
        "database_url": "postgresql://staging.example.test/aria",
        "queue_broker_url": "rediss://:pass@queue.example.test:6379/0",
        "storage_endpoint": "https://storage.example.test",
        "storage_region": "eu-central-1",
        "storage_bucket": "private",
        "storage_access_key": "access",
        "storage_secret_key": "secret",
        "auth_provider_url": "https://auth.example.test",
        "auth_jwks_url": "https://auth.example.test/.well-known/jwks.json",
        "auth_audience": "authenticated",
        "release_commit_sha": "a" * 40,
        "context_structuring_enabled": True,
    }
    with pytest.raises(ValueError, match="cannot be enabled in a hosted environment"):
        ApiSettings(app_env="staging", **hosted)  # type: ignore[arg-type]
