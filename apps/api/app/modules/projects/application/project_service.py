from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.projects.application.ports import (
    ProjectRepositoryError,
    ProjectUnitOfWorkFactory,
)
from app.modules.projects.domain.project import (
    NewProject,
    Project,
    ProjectStatus,
    ProjectType,
    ProjectValidationError,
    validate_project_status,
    validate_project_title,
    validate_project_type,
)


class ProjectNotFound(Exception):
    """The tenant-scoped active Project was not found."""


class ProjectReadOnly(Exception):
    """An archived Project cannot be mutated."""


class ProjectPermissionDenied(Exception):
    """The active Membership role does not allow the requested operation."""


@dataclass(frozen=True, slots=True)
class CreateProjectCommand:
    title: str
    project_type: ProjectType


@dataclass(frozen=True, slots=True)
class UpdateProjectCommand:
    title: str | None = None
    status: ProjectStatus | None = None


class ProjectApplicationService:
    def __init__(
        self,
        unit_of_work_factory: ProjectUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory

    async def create(
        self,
        context: TenantContext,
        command: CreateProjectCommand,
    ) -> Project:
        _require_active_context(context)
        title = validate_project_title(command.title)
        project_type = validate_project_type(command.project_type)
        project_id = self._id_factory()
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                project = NewProject(
                    id=project_id,
                    account_id=context.account_id,
                    owner_id=context.subject_id,
                    title=title,
                    project_type=project_type,
                    status="draft",
                    current_context_version=0,
                )
                persisted = await unit_of_work.repository.add(project)
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("create", started_at)
            raise
        self._event_logger.emit(
            "project.created",
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        return persisted

    async def update(
        self,
        context: TenantContext,
        project_id: UUID,
        command: UpdateProjectCommand,
    ) -> Project:
        _require_active_context(context)
        title = validate_project_title(command.title) if command.title is not None else None
        status = validate_project_status(command.status) if command.status is not None else None
        if title is None and status is None:
            raise ProjectValidationError("A Project update requires a documented mutable field")
        if status == "archived":
            _require_privileged_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                current = await unit_of_work.repository.get(
                    account_id=context.account_id,
                    project_id=project_id,
                )
                if current is None:
                    raise ProjectNotFound
                if current.is_read_only:
                    raise ProjectReadOnly
                persisted = await unit_of_work.repository.update(
                    account_id=context.account_id,
                    project_id=project_id,
                    title=title,
                    status=status,
                )
                if persisted is None:
                    raise ProjectNotFound
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("update", started_at)
            raise
        self._event_logger.emit(
            "project.updated",
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        return persisted

    async def archive(self, context: TenantContext, project_id: UUID) -> Project:
        _require_privileged_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.update(
                    account_id=context.account_id,
                    project_id=project_id,
                    status="archived",
                )
                if persisted is None:
                    raise ProjectNotFound
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("archive", started_at)
            raise
        self._event_logger.emit(
            "project.archived",
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        return persisted

    async def soft_delete(self, context: TenantContext, project_id: UUID) -> Project:
        _require_privileged_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.soft_delete(
                    account_id=context.account_id,
                    project_id=project_id,
                )
                if persisted is None:
                    raise ProjectNotFound
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("soft_delete", started_at)
            raise
        self._event_logger.emit(
            "project.soft_deleted",
            duration_ms=(perf_counter() - started_at) * 1000,
        )
        return persisted

    def _repository_failed(self, operation: str, started_at: float) -> None:
        self._event_logger.emit(
            "project.repository_failed",
            level="ERROR",
            component="project_repository",
            operation=operation,
            error_code="PROJECT_REPOSITORY_FAILURE",
            duration_ms=(perf_counter() - started_at) * 1000,
        )


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ProjectPermissionDenied


def _require_privileged_context(context: TenantContext) -> None:
    _require_active_context(context)
    if context.role not in {"owner", "admin"}:
        raise ProjectPermissionDenied
