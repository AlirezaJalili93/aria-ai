from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.account_discovery import AccountSelection
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.projects.application.project_service import (
    CreateProjectCommand,
    ProjectNotFound,
    ProjectPermissionDenied,
    ProjectVersionConflict,
    UpdateProjectCommand,
)
from app.modules.projects.domain.project import Project


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


class StubAccountDiscovery:
    def __init__(self, values: tuple[AccountSelection, ...]) -> None:
        self._values = values

    async def execute(
        self, identity: AuthenticatedIdentity
    ) -> tuple[AccountSelection, ...]:
        del identity
        return self._values


class StubProjectService:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.create_command: CreateProjectCommand | None = None
        self.update_command: UpdateProjectCommand | None = None
        self.get_error: Exception | None = None
        self.update_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.list_rows: tuple[Project, ...] = (project,)
        self.list_calls: list[tuple[int, datetime | None, UUID | None]] = []

    async def create(
        self, context: TenantContext, command: CreateProjectCommand
    ) -> Project:
        del context
        self.create_command = command
        return self.project

    async def get(self, context: TenantContext, project_id: UUID) -> Project:
        del context, project_id
        if self.get_error is not None:
            raise self.get_error
        return self.project

    async def list(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Project, ...]:
        del context
        self.list_calls.append((limit, cursor_created_at, cursor_id))
        return self.list_rows

    async def update(
        self,
        context: TenantContext,
        project_id: UUID,
        command: UpdateProjectCommand,
    ) -> Project:
        del context, project_id
        self.update_command = command
        if self.update_error is not None:
            raise self.update_error
        return self.project

    async def soft_delete(self, context: TenantContext, project_id: UUID) -> Project:
        del context, project_id
        if self.delete_error is not None:
            raise self.delete_error
        return self.project


def _fixture() -> tuple[TestClient, StubProjectService, TenantContext, str]:
    token = "project-api-token"
    subject = uuid4()
    account_id = uuid4()
    now = datetime.now(UTC)
    context = TenantContext(
        subject_id=subject,
        account_id=account_id,
        membership_id=uuid4(),
        role="owner",
        membership_status="active",
    )
    project = Project(
        id=uuid4(),
        account_id=account_id,
        owner_id=subject,
        title="Project",
        project_type="landing",
        status="draft",
        current_context_version=0,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    service = StubProjectService(project)
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(token, subject),
        tenant_context_resolver=StubTenantContextResolver(context),
        account_discovery=StubAccountDiscovery(
            (
                AccountSelection(id=account_id, role="owner"),
                AccountSelection(id=uuid4(), role="member"),
            )
        ),
        project_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service, context, token


def _headers(context: TenantContext, token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Account-ID": str(context.account_id),
    }


def test_account_discovery_returns_exact_pre_tenant_collection_envelope() -> None:
    client, _, context, token = _fixture()
    response = client.get(
        "/api/v1/accounts",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Account-ID": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"][0] == {"id": str(context.account_id), "role": "owner"}
    assert set(body["data"][1]) == {"id", "role"}
    assert body["meta"]["next_cursor"] is None
    assert body["meta"]["has_more"] is False
    UUID(body["meta"]["request_id"])
    unauthorized = client.get("/api/v1/accounts")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "AUTH_REQUIRED"
    assert client.get("/api/v1/account-contexts").status_code == 404


def test_create_requires_idempotency_and_accepts_no_description() -> None:
    client, service, context, token = _fixture()
    headers = _headers(context, token)
    missing = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"title": "Project", "project_type": "landing"},
    )
    extra = client.post(
        "/api/v1/projects",
        headers={**headers, "Idempotency-Key": "extra-field"},
        json={"title": "Project", "project_type": "landing", "description": "no"},
    )
    created = client.post(
        "/api/v1/projects",
        headers={**headers, "Idempotency-Key": "create-project"},
        json={"title": " Project ", "project_type": "landing"},
    )

    assert missing.status_code == 422
    assert extra.status_code == 422
    assert created.status_code == 201
    assert service.create_command == CreateProjectCommand(
        title=" Project ", project_type="landing", idempotency_key="create-project"
    )
    assert "description" not in created.json()


def test_missing_and_cross_tenant_project_share_safe_404() -> None:
    client, service, context, token = _fixture()
    service.get_error = ProjectNotFound()
    response = client.get(
        f"/api/v1/projects/{uuid4()}", headers=_headers(context, token)
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "The requested resource was not found.",
        "retryable": False,
    }


def test_patch_maps_stale_version_and_delete_maps_role_denial() -> None:
    client, service, context, token = _fixture()
    headers = _headers(context, token)
    service.update_error = ProjectVersionConflict()
    patched = client.patch(
        f"/api/v1/projects/{service.project.id}",
        headers=headers,
        json={
            "title": "Updated",
            "expected_updated_at": service.project.updated_at.isoformat(),
        },
    )
    service.delete_error = ProjectPermissionDenied()
    deleted = client.delete(
        f"/api/v1/projects/{service.project.id}", headers=headers
    )

    assert patched.status_code == 409
    assert patched.json()["error"]["code"] == "VERSION_CONFLICT"
    assert deleted.status_code == 403
    assert deleted.json()["error"]["code"] == "FORBIDDEN"


def test_invalid_cursor_has_stable_validation_error() -> None:
    client, _, context, token = _fixture()
    response = client.get(
        "/api/v1/projects?cursor=not-a-cursor",
        headers=_headers(context, token),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_project_list_uses_default_limit_and_opaque_cursor() -> None:
    client, service, context, token = _fixture()
    service.list_rows = tuple(
        Project(
            id=uuid4(),
            account_id=service.project.account_id,
            owner_id=service.project.owner_id,
            title=f"Project {index}",
            project_type="landing",
            status="draft",
            current_context_version=0,
            created_at=service.project.created_at,
            updated_at=service.project.updated_at,
            deleted_at=None,
        )
        for index in range(21)
    )
    response = client.get("/api/v1/projects", headers=_headers(context, token))

    assert response.status_code == 200
    assert len(response.json()["data"]) == 20
    assert response.json()["meta"]["has_more"] is True
    assert response.json()["meta"]["next_cursor"]
    assert service.list_calls == [(21, None, None)]
    excessive = client.get(
        "/api/v1/projects?limit=101", headers=_headers(context, token)
    )
    assert excessive.status_code == 422
    assert excessive.json()["error"]["code"] == "VALIDATION_FAILED"
