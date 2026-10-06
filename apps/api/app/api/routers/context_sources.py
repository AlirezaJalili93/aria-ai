from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.api.dependencies.tenant_context import require_tenant_context
from app.modules.context.application.context_source_service import (
    CompleteContextSourceVersionCommand,
    ContextSourceApplicationService,
    CreateContextSourceCommand,
    CreateContextSourceVersionCommand,
)
from app.modules.context.infrastructure.models import ContextSourceModel
from app.modules.identity.application.tenant_context import TenantContext


class CreateContextSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    original_name: str | None = None


class ContextSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    project_id: UUID
    source_type: str
    status: str
    raw_text: str | None
    original_name: str | None
    created_at: datetime


class ContextSourcesListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[ContextSourceResponse]


def _context_source_service(request: Request) -> ContextSourceApplicationService:
    return cast(ContextSourceApplicationService, request.app.state.context_source_service)


def create_context_sources_router() -> APIRouter:
    router = APIRouter(prefix="/projects/{project_id}/context-sources", tags=["context-sources"])

    @router.post("", response_model=ContextSourceResponse, status_code=status.HTTP_201_CREATED)
    async def create_context_source(
        project_id: UUID,
        body: CreateContextSourceRequest,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
        service: Annotated[ContextSourceApplicationService, Depends(_context_source_service)],
    ) -> ContextSourceResponse:
        source = await service.create_source(
            context,
            CreateContextSourceCommand(
                project_id=project_id,
                source_type="text",
                raw_text=body.raw_text,
                original_name=body.original_name,
            ),
        )
        version = await service.create_version(
            context,
            CreateContextSourceVersionCommand(
                project_id=project_id,
                source_id=source.id,
                version_no=1,
            ),
        )
        await service.complete_version(
            context,
            CompleteContextSourceVersionCommand(
                project_id=project_id,
                source_id=source.id,
                version_id=version.id,
                content_hash=None,
                canonical_text=body.raw_text,
                storage_ref=None,
                metadata=None,
            ),
        )
        return ContextSourceResponse(
            id=source.id,
            project_id=source.project_id,
            source_type=source.source_type,
            status="ready",
            raw_text=source.raw_text,
            original_name=source.original_name,
            created_at=source.created_at,
        )

    @router.get("", response_model=ContextSourcesListResponse)
    async def list_context_sources(
        project_id: UUID,
        request: Request,
        context: Annotated[TenantContext, Depends(require_tenant_context)],
    ) -> ContextSourcesListResponse:
        session_factory = getattr(request.app.state, "session_factory", None)
        if session_factory is None:
            return ContextSourcesListResponse(data=[])
        async with session_factory() as session:
            models = (
                await session.scalars(
                    select(ContextSourceModel)
                    .where(
                        ContextSourceModel.account_id == context.account_id,
                        ContextSourceModel.project_id == project_id,
                        ContextSourceModel.status != "deleted",
                    )
                    .order_by(ContextSourceModel.created_at.desc())
                )
            ).all()
            data = [
                ContextSourceResponse(
                    id=m.id,
                    project_id=m.project_id,
                    source_type=m.source_type,
                    status=m.status,
                    raw_text=m.raw_text,
                    original_name=m.original_name,
                    created_at=m.created_at,
                )
                for m in models
            ]
        return ContextSourcesListResponse(data=data)

    return router
