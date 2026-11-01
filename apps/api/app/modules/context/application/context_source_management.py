from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from time import perf_counter
from types import TracebackType
from typing import Protocol
from uuid import UUID

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import JobStatus


class ContextSourceNotFound(Exception):
    """The Source is not visible in the current tenant and Project."""


class ContextSourceBusy(Exception):
    """A queued or running parser Job prevents logical archive."""


class ContextSourceManagementRepositoryError(Exception):
    """A declared Context Source management persistence failure."""


@dataclass(frozen=True, slots=True)
class ContextSourceVersionSummary:
    id: UUID
    version_no: int
    parse_status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContextSourceJobSummary:
    id: UUID
    status: JobStatus
    retryable: bool
    error_code: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ContextSourceView:
    id: UUID
    source_type: str
    status: str
    original_name: str | None
    mime_type: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    latest_version: ContextSourceVersionSummary | None
    current_ready_version: ContextSourceVersionSummary | None
    latest_job: ContextSourceJobSummary | None
    can_archive: bool = False


class ContextSourceManagementRepository(Protocol):
    async def project_exists(self, *, account_id: UUID, project_id: UUID) -> bool: ...

    async def list_sources(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[ContextSourceView, ...]: ...

    async def get_source(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        include_deleted: bool = False,
    ) -> ContextSourceView | None: ...

    async def has_active_parser_job(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> bool: ...

    async def archive_source(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> bool: ...


class ContextSourceManagementUnitOfWork(Protocol):
    @property
    def repository(self) -> ContextSourceManagementRepository: ...

    async def __aenter__(self) -> ContextSourceManagementUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ContextSourceManagementUnitOfWorkFactory(Protocol):
    def __call__(self) -> ContextSourceManagementUnitOfWork: ...


class ContextSourceManagementService:
    def __init__(
        self,
        unit_of_work_factory: ContextSourceManagementUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger

    async def list(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[ContextSourceView, ...]:
        _require_active(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        async with self._unit_of_work_factory() as unit_of_work:
            if not await unit_of_work.repository.project_exists(
                account_id=context.account_id, project_id=project_id
            ):
                raise ContextSourceNotFound
            sources = await unit_of_work.repository.list_sources(
                account_id=context.account_id,
                project_id=project_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_id=cursor_id,
            )
            return tuple(_with_permissions(source, context) for source in sources)

    async def get(
        self, context: TenantContext, *, project_id: UUID, source_id: UUID
    ) -> ContextSourceView:
        _require_active(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        async with self._unit_of_work_factory() as unit_of_work:
            source = await unit_of_work.repository.get_source(
                account_id=context.account_id,
                project_id=project_id,
                source_id=source_id,
            )
        if source is None:
            raise ContextSourceNotFound
        self._event_logger.emit(
            "context_source.viewed",
            actor_id=str(context.subject_id),
            source_id=str(source.id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return _with_permissions(source, context)

    async def archive(self, context: TenantContext, *, project_id: UUID, source_id: UUID) -> None:
        _require_active(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        async with self._unit_of_work_factory() as unit_of_work:
            source = await unit_of_work.repository.get_source(
                account_id=context.account_id,
                project_id=project_id,
                source_id=source_id,
                include_deleted=True,
            )
            if source is None or (
                context.role == "member" and source.created_by != context.subject_id
            ):
                raise ContextSourceNotFound
            if source.status == "deleted":
                return
            if await unit_of_work.repository.has_active_parser_job(
                account_id=context.account_id,
                project_id=project_id,
                source_id=source_id,
            ):
                self._event_logger.emit(
                    "context_source.archive_blocked",
                    level="WARNING",
                    actor_id=str(context.subject_id),
                    source_id=str(source_id),
                    role=context.role,
                    error_code="CONTEXT_SOURCE_BUSY",
                    status="rejected",
                )
                raise ContextSourceBusy
            archived = await unit_of_work.repository.archive_source(
                account_id=context.account_id,
                project_id=project_id,
                source_id=source_id,
            )
            if not archived:
                raise ContextSourceNotFound
            await unit_of_work.commit()
        self._event_logger.emit(
            "context_source.archived",
            actor_id=str(context.subject_id),
            source_id=str(source_id),
            role=context.role,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )


def parser_job_retryable(*, status: str, error_code: str | None) -> bool:
    return status == "failed" and error_code == "PARSER_STORAGE_UNAVAILABLE"


def _with_permissions(source: ContextSourceView, context: TenantContext) -> ContextSourceView:
    return replace(
        source,
        can_archive=context.role in ("owner", "admin") or source.created_by == context.subject_id,
    )


def _require_active(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ContextSourceNotFound
