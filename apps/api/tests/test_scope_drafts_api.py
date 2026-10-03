from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_draft_service import (
    ScopeDraftAccessNotFound,
    ScopeDraftEditConflict,
    ScopeDraftStale,
    UpdateScopeSectionCommand,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS, ScopeDraft

SUBJECT, ACCOUNT_ID, PROJECT_ID = uuid4(), uuid4(), uuid4()


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != "scope-token":
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


class StubScopeDraftService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.draft = ScopeDraft(
            id=uuid4(),
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            context_version=2,
            content={
                "schema_version": "scope_content_schema_v1",
                "sections": [
                    {
                        "section_id": section_id,
                        "value": []
                        if section_id not in {"summary", "visual_direction"}
                        else "",
                        "trace": {
                            "context_item_ids": [],
                            "requirement_ids": [],
                            "gap_ids": [],
                        },
                    }
                    for section_id in SECTION_IDS
                ],
            },
            updated_by_type="system",
            created_at=now,
            updated_at=now,
        )
        self.error: Exception | None = None
        self.command: UpdateScopeSectionCommand | None = None
        self.section_id: str | None = None

    async def get_current(self, context: TenantContext, *, project_id: UUID) -> ScopeDraft:
        del context
        assert project_id == PROJECT_ID
        if self.error:
            raise self.error
        return self.draft

    async def update_section(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        section_id: str,
        command: UpdateScopeSectionCommand,
    ) -> ScopeDraft:
        del context
        assert project_id == PROJECT_ID
        self.command = command
        self.section_id = section_id
        if self.error:
            raise self.error
        return self.draft


def _fixture() -> tuple[TestClient, StubScopeDraftService]:
    service = StubScopeDraftService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        scope_draft_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer scope-token",
        "X-Account-ID": str(ACCOUNT_ID),
    }


def test_get_current_scope_exposes_only_canonical_response_fields() -> None:
    client, service = _fixture()
    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/scope/draft", headers=_headers()
    )

    assert response.status_code == 200
    assert set(response.json()["data"]) == {
        "id",
        "context_version",
        "content",
        "updated_at",
    }
    assert response.json()["data"]["id"] == str(service.draft.id)
    assert "account_id" not in response.json()["data"]


def test_patch_accepts_value_only_and_rejects_client_trace() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/draft/sections/summary"
    response = client.patch(
        path,
        headers=_headers(),
        json={
            "value": "خلاصه جدید",
            "expected_updated_at": service.draft.updated_at.isoformat(),
        },
    )
    trace_attempt = client.patch(
        path,
        headers=_headers(),
        json={
            "value": "خلاصه",
            "expected_updated_at": service.draft.updated_at.isoformat(),
            "trace": {"context_item_ids": []},
        },
    )

    assert response.status_code == 200
    assert service.section_id == "summary"
    assert service.command is not None and service.command.value == "خلاصه جدید"
    assert trace_attempt.status_code == 422
    assert trace_attempt.json()["error"]["code"] == "VALIDATION_FAILED"


def test_scope_api_maps_missing_conflict_and_stale_without_enumeration() -> None:
    client, service = _fixture()
    get_path = f"/api/v1/projects/{PROJECT_ID}/scope/draft"
    patch_path = f"{get_path}/sections/summary"
    payload = {
        "value": "تغییر",
        "expected_updated_at": service.draft.updated_at.isoformat(),
    }

    service.error = ScopeDraftAccessNotFound()
    missing = client.get(get_path, headers=_headers())
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    service.error = ScopeDraftEditConflict()
    conflict = client.patch(patch_path, headers=_headers(), json=payload)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "VERSION_CONFLICT"

    service.error = ScopeDraftStale()
    stale = client.patch(patch_path, headers=_headers(), json=payload)
    assert stale.status_code == 409
    assert stale.json()["error"] == {
        "code": "SCOPE_DRAFT_STALE",
        "message": "The Scope Draft belongs to a historical Context Version.",
        "retryable": False,
    }


def test_scope_routes_require_tenant_auth_and_canonical_section_id() -> None:
    client, service = _fixture()
    base = f"/api/v1/projects/{PROJECT_ID}/scope/draft"
    assert client.get(base).status_code == 401
    invalid = client.patch(
        f"{base}/sections/invented",
        headers=_headers(),
        json={
            "value": "x",
            "expected_updated_at": service.draft.updated_at.isoformat(),
        },
    )
    assert invalid.status_code == 422
