from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.context.application.context_source_management import (
    ContextSourceBusy,
    ContextSourceJobSummary,
    ContextSourceNotFound,
    ContextSourceVersionSummary,
    ContextSourceView,
)
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.job_retry import (
    JobRetryIdempotencyConflict,
    JobRetryNotAllowed,
    JobRetryNotFound,
    RetriedJob,
)

SUBJECT_ID = uuid4()
ACCOUNT_ID = uuid4()
PROJECT_ID = uuid4()
SOURCE_ID = uuid4()
VERSION_ID = uuid4()
JOB_ID = uuid4()
RETRY_JOB_ID = uuid4()
AUTH_FIXTURE_VALUE = "context-source-management-token"
NOW = datetime.now(UTC)
CONTEXT = TenantContext(
    subject_id=SUBJECT_ID,
    account_id=ACCOUNT_ID,
    membership_id=uuid4(),
    role="member",
    membership_status="active",
)


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != AUTH_FIXTURE_VALUE:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=SUBJECT_ID)


class StubTenantContextResolver:
    async def execute(self, identity: AuthenticatedIdentity, account_id: UUID) -> TenantContext:
        assert identity.subject == SUBJECT_ID
        assert account_id == ACCOUNT_ID
        return CONTEXT


class StubContextSourceManagementService:
    def __init__(self, row: ContextSourceView) -> None:
        self.row = row
        self.error: Exception | None = None
        self.list_calls: list[tuple[int, datetime | None, UUID | None]] = []

    async def list(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[ContextSourceView, ...]:
        assert context == CONTEXT
        assert project_id == PROJECT_ID
        if self.error is not None:
            raise self.error
        self.list_calls.append((limit, cursor_created_at, cursor_id))
        return (self.row,)

    async def get(
        self, context: TenantContext, *, project_id: UUID, source_id: UUID
    ) -> ContextSourceView:
        assert context == CONTEXT
        assert project_id == PROJECT_ID
        assert source_id == SOURCE_ID
        if self.error is not None:
            raise self.error
        return self.row

    async def archive(self, context: TenantContext, *, project_id: UUID, source_id: UUID) -> None:
        assert context == CONTEXT
        assert project_id == PROJECT_ID
        assert source_id == SOURCE_ID
        if self.error is not None:
            raise self.error


class StubRetryJobUseCase:
    def __init__(self) -> None:
        self.error: Exception | None = None

    async def execute(self, context: TenantContext, command) -> RetriedJob:
        assert context == CONTEXT
        assert command.job_id == JOB_ID
        assert command.idempotency_key == "retry-key"
        if self.error is not None:
            raise self.error
        return RetriedJob(id=RETRY_JOB_ID, status="queued", retry_of_job_id=JOB_ID)


def _row() -> ContextSourceView:
    version = ContextSourceVersionSummary(
        id=VERSION_ID,
        version_no=1,
        parse_status="failed",
        created_at=NOW,
    )
    job = ContextSourceJobSummary(
        id=JOB_ID,
        status="failed",
        retryable=True,
        error_code="PARSER_STORAGE_UNAVAILABLE",
        created_at=NOW,
    )
    return ContextSourceView(
        id=SOURCE_ID,
        source_type="file",
        status="failed",
        original_name="brief.txt",
        mime_type="text/plain",
        created_at=NOW,
        updated_at=NOW,
        created_by=SUBJECT_ID,
        latest_version=version,
        current_ready_version=None,
        latest_job=job,
    )


def _fixture() -> tuple[TestClient, StubContextSourceManagementService, StubRetryJobUseCase]:
    source_service = StubContextSourceManagementService(_row())
    retry_service = StubRetryJobUseCase()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        context_source_management_service=source_service,  # type: ignore[arg-type]
        job_retry_use_case=retry_service,  # type: ignore[arg-type]
    )
    return TestClient(app), source_service, retry_service


def _headers(*, retry: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {AUTH_FIXTURE_VALUE}",
        "X-Account-ID": str(ACCOUNT_ID),
    }
    if retry:
        headers["Idempotency-Key"] = "retry-key"
    return headers


def test_source_list_and_detail_expose_only_safe_projection() -> None:
    client, service, _ = _fixture()
    listed = client.get(f"/api/v1/projects/{PROJECT_ID}/context-sources", headers=_headers())
    assert listed.status_code == 200
    data = listed.json()["data"][0]
    assert data["id"] == str(SOURCE_ID)
    assert data["can_archive"] is False
    assert data["latest_version"]["id"] == str(VERSION_ID)
    assert data["latest_job"] == {
        "id": str(JOB_ID),
        "status": "failed",
        "retryable": True,
        "error_code": "PARSER_STORAGE_UNAVAILABLE",
        "status_url": f"/api/v1/jobs/{JOB_ID}",
        "created_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    serialized = listed.text
    for forbidden in (
        "raw_text",
        "canonical_text",
        "storage_ref",
        "object_key",
        "content_hash",
        "payload_ref",
        "created_by",
    ):
        assert forbidden not in serialized
    assert service.list_calls == [(21, None, None)]

    detail = client.get(
        f"/api/v1/projects/{PROJECT_ID}/context-sources/{SOURCE_ID}",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["current_ready_version"] is None


def test_source_missing_and_archive_denials_use_frozen_errors() -> None:
    client, service, _ = _fixture()
    service.error = ContextSourceNotFound()
    missing = client.get(
        f"/api/v1/projects/{PROJECT_ID}/context-sources/{SOURCE_ID}",
        headers=_headers(),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    service.error = ContextSourceBusy()
    busy = client.delete(
        f"/api/v1/projects/{PROJECT_ID}/context-sources/{SOURCE_ID}",
        headers=_headers(),
    )
    assert busy.status_code == 409
    assert busy.json()["error"] == {
        "code": "CONTEXT_SOURCE_BUSY",
        "message": "The Context Source is currently being processed.",
        "retryable": False,
    }

    service.error = None
    assert (
        client.delete(
            f"/api/v1/projects/{PROJECT_ID}/context-sources/{SOURCE_ID}",
            headers=_headers(),
        ).status_code
        == 204
    )


def test_explicit_retry_returns_relative_status_url_and_stable_errors() -> None:
    client, _, retry = _fixture()
    response = client.post(f"/api/v1/jobs/{JOB_ID}/retry", headers=_headers(retry=True))
    assert response.status_code == 202
    assert response.json()["data"] == {
        "job_id": str(RETRY_JOB_ID),
        "status": "queued",
        "retry_of_job_id": str(JOB_ID),
        "status_url": f"/api/v1/jobs/{RETRY_JOB_ID}",
    }

    retry.error = JobRetryNotAllowed()
    rejected = client.post(f"/api/v1/jobs/{JOB_ID}/retry", headers=_headers(retry=True))
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "JOB_NOT_RETRYABLE"

    retry.error = JobRetryIdempotencyConflict()
    conflict = client.post(f"/api/v1/jobs/{JOB_ID}/retry", headers=_headers(retry=True))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    retry.error = JobRetryNotFound()
    hidden = client.post(f"/api/v1/jobs/{JOB_ID}/retry", headers=_headers(retry=True))
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
