from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.projects.application.ports import ProjectRepositoryError, ProjectUnitOfWorkFactory
from app.modules.projects.domain.project import (
    NewProject,
    Project,
    ProjectType,
    ProjectValidationError,
    validate_project_title,
    validate_project_type,
)


class ProjectNotFound(Exception):
    """The tenant-scoped active Project was not found."""


class ProjectReadOnly(Exception):
    """An archived Project cannot be mutated."""


class ProjectPermissionDenied(Exception):
    """The active Membership role does not allow the requested operation."""


class ProjectIdempotencyConflict(Exception):
    """An idempotency key was reused with a different normalized request."""


class ProjectVersionConflict(Exception):
    """The Project changed after the caller's expected version timestamp."""


@dataclass(frozen=True, slots=True)
class CreateProjectCommand:
    title: str
    project_type: ProjectType
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class UpdateProjectCommand:
    title: str
    expected_updated_at: datetime


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

    async def create(self, context: TenantContext, command: CreateProjectCommand) -> Project:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        title = validate_project_title(command.title)
        project_type = validate_project_type(command.project_type)
        if not command.idempotency_key.strip():
            raise ProjectValidationError("Idempotency-Key must not be empty")
        payload_hash = _create_payload_hash(title, project_type)
        project_id = self._id_factory()
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.repository.reserve_create(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    idempotency_key=command.idempotency_key,
                    payload_hash=payload_hash,
                    project_id=project_id,
                )
                if not reservation.acquired:
                    if reservation.payload_hash != payload_hash:
                        raise ProjectIdempotencyConflict
                    if reservation.response_snapshot is None:
                        raise ProjectRepositoryError
                    return reservation.response_snapshot

                project = NewProject(
                    id=reservation.project_id,
                    account_id=context.account_id,
                    owner_id=context.subject_id,
                    title=title,
                    project_type=project_type,
                    status="draft",
                    current_context_version=0,
                )
                persisted = await unit_of_work.repository.add(project)
                await unit_of_work.repository.complete_create_reservation(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    idempotency_key=command.idempotency_key,
                    project=persisted,
                )
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("create", context, started_at)
            raise
        enrich_trace_context(project_id=str(persisted.id))
        self._event_logger.emit(
            "project.created",
            actor_id=str(context.subject_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def get(self, context: TenantContext, project_id: UUID) -> Project:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                project = await unit_of_work.repository.get(
                    account_id=context.account_id,
                    project_id=project_id,
                )
        except ProjectRepositoryError:
            self._repository_failed("get", context, started_at)
            raise
        if project is None:
            self._access_denied(context, project_id, started_at)
            raise ProjectNotFound
        enrich_trace_context(project_id=str(project.id))
        return project

    async def list(
        self,
        context: TenantContext,
        *,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Project, ...]:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                return await unit_of_work.repository.list_by_account(
                    account_id=context.account_id,
                    limit=limit,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                )
        except ProjectRepositoryError:
            self._repository_failed("list", context, started_at)
            raise

    async def update(
        self,
        context: TenantContext,
        project_id: UUID,
        command: UpdateProjectCommand,
    ) -> Project:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        title = validate_project_title(command.title)
        if command.expected_updated_at.tzinfo is None:
            raise ProjectValidationError("expected_updated_at must include a timezone")
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                current = await unit_of_work.repository.get(
                    account_id=context.account_id,
                    project_id=project_id,
                )
                if current is None:
                    self._access_denied(context, project_id, started_at)
                    raise ProjectNotFound
                if current.is_read_only:
                    raise ProjectReadOnly
                if current.updated_at != command.expected_updated_at:
                    raise ProjectVersionConflict
                persisted = await unit_of_work.repository.update(
                    account_id=context.account_id,
                    project_id=project_id,
                    title=title,
                    expected_updated_at=command.expected_updated_at,
                )
                if persisted is None:
                    raise ProjectVersionConflict
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("update", context, started_at)
            raise
        enrich_trace_context(project_id=str(persisted.id))
        self._event_logger.emit(
            "project.updated",
            actor_id=str(context.subject_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def archive(self, context: TenantContext, project_id: UUID) -> Project:
        _require_privileged_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.update(
                    account_id=context.account_id,
                    project_id=project_id,
                    status="archived",
                )
                if persisted is None:
                    self._access_denied(context, project_id, started_at)
                    raise ProjectNotFound
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("archive", context, started_at)
            raise
        enrich_trace_context(project_id=str(persisted.id))
        self._event_logger.emit(
            "project.archived",
            actor_id=str(context.subject_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def soft_delete(self, context: TenantContext, project_id: UUID) -> Project:
        _require_privileged_context(context)
        enrich_trace_context(account_id=str(context.account_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.soft_delete(
                    account_id=context.account_id,
                    project_id=project_id,
                )
                if persisted is None:
                    self._access_denied(context, project_id, started_at)
                    raise ProjectNotFound
                await unit_of_work.commit()
        except ProjectRepositoryError:
            self._repository_failed("soft_delete", context, started_at)
            raise
        enrich_trace_context(project_id=str(persisted.id))
        self._event_logger.emit(
            "project.soft_deleted",
            actor_id=str(context.subject_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    def _repository_failed(
        self, operation: str, context: TenantContext, started_at: float
    ) -> None:
        self._event_logger.emit(
            "project.repository_failed",
            level="ERROR",
            actor_id=str(context.subject_id),
            component="project_repository",
            operation=operation,
            error_code="PROJECT_REPOSITORY_FAILURE",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="failed",
        )

    def _access_denied(
        self, context: TenantContext, project_id: UUID, started_at: float
    ) -> None:
        self._event_logger.emit(
            "security.project_access_denied",
            level="WARNING",
            actor_id=str(context.subject_id),
            project_id=str(project_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="denied",
            error_code="RESOURCE_NOT_FOUND",
        )


def _create_payload_hash(title: str, project_type: ProjectType) -> str:
    payload = json.dumps(
        {"project_type": project_type, "title": title},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ProjectPermissionDenied


def _require_privileged_context(context: TenantContext) -> None:
    _require_active_context(context)
    if context.role not in {"owner", "admin"}:
        raise ProjectPermissionDenied
