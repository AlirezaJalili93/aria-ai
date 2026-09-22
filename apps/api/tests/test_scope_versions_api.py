from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_version_service import (
    CreateScopeVersionCommand,
    ScopeVersionAccessNotFound,
    ScopeVersionCreateConflict,
    ScopeVersionIdempotencyConflict,
    ScopeVersionNotReady,
    ScopeVersionUnchanged,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.domain.scope_version import ScopeVersion, hash_scope_snapshot


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


def _content() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


def _version(version_no: int = 1) -> ScopeVersion:
    data = _content()
    return ScopeVersion(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        version_no=version_no,
        context_version=2,
        status="awaiting_approval",
        snapshot_data=data,
        snapshot_hash=hash_scope_snapshot(data),
        created_by=SUBJECT,
        created_at=NOW,
    )


class StubScopeVersionService:
    def __init__(self) -> None:
        self.rows: tuple[ScopeVersion, ...] = (_version(),)
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None
        self.list_error: Exception | None = None
        self.command: CreateScopeVersionCommand | None = None

    async def create(self, context, *, project_id, command):
        del context, project_id
        self.command = command
        if self.create_error is not None:
            raise self.create_error
        return self.rows[0]

    async def get(self, context, *, project_id, version_no):
        del context, project_id
        if self.get_error is not None:
            raise self.get_error
        return next((row for row in self.rows if row.version_no == version_no), self.rows[0])

    async def list(self, context, *, project_id, limit, before_version_no):
        del context, project_id, before_version_no
        if self.list_error is not None:
            raise self.list_error
        return self.rows[:limit]


SUBJECT, ACCOUNT_ID, PROJECT_ID = uuid4(), uuid4(), uuid4()
NOW = datetime.now(UTC)
AUTH_VALUE = "scope-version-token"


def _fixture() -> tuple[TestClient, StubScopeVersionService, TenantContext]:
    context = TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )
    service = StubScopeVersionService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(AUTH_VALUE, SUBJECT),
        tenant_context_resolver=StubTenantContextResolver(context),
        scope_version_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service, context


def _headers(context: TenantContext) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {AUTH_VALUE}",
        "X-Account-ID": str(context.account_id),
    }


def test_create_requires_idempotency_and_returns_minimal_summary() -> None:
    client, service, context = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions"
    missing = client.post(
        path,
        headers=_headers(context),
        json={"expected_draft_updated_at": NOW.isoformat()},
    )
    created = client.post(
        path,
        headers={**_headers(context), "Idempotency-Key": "freeze-1"},
        json={"expected_draft_updated_at": NOW.isoformat()},
    )

    assert missing.status_code == 422
    assert created.status_code == 201
    assert service.command == CreateScopeVersionCommand(NOW, "freeze-1")
    assert set(created.json()["data"]) == {
        "version_no",
        "context_version",
        "status",
        "snapshot_hash",
        "schema_version",
        "created_at",
    }
    assert "created_by" not in created.json()["data"]
    assert "snapshot_data" not in created.json()["data"]


def test_create_maps_all_frozen_failure_contracts() -> None:
    client, service, context = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions"
    headers = {**_headers(context), "Idempotency-Key": "freeze"}
    cases = (
        (ScopeVersionAccessNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ScopeVersionCreateConflict(), 409, "VERSION_CONFLICT"),
        (ScopeVersionNotReady(), 422, "CRITICAL_GAPS_OPEN"),
        (ScopeVersionUnchanged(), 409, "SCOPE_VERSION_UNCHANGED"),
        (ScopeVersionIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
    )
    for error, expected_status, expected_code in cases:
        service.create_error = error
        response = client.post(
            path,
            headers=headers,
            json={"expected_draft_updated_at": NOW.isoformat()},
        )
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
        assert response.json()["error"]["retryable"] is False


def test_list_is_summary_only_and_detail_contains_snapshot() -> None:
    client, service, context = _fixture()
    service.rows = tuple(_version(index) for index in range(21, 0, -1))
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions"
    listed = client.get(path, headers=_headers(context))
    detailed = client.get(f"{path}/1", headers=_headers(context))

    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 20
    assert listed.json()["meta"]["has_more"] is True
    assert listed.json()["meta"]["next_cursor"]
    assert all("snapshot_data" not in item for item in listed.json()["data"])
    assert detailed.status_code == 200
    assert detailed.json()["data"]["snapshot_data"] == _content()


def test_cross_tenant_safe_not_found_and_no_mutation_routes() -> None:
    client, service, context = _fixture()
    service.get_error = ScopeVersionAccessNotFound()
    service.list_error = ScopeVersionAccessNotFound()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions"

    assert client.get(path, headers=_headers(context)).status_code == 404
    assert client.get(f"{path}/1", headers=_headers(context)).status_code == 404
    assert client.patch(f"{path}/1", headers=_headers(context), json={}).status_code == 405
    assert client.delete(f"{path}/1", headers=_headers(context)).status_code == 405
