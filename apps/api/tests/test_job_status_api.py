from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.application.job_status import (
    JobNotFound,
    JobStatusError,
    JobStatusView,
)


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


class StubJobStatusService:
    def __init__(self, view: JobStatusView) -> None:
        self.view = view
        self.error: Exception | None = None

    async def get(self, context: TenantContext, job_id: UUID) -> JobStatusView:
        assert context.account_id == ACCOUNT_ID
        assert job_id == self.view.id
        if self.error is not None:
            raise self.error
        return self.view


SUBJECT_ID = uuid4()
ACCOUNT_ID = uuid4()
JOB_ID = uuid4()
TOKEN = "job-status-token"
NOW = datetime.now(UTC)
CONTEXT = TenantContext(
    subject_id=SUBJECT_ID,
    account_id=ACCOUNT_ID,
    membership_id=uuid4(),
    role="member",
    membership_status="active",
)


def _fixture() -> tuple[TestClient, StubJobStatusService]:
    service = StubJobStatusService(
        JobStatusView(
            id=JOB_ID,
            job_type="context_parse",
            status="failed",
            progress_stage=None,
            retryable=False,
            error=JobStatusError(code="CONTEXT_PARSE_FAILED", detail="safe detail"),
        )
    )
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(TOKEN, SUBJECT_ID),
        tenant_context_resolver=StubTenantContextResolver(CONTEXT),
        job_status_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
        "X-Account-ID": str(ACCOUNT_ID),
    }


def test_job_status_returns_only_approved_public_fields() -> None:
    client, _ = _fixture()
    response = client.get(f"/api/v1/jobs/{JOB_ID}", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {
        "id": str(JOB_ID),
        "job_type": "context_parse",
        "status": "failed",
        "progress_stage": None,
        "retryable": False,
        "error": {"code": "CONTEXT_PARSE_FAILED", "detail": "safe detail"},
    }
    assert set(body["data"]) == {
        "id",
        "job_type",
        "status",
        "progress_stage",
        "retryable",
        "error",
    }
    UUID(body["meta"]["request_id"])


def test_job_status_missing_or_cross_tenant_is_safe_not_found() -> None:
    client, service = _fixture()
    service.error = JobNotFound()
    response = client.get(f"/api/v1/jobs/{JOB_ID}", headers=_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_job_status_requires_authenticated_tenant_context() -> None:
    client, _ = _fixture()
    assert client.get(f"/api/v1/jobs/{JOB_ID}").status_code == 401
    response = client.get(
        f"/api/v1/jobs/{JOB_ID}",
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ACCOUNT_CONTEXT_REQUIRED"
