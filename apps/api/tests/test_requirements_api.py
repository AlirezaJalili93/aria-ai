from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.requirements.application.requirement_crud_service import (
    CreateManualRequirementCommand,
    RequirementContextRequired,
    RequirementInvalidState,
    RequirementNotFound,
    RequirementVersionConflict,
    UpdateRequirementCommand,
)
from app.modules.requirements.domain.requirement import Requirement

SUBJECT, ACCOUNT_ID, PROJECT_ID = uuid4(), uuid4(), uuid4()


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != "requirements-token":
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=SUBJECT)


class StubTenantContextResolver:
    async def execute(
        self, identity: AuthenticatedIdentity, account_id: UUID
    ) -> TenantContext:
        assert identity.subject == SUBJECT
        assert account_id == ACCOUNT_ID
        return _context()


class StubRequirementCrudService:
    def __init__(self, requirement: Requirement) -> None:
        self.requirement = requirement
        self.rows = tuple(requirement for _ in range(21))
        self.error: Exception | None = None
        self.create_command: CreateManualRequirementCommand | None = None
        self.update_command: UpdateRequirementCommand | None = None
        self.list_kwargs: dict[str, object] | None = None

    async def create_manual(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        command: CreateManualRequirementCommand,
    ) -> Requirement:
        del context
        assert project_id == PROJECT_ID
        self.create_command = command
        if self.error is not None:
            raise self.error
        return self.requirement

    async def list(
        self, context: TenantContext, *, project_id: UUID, **kwargs: object
    ) -> tuple[Requirement, ...]:
        del context
        assert project_id == PROJECT_ID
        self.list_kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.rows

    async def update(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        requirement_id: UUID,
        command: UpdateRequirementCommand,
    ) -> Requirement:
        del context
        assert project_id == PROJECT_ID
        assert requirement_id == self.requirement.id
        self.update_command = command
        if self.error is not None:
            raise self.error
        return self.requirement

    async def remove_draft(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        requirement_id: UUID,
    ) -> None:
        del context
        assert project_id == PROJECT_ID
        assert requirement_id == self.requirement.id
        if self.error is not None:
            raise self.error


def _context() -> TenantContext:
    return TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _requirement() -> Requirement:
    now = datetime.now(UTC)
    return Requirement(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=2,
        category="functional",
        title="عنوان",
        description="شرح",
        priority="must",
        status="draft",
        source_refs=(),
        confidence=None,
        is_unsupported=False,
        created_by_type="user",
        created_by=SUBJECT,
        acceptance_note=None,
        created_at=now,
        updated_at=now,
    )


def _fixture() -> tuple[TestClient, StubRequirementCrudService]:
    service = StubRequirementCrudService(_requirement())
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        requirement_crud_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers(*, idempotency_key: str | None = None) -> dict[str, str]:
    values = {
        "Authorization": "Bearer requirements-token",
        "X-Account-ID": str(ACCOUNT_ID),
    }
    if idempotency_key is not None:
        values["Idempotency-Key"] = idempotency_key
    return values


def test_requirement_list_is_paginated_filtered_and_exposes_only_public_fields() -> None:
    client, service = _fixture()
    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/requirements?category=functional&status=draft&limit=20",
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 20
    assert body["meta"]["has_more"] is True
    assert body["meta"]["next_cursor"]
    assert service.list_kwargs is not None
    assert service.list_kwargs["category"] == "functional"
    assert service.list_kwargs["status"] == "draft"
    assert service.list_kwargs["limit"] == 21
    assert set(body["data"][0]) == {
        "id",
        "context_version",
        "category",
        "title",
        "description",
        "priority",
        "status",
        "source_refs",
        "confidence",
        "is_unsupported",
        "created_by_type",
        "acceptance_note",
        "created_at",
        "updated_at",
    }
    assert "account_id" not in body["data"][0]
    assert "generation_job_id" not in body["data"][0]
    assert "duplicate_group_key" not in body["data"][0]


def test_manual_create_requires_idempotency_and_accepts_only_approved_input() -> None:
    client, service = _fixture()
    payload = {
        "title": "عنوان",
        "description": "شرح",
        "category": "business",
        "priority": "should",
    }
    missing_key = client.post(
        f"/api/v1/projects/{PROJECT_ID}/requirements",
        headers=_headers(),
        json=payload,
    )
    extra_field = client.post(
        f"/api/v1/projects/{PROJECT_ID}/requirements",
        headers=_headers(idempotency_key="extra"),
        json={**payload, "acceptance_note": "deferred on create"},
    )
    created = client.post(
        f"/api/v1/projects/{PROJECT_ID}/requirements",
        headers=_headers(idempotency_key="manual-1"),
        json=payload,
    )

    assert missing_key.status_code == 422
    assert extra_field.status_code == 422
    assert created.status_code == 201
    assert service.create_command == CreateManualRequirementCommand(
        title="عنوان",
        description="شرح",
        category="business",
        priority="should",
        idempotency_key="manual-1",
    )
    assert created.json()["meta"]["request_id"]


def test_manual_create_without_context_has_stable_domain_error() -> None:
    client, service = _fixture()
    service.error = RequirementContextRequired()
    response = client.post(
        f"/api/v1/projects/{PROJECT_ID}/requirements",
        headers=_headers(idempotency_key="no-context"),
        json={
            "title": "عنوان",
            "description": "شرح",
            "category": "content",
            "priority": "could",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "CONTEXT_VERSION_REQUIRED",
        "message": "A valid Project Context Version is required.",
        "retryable": False,
    }


def test_patch_preserves_explicit_null_note_and_maps_concurrency_and_state() -> None:
    client, service = _fixture()
    requirement = service.requirement
    response = client.patch(
        f"/api/v1/projects/{PROJECT_ID}/requirements/{requirement.id}",
        headers=_headers(),
        json={
            "expected_updated_at": requirement.updated_at.isoformat(),
            "title": "عنوان جدید",
            "acceptance_note": None,
        },
    )

    assert response.status_code == 200
    assert service.update_command is not None
    assert service.update_command.title == "عنوان جدید"
    assert service.update_command.acceptance_note is None
    assert service.update_command.acceptance_note_set is True

    for error, code in (
        (RequirementVersionConflict(), "VERSION_CONFLICT"),
        (RequirementInvalidState(), "INVALID_REQUIREMENT_STATE"),
    ):
        service.error = error
        failed = client.patch(
            f"/api/v1/projects/{PROJECT_ID}/requirements/{requirement.id}",
            headers=_headers(),
            json={
                "expected_updated_at": requirement.updated_at.isoformat(),
                "status": "confirmed",
            },
        )
        assert failed.status_code == 409
        assert failed.json()["error"]["code"] == code


def test_delete_is_soft_command_and_cross_tenant_remains_safe_not_found() -> None:
    client, service = _fixture()
    requirement = service.requirement
    deleted = client.delete(
        f"/api/v1/projects/{PROJECT_ID}/requirements/{requirement.id}",
        headers=_headers(),
    )
    assert deleted.status_code == 204
    assert deleted.content == b""

    service.error = RequirementNotFound()
    hidden = client.delete(
        f"/api/v1/projects/{PROJECT_ID}/requirements/{requirement.id}",
        headers=_headers(),
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_invalid_cursor_and_unapproved_status_fail_validation() -> None:
    client, service = _fixture()
    bad_cursor = client.get(
        f"/api/v1/projects/{PROJECT_ID}/requirements?cursor=invalid",
        headers=_headers(),
    )
    bad_status = client.patch(
        f"/api/v1/projects/{PROJECT_ID}/requirements/{service.requirement.id}",
        headers=_headers(),
        json={
            "expected_updated_at": service.requirement.updated_at.isoformat(),
            "status": "removed",
        },
    )
    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["error"]["code"] == "VALIDATION_FAILED"
    assert bad_status.status_code == 422
    assert bad_status.json()["error"]["code"] == "VALIDATION_FAILED"
