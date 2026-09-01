from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from aria_observability import current_trace_context
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.api.dependencies.tenant_context import require_tenant_context
from app.api.errors import (
    ForbiddenError,
    IdempotencyConflictError,
    ResourceNotFoundError,
    ValidationFailedError,
    VersionConflictError,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.projects.application.project_service import (
    CreateProjectCommand,
    ProjectApplicationService,
    ProjectIdempotencyConflict,
    ProjectNotFound,
    ProjectPermissionDenied,
    ProjectReadOnly,
    ProjectVersionConflict,
    UpdateProjectCommand,
)
from app.modules.projects.domain.project import (
    Project,
    ProjectStatus,
    ProjectType,
    ProjectValidationError,
)


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    project_type: ProjectType


class UpdateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    expected_updated_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    account_id: UUID
    owner_id: UUID
    title: str
    project_type: ProjectType
    status: ProjectStatus
    current_context_version: int
    created_at: datetime
    updated_at: datetime


class CollectionMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    next_cursor: str | None
    has_more: bool


class ProjectsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ProjectResponse]
    meta: CollectionMeta


def _project_service(request: Request) -> ProjectApplicationService:
    return cast(ProjectApplicationService, request.app.state.project_service)


def create_projects_router() -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])

    @router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
    async def create_project(
        body: CreateProjectRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ProjectApplicationService, Depends(_project_service)],
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> ProjectResponse:
        try:
            project = await service.create(
                context,
                CreateProjectCommand(
                    title=body.title,
                    project_type=body.project_type,
                    idempotency_key=idempotency_key,
                ),
            )
        except ProjectIdempotencyConflict:
            raise IdempotencyConflictError from None
        except ProjectValidationError:
            raise ValidationFailedError from None
        return _response(project)

    @router.get("", response_model=ProjectsResponse)
    async def list_projects(
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ProjectApplicationService, Depends(_project_service)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> ProjectsResponse:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        rows = await service.list(
            context,
            limit=limit + 1,
            cursor_created_at=cursor_created_at,
            cursor_id=cursor_id,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = _encode_cursor(page[-1]) if has_more and page else None
        trace = current_trace_context()
        if trace is None or trace.request_id is None:
            raise RuntimeError("Project list requires an active request context")
        return ProjectsResponse(
            data=[_response(item) for item in page],
            meta=CollectionMeta(
                request_id=UUID(trace.request_id),
                next_cursor=next_cursor,
                has_more=has_more,
            ),
        )

    @router.get("/{project_id}", response_model=ProjectResponse)
    async def get_project(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ProjectApplicationService, Depends(_project_service)],
    ) -> ProjectResponse:
        try:
            return _response(await service.get(context, project_id))
        except ProjectNotFound:
            raise ResourceNotFoundError from None

    @router.patch("/{project_id}", response_model=ProjectResponse)
    async def update_project(
        project_id: UUID,
        body: UpdateProjectRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ProjectApplicationService, Depends(_project_service)],
    ) -> ProjectResponse:
        try:
            project = await service.update(
                context,
                project_id,
                UpdateProjectCommand(
                    title=body.title,
                    expected_updated_at=body.expected_updated_at,
                ),
            )
        except ProjectNotFound:
            raise ResourceNotFoundError from None
        except ProjectVersionConflict:
            raise VersionConflictError from None
        except (ProjectReadOnly, ProjectValidationError):
            raise ValidationFailedError from None
        return _response(project)

    @router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_project(
        project_id: UUID,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ProjectApplicationService, Depends(_project_service)],
    ) -> Response:
        try:
            await service.soft_delete(context, project_id)
        except ProjectPermissionDenied:
            raise ForbiddenError from None
        except ProjectNotFound:
            raise ResourceNotFoundError from None
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        account_id=project.account_id,
        owner_id=project.owner_id,
        title=project.title,
        project_type=project.project_type,
        status=project.status,
        current_context_version=project.current_context_version,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _encode_cursor(project: Project) -> str:
    raw = json.dumps(
        {"created_at": project.created_at.isoformat(), "id": str(project.id)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime | None, UUID | None]:
    if value is None:
        return None, None
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        created_at = datetime.fromisoformat(payload["created_at"])
        project_id = UUID(payload["id"])
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, project_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ValidationFailedError from None
