from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.requirements.application.requirement_crud_ports import (
    RequirementCrudRepositoryError,
    RequirementCrudUnitOfWork,
    RequirementCrudUnitOfWorkFactory,
)
from app.modules.requirements.domain.requirement import (
    NewRequirement,
    Requirement,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
)

REQUIREMENT_CREATE_ROUTE_KEY = "POST /api/v1/projects/{project_id}/requirements"
REQUIREMENT_CREATE_IDEMPOTENCY_TTL = timedelta(hours=24)


class RequirementNotFound(Exception):
    """The tenant-scoped Project or Requirement was not found."""


class RequirementPermissionDenied(Exception):
    """The caller does not have an active Membership."""


class RequirementContextRequired(Exception):
    """The Project has no valid Context Version for a manual Requirement."""


class RequirementIdempotencyConflict(Exception):
    """The idempotency key was reused with a different request."""


class RequirementVersionConflict(Exception):
    """The Requirement changed after the caller read it."""


class RequirementInvalidState(Exception):
    """The requested lifecycle operation is not valid for the current status."""


@dataclass(frozen=True, slots=True)
class CreateManualRequirementCommand:
    title: str
    description: str
    category: RequirementCategory
    priority: RequirementPriority
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class UpdateRequirementCommand:
    expected_updated_at: datetime
    title: str | None = None
    description: str | None = None
    priority: RequirementPriority | None = None
    acceptance_note: str | None = None
    acceptance_note_set: bool = False
    status: Literal["confirmed"] | None = None

    @property
    def changes_content(self) -> bool:
        return any(
            (
                self.title is not None,
                self.description is not None,
                self.priority is not None,
                self.acceptance_note_set,
            )
        )


class RequirementCrudService:
    def __init__(
        self,
        unit_of_work_factory: RequirementCrudUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def create_manual(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        command: CreateManualRequirementCommand,
    ) -> Requirement:
        _require_active_context(context)
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        request_hash = _create_request_hash(project_id, command)
        now = self._clock()
        requirement_id = self._id_factory()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=self._id_factory(),
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=REQUIREMENT_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + REQUIREMENT_CREATE_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise RequirementIdempotencyConflict
                    return await self._replay_create(
                        unit_of_work,
                        context=context,
                        project_id=project_id,
                        response_status=reservation.response_status,
                        response_ref=reservation.response_ref,
                    )

                current_context_version = (
                    await unit_of_work.repository.get_project_current_context_version(
                        account_id=context.account_id,
                        project_id=project_id,
                    )
                )
                if current_context_version is None:
                    self._access_denied(context, project_id)
                    raise RequirementNotFound
                if current_context_version < 1:
                    raise RequirementContextRequired

                persisted = await unit_of_work.repository.add(
                    NewRequirement(
                        id=requirement_id,
                        account_id=context.account_id,
                        project_id=project_id,
                        context_version=current_context_version,
                        category=command.category,
                        title=command.title,
                        description=command.description,
                        priority=command.priority,
                        source_refs=(),
                        confidence=None,
                        is_unsupported=False,
                        created_by_type="user",
                        created_by=context.subject_id,
                        status="draft",
                    )
                )
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=REQUIREMENT_CREATE_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=201,
                    response_ref={"requirement_id": str(persisted.id)},
                )
                await unit_of_work.commit()
        except RequirementCrudRepositoryError:
            self._repository_failed("create", context, started_at)
            raise

        self._event_logger.emit(
            "requirement.added",
            actor_id=str(context.subject_id),
            requirement_id=str(persisted.id),
            context_version=persisted.context_version,
            priority=persisted.priority,
            created_by_type=persisted.created_by_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    async def list(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        category: RequirementCategory | None,
        status: RequirementStatus | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Requirement, ...]:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                rows = await unit_of_work.repository.list_by_project(
                    account_id=context.account_id,
                    project_id=project_id,
                    category=category,
                    status=status,
                    limit=limit,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                )
        except RequirementCrudRepositoryError:
            self._repository_failed("list", context, started_at)
            raise
        if rows is None:
            self._access_denied(context, project_id)
            raise RequirementNotFound
        return rows

    async def update(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        requirement_id: UUID,
        command: UpdateRequirementCommand,
    ) -> Requirement:
        _require_active_context(context)
        if command.expected_updated_at.tzinfo is None:
            raise ValueError("expected_updated_at must include a timezone")
        if not command.changes_content and command.status is None:
            raise ValueError("At least one Requirement field must be updated")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                current = await unit_of_work.repository.get_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    requirement_id=requirement_id,
                )
                if current is None:
                    self._access_denied(context, project_id, requirement_id)
                    raise RequirementNotFound
                if current.status in {"removed", "superseded"}:
                    raise RequirementInvalidState
                if current.updated_at != command.expected_updated_at:
                    self._version_conflict(context, current)
                    raise RequirementVersionConflict
                if command.status == "confirmed" and current.status != "draft":
                    raise RequirementInvalidState

                next_status: RequirementStatus = current.status
                if current.status == "confirmed" and command.changes_content:
                    next_status = "draft"
                if command.status == "confirmed":
                    next_status = "confirmed"

                persisted = await unit_of_work.repository.update_mutable(
                    account_id=context.account_id,
                    project_id=project_id,
                    requirement_id=requirement_id,
                    expected_updated_at=command.expected_updated_at,
                    title=command.title if command.title is not None else current.title,
                    description=(
                        command.description
                        if command.description is not None
                        else current.description
                    ),
                    priority=(
                        command.priority if command.priority is not None else current.priority
                    ),
                    acceptance_note=(
                        command.acceptance_note
                        if command.acceptance_note_set
                        else current.acceptance_note
                    ),
                    status=next_status,
                )
                if persisted is None:
                    self._version_conflict(context, current)
                    raise RequirementVersionConflict
                await unit_of_work.commit()
        except RequirementCrudRepositoryError:
            self._repository_failed("update", context, started_at)
            raise

        event_name = (
            "requirement.confirmed"
            if persisted.status == "confirmed" and current.status == "draft"
            else "requirement.edited"
        )
        self._event_logger.emit(
            event_name,
            actor_id=str(context.subject_id),
            requirement_id=str(persisted.id),
            context_version=persisted.context_version,
            priority=persisted.priority,
            duration_ms=(perf_counter() - started_at) * 1000,
            status=persisted.status,
        )
        return persisted

    async def remove_draft(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        requirement_id: UUID,
    ) -> None:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                current = await unit_of_work.repository.get_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    requirement_id=requirement_id,
                )
                if current is None:
                    self._access_denied(context, project_id, requirement_id)
                    raise RequirementNotFound
                if current.status != "draft":
                    raise RequirementInvalidState
                persisted = await unit_of_work.repository.update_mutable(
                    account_id=context.account_id,
                    project_id=project_id,
                    requirement_id=requirement_id,
                    expected_updated_at=current.updated_at,
                    title=current.title,
                    description=current.description,
                    priority=current.priority,
                    acceptance_note=current.acceptance_note,
                    status="removed",
                )
                if persisted is None:
                    self._version_conflict(context, current)
                    raise RequirementVersionConflict
                await unit_of_work.commit()
        except RequirementCrudRepositoryError:
            self._repository_failed("remove", context, started_at)
            raise

        self._event_logger.emit(
            "requirement.removed",
            actor_id=str(context.subject_id),
            requirement_id=str(requirement_id),
            context_version=persisted.context_version,
            priority=persisted.priority,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="removed",
        )

    async def _replay_create(
        self,
        unit_of_work: RequirementCrudUnitOfWork,
        *,
        context: TenantContext,
        project_id: UUID,
        response_status: int | None,
        response_ref: dict[str, object] | None,
    ) -> Requirement:
        try:
            if response_status != 201 or response_ref is None:
                raise ValueError
            requirement_id = UUID(str(response_ref["requirement_id"]))
        except (KeyError, TypeError, ValueError):
            raise RequirementCrudRepositoryError from None
        existing = await unit_of_work.repository.get_by_id(
            account_id=context.account_id,
            project_id=project_id,
            requirement_id=requirement_id,
        )
        if existing is None:
            raise RequirementCrudRepositoryError
        self._event_logger.emit(
            "requirement.create_replayed",
            actor_id=str(context.subject_id),
            requirement_id=str(existing.id),
            context_version=existing.context_version,
            status=existing.status,
        )
        return existing

    def _version_conflict(self, context: TenantContext, requirement: Requirement) -> None:
        self._event_logger.emit(
            "requirement.version_conflict",
            level="WARNING",
            actor_id=str(context.subject_id),
            requirement_id=str(requirement.id),
            context_version=requirement.context_version,
            status="conflict",
            error_code="VERSION_CONFLICT",
        )

    def _access_denied(
        self,
        context: TenantContext,
        project_id: UUID,
        requirement_id: UUID | None = None,
    ) -> None:
        del requirement_id
        self._event_logger.emit(
            "security.requirement_access_denied",
            level="WARNING",
            actor_id=str(context.subject_id),
            project_id=str(project_id),
            status="denied",
            error_code="RESOURCE_NOT_FOUND",
        )

    def _repository_failed(
        self, operation: str, context: TenantContext, started_at: float
    ) -> None:
        self._event_logger.emit(
            "requirement.repository_failed",
            level="ERROR",
            actor_id=str(context.subject_id),
            component="requirement_repository",
            operation=operation,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="failed",
            error_code="REQUIREMENT_REPOSITORY_FAILURE",
        )


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise RequirementPermissionDenied


def _create_request_hash(
    project_id: UUID, command: CreateManualRequirementCommand
) -> str:
    canonical_request = json.dumps(
        {
            "project_id": str(project_id),
            "title": command.title,
            "description": command.description,
            "category": command.category,
            "priority": command.priority,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical_request.encode("utf-8")).hexdigest()
