from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.context.application.text_context_ingestion import (
    CreateTextContextCommand,
    TextContextAccepted,
    TextContextIdempotencyConflict,
    TextContextNotFound,
    TextContextPermissionDenied,
)
from app.modules.context.domain.context_source import ContextSourceValidationError
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


class StubTextContextUseCase:
    def __init__(self) -> None:
        self.command: CreateTextContextCommand | None = None
        self.error: Exception | None = None
        self.accepted = TextContextAccepted(
            source_id=uuid4(),
            status="uploaded",
            job_id=uuid4(),
        )

    async def execute(
        self, context: TenantContext, command: CreateTextContextCommand
    ) -> TextContextAccepted:
        del context
        self.command = command
        if self.error is not None:
            raise self.error
        return self.accepted


def _fixture() -> tuple[TestClient, StubTextContextUseCase, TenantContext, str]:
    token = "context-api-token"
    subject_id, account_id = uuid4(), uuid4()
    context = TenantContext(
        subject_id=subject_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )
    use_case = StubTextContextUseCase()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(token, subject_id),
        tenant_context_resolver=StubTenantContextResolver(context),
        text_context_use_case=use_case,  # type: ignore[arg-type]
    )
    return TestClient(app), use_case, context, token


def _headers(
    context: TenantContext,
    token: str,
    *,
    key: str | None = "context-key",
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Account-ID": str(context.account_id),
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_text_context_accepts_exact_body_and_returns_standard_202_envelope() -> None:
    client, use_case, context, token = _fixture()
    project_id = uuid4()
    response = client.post(
        f"/api/v1/projects/{project_id}/context-sources",
        headers=_headers(context, token),
        json={"source_type": "text", "raw_text": "  متن فارسی\n"},
    )

    assert response.status_code == 202
    assert response.json()["data"] == {
        "source_id": str(use_case.accepted.source_id),
        "status": "uploaded",
        "job_id": str(use_case.accepted.job_id),
    }
    UUID(response.json()["meta"]["request_id"])
    assert use_case.command is not None
    assert use_case.command.project_id == project_id
    assert use_case.command.raw_text == "  متن فارسی\n"
    assert use_case.command.idempotency_key == "context-key"


def test_text_context_requires_auth_tenant_key_and_exact_text_body() -> None:
    client, _, context, token = _fixture()
    path = f"/api/v1/projects/{uuid4()}/context-sources"
    body = {"source_type": "text", "raw_text": "text"}

    assert client.post(path, json=body).status_code == 401
    assert (
        client.post(
            path,
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        ).json()["error"]["code"]
        == "ACCOUNT_CONTEXT_REQUIRED"
    )
    missing_key_response = client.post(
        path,
        headers=_headers(context, token, key=None),
        json=body,
    )
    assert missing_key_response.status_code == 422
    assert (
        client.post(
            path,
            headers=_headers(context, token),
            json={"source_type": "file", "raw_text": "text"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            headers=_headers(context, token),
            json={"source_type": "text", "raw_text": "text", "metadata": {}},
        ).status_code
        == 422
    )


def test_text_context_maps_validation_conflict_and_safe_not_found() -> None:
    client, use_case, context, token = _fixture()
    path = f"/api/v1/projects/{uuid4()}/context-sources"
    headers = _headers(context, token)
    body = {"source_type": "text", "raw_text": "text"}

    for error, status_code, code in (
        (ContextSourceValidationError(), 422, "VALIDATION_FAILED"),
        (TextContextIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (TextContextNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (TextContextPermissionDenied(), 403, "MEMBERSHIP_REQUIRED"),
    ):
        use_case.error = error
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == status_code
        assert response.json()["error"]["code"] == code
        assert response.json()["error"]["retryable"] is False
