from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.context.application.file_context_ingestion import (
    CreateFileContextCommand,
    FileContextAccepted,
    FileContextIdempotencyConflict,
    FileContextNotFound,
    FileContextPermissionDenied,
    FileContextStorageFailure,
)
from app.modules.context.domain.file_upload import (
    FileTooLargeError,
    FileUploadValidationError,
    UnsupportedFileTypeError,
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


class StubFileContextUseCase:
    def __init__(self) -> None:
        self.command: CreateFileContextCommand | None = None
        self.error: Exception | None = None
        self.accepted = FileContextAccepted(
            source_id=uuid4(),
            status="uploaded",
            job_id=uuid4(),
        )

    async def execute(
        self, context: TenantContext, command: CreateFileContextCommand
    ) -> FileContextAccepted:
        del context
        self.command = command
        if self.error is not None:
            raise self.error
        return self.accepted


def _fixture(*, enabled: bool = True):
    token = "file-context-token"
    subject_id, account_id = uuid4(), uuid4()
    context = TenantContext(
        subject_id=subject_id,
        account_id=account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )
    use_case = StubFileContextUseCase()
    settings = ApiSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        txt_upload_enabled=enabled,
        storage_endpoint="https://project.storage.supabase.co/storage/v1/s3",
        storage_region="eu-central-1",
        storage_bucket="private-context",
        storage_access_key="test-access",
        storage_secret_key="test-secret",
    )
    app = create_app(
        settings,
        access_token_verifier=StubTokenVerifier(token, subject_id),
        tenant_context_resolver=StubTenantContextResolver(context),
        file_context_use_case=use_case,  # type: ignore[arg-type]
    )
    return TestClient(app), use_case, context, token


def _headers(context: TenantContext, token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Account-ID": str(context.account_id),
        "Idempotency-Key": "upload-key",
    }


def _post(
    client: TestClient,
    context: TenantContext,
    token: str,
    *,
    source_type: str = "file",
    filename: str = "brief.txt",
    content: bytes = "متن فارسی".encode(),
    mime_type: str = "text/plain",
    extra: bool = False,
):
    data = {"source_type": source_type}
    if extra:
        data["metadata"] = "forbidden"
    return client.post(
        f"/api/v1/projects/{uuid4()}/context-sources",
        headers=_headers(context, token),
        data=data,
        files={"file": (filename, content, mime_type)},
    )


def test_file_context_accepts_exact_multipart_and_response_never_exposes_storage() -> None:
    client, use_case, context, token = _fixture()
    project_id = uuid4()
    response = client.post(
        f"/api/v1/projects/{project_id}/context-sources",
        headers=_headers(context, token),
        data={"source_type": "file"},
        files={"file": ("brief.txt", "متن فارسی".encode(), "text/plain")},
    )
    assert response.status_code == 202
    assert response.json()["data"] == {
        "source_id": str(use_case.accepted.source_id),
        "status": "uploaded",
        "job_id": str(use_case.accepted.job_id),
        "status_url": f"/api/v1/jobs/{use_case.accepted.job_id}",
    }
    serialized = response.text.lower()
    for forbidden in ("storage_ref", "object_key", "public_url", "signed_url", "filename"):
        assert forbidden not in serialized
    assert use_case.command is not None
    assert use_case.command.project_id == project_id
    assert use_case.command.filename == "brief.txt"
    assert use_case.command.declared_mime_type == "text/plain"
    assert use_case.command.content == "متن فارسی".encode()


@pytest.mark.parametrize(
    "kwargs",
    (
        {"source_type": "text"},
        {"extra": True},
    ),
)
def test_file_context_rejects_non_exact_multipart(kwargs: dict[str, object]) -> None:
    client, _, context, token = _fixture()
    response = _post(client, context, token, **kwargs)  # type: ignore[arg-type]
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_file_context_is_fail_closed_when_feature_flag_is_off() -> None:
    client, use_case, context, token = _fixture(enabled=False)
    response = _post(client, context, token)
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FEATURE_NOT_ENABLED",
        "message": "This feature is not enabled.",
        "retryable": False,
    }
    assert use_case.command is None


@pytest.mark.parametrize("size", (200_001, 1_100_000))
def test_file_context_maps_every_oversized_multipart_file_to_413_before_use_case(
    size: int,
) -> None:
    client, use_case, context, token = _fixture()
    response = _post(client, context, token, content=b"a" * size)

    assert response.status_code == 413
    assert response.json()["error"] == {
        "code": "FILE_TOO_LARGE",
        "message": "The uploaded file exceeds the allowed size.",
        "retryable": False,
    }
    assert use_case.command is None


@pytest.mark.parametrize(
    ("error", "status_code", "code", "retryable"),
    (
        (UnsupportedFileTypeError(), 415, "UNSUPPORTED_FILE_TYPE", False),
        (FileTooLargeError(), 413, "FILE_TOO_LARGE", False),
        (FileUploadValidationError(), 422, "VALIDATION_FAILED", False),
        (FileContextIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT", False),
        (FileContextNotFound(), 404, "RESOURCE_NOT_FOUND", False),
        (FileContextPermissionDenied(), 403, "MEMBERSHIP_REQUIRED", False),
        (FileContextStorageFailure(retryable=True), 503, "STORAGE_ERROR", True),
        (FileContextStorageFailure(retryable=False), 503, "STORAGE_ERROR", False),
    ),
)
def test_file_context_maps_frozen_error_contract(
    error: Exception,
    status_code: int,
    code: str,
    retryable: bool,
) -> None:
    client, use_case, context, token = _fixture()
    use_case.error = error
    response = _post(client, context, token)
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["retryable"] is retryable
