from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_revision_service import (
    CreateScopeRevisionCommand,
    ScopeRevisionAccessNotFound,
    ScopeRevisionIdempotencyConflict,
    ScopeRevisionNotReady,
    ScopeRevisionResult,
    ScopeRevisionStale,
    ScopeRevisionUnchanged,
    ScopeRevisionVersionConflict,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.domain.scope_version import ScopeVersion, hash_scope_snapshot

SUBJECT, ACCOUNT_ID, PROJECT_ID, CHANGE_REQUEST_ID = uuid4(), uuid4(), uuid4(), uuid4()
NOW = datetime.now(UTC)
AUTH_VALUE = "scope-revision-token"


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != AUTH_VALUE:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=SUBJECT)


class StubTenantContextResolver:
    async def execute(
        self, identity: AuthenticatedIdentity, account_id: UUID
    ) -> TenantContext:
        assert identity.subject == SUBJECT
        assert account_id == ACCOUNT_ID
        return TenantContext(
            subject_id=SUBJECT,
            account_id=ACCOUNT_ID,
            membership_id=uuid4(),
            role="member",
            membership_status="active",
        )


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


def _version() -> ScopeVersion:
    content = _content()
    return ScopeVersion(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        version_no=2,
        context_version=1,
        status="awaiting_approval",
        snapshot_data=content,
        snapshot_hash=hash_scope_snapshot(content),
        created_by=SUBJECT,
        created_at=NOW,
        revision_of_scope_version_id=uuid4(),
        change_request_id=CHANGE_REQUEST_ID,
    )


class StubRevisionService:
    def __init__(self) -> None:
        self.command: CreateScopeRevisionCommand | None = None
        self.error: Exception | None = None
        self.replayed = False

    async def create(self, context, *, project_id, target_version_no, command):
        del context
        assert project_id == PROJECT_ID
        assert target_version_no == 1
        self.command = command
        if self.error is not None:
            raise self.error
        return ScopeRevisionResult(version=_version(), replayed=self.replayed)


def _fixture() -> tuple[TestClient, StubRevisionService]:
    service = StubRevisionService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        scope_revision_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {AUTH_VALUE}",
        "X-Account-ID": str(ACCOUNT_ID),
        "Idempotency-Key": "revision-1",
    }


def _body() -> dict[str, str]:
    return {
        "change_request_id": str(CHANGE_REQUEST_ID),
        "expected_draft_updated_at": NOW.isoformat(),
    }


def test_revision_returns_201_then_200_replay_with_same_business_result() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions/1/revisions"
    created = client.post(path, headers=_headers(), json=_body())
    service.replayed = True
    replayed = client.post(path, headers=_headers(), json=_body())

    assert created.status_code == 201
    assert created.json()["meta"]["replayed"] is False
    assert replayed.status_code == 200
    assert replayed.json()["meta"]["replayed"] is True
    assert created.json()["data"] == replayed.json()["data"]
    assert service.command == CreateScopeRevisionCommand(
        CHANGE_REQUEST_ID, NOW, "revision-1"
    )
    assert "snapshot_data" not in created.json()["data"]


def test_revision_enforces_exact_body_and_maps_frozen_errors() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions/1/revisions"
    invalid = client.post(path, headers=_headers(), json={**_body(), "comment": "leak"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_FAILED"

    cases = (
        (ScopeRevisionAccessNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ScopeRevisionIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (ScopeRevisionStale(), 409, "SCOPE_REVISION_STALE"),
        (ScopeRevisionVersionConflict(), 409, "VERSION_CONFLICT"),
        (ScopeRevisionNotReady(), 422, "CRITICAL_GAPS_OPEN"),
        (ScopeRevisionUnchanged(), 409, "SCOPE_VERSION_UNCHANGED"),
    )
    for error, status_code, code in cases:
        service.error = error
        response = client.post(path, headers=_headers(), json=_body())
        assert response.status_code == status_code
        assert response.json()["error"]["code"] == code
