from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Literal
from uuid import UUID

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.context.application.context_item_ports import (
    ContextItemRepository,
    ContextItemRepositoryError,
    ContextItemUnitOfWorkFactory,
    CurrentContextItems,
)
from app.modules.context.domain.context_item import (
    ContextItem,
    ContextItemStatus,
    ContextItemType,
    ContextItemValidationError,
    NewContextItem,
    SourceReference,
)
from app.modules.identity.application.tenant_context import TenantContext


class ContextItemProvenanceError(ValueError):
    """A Source Reference did not resolve to valid same-tenant ready provenance."""


class ContextItemNotFound(Exception):
    """The tenant-scoped current Context Item was not found."""


class ContextItemVersionConflict(Exception):
    """The Context Item changed after the caller read it."""


class ContextItemInvalidState(Exception):
    """The Context Item is not proposed and is immutable in H04."""


class ContextItemPermissionDenied(Exception):
    """The caller does not have an active Membership."""


ContextReviewCommand = Literal["confirm", "reject", "edit"]


@dataclass(frozen=True, slots=True)
class ReviewContextItemCommand:
    command: ContextReviewCommand
    expected_updated_at: datetime
    content: str | None = None


class CreateContextItemUseCase:
    def __init__(self, unit_of_work_factory: ContextItemUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self, item: NewContextItem) -> ContextItem:
        async with self._unit_of_work_factory() as unit_of_work:
            for source_ref in item.source_refs:
                await self._validate_reference(unit_of_work.repository, item, source_ref)
            persisted = await unit_of_work.repository.add(item)
            await unit_of_work.commit()
            return persisted

    @staticmethod
    async def _validate_reference(
        repository: ContextItemRepository,
        item: NewContextItem,
        source_ref: SourceReference,
    ) -> None:
        target = await repository.resolve_provenance(
            account_id=item.account_id,
            project_id=item.project_id,
            source_id=source_ref.source_id,
            source_version_id=source_ref.source_version_id,
        )
        if (
            target is None
            or target.account_id != item.account_id
            or target.project_id != item.project_id
            or target.source_id != source_ref.source_id
            or target.source_version_id != source_ref.source_version_id
        ):
            raise ContextItemProvenanceError("Source Reference is not valid ready provenance")
        if source_ref.end_offset is not None and (
            target.canonical_text_length is None
            or source_ref.end_offset > target.canonical_text_length
        ):
            raise ContextItemProvenanceError("Source Reference offsets exceed canonical text")


class ContextItemReviewService:
    def __init__(
        self,
        unit_of_work_factory: ContextItemUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger

    async def list_current(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        item_type: ContextItemType | None,
        status: ContextItemStatus | None,
        source_id: UUID | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> CurrentContextItems:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                result = await unit_of_work.repository.list_current(
                    account_id=context.account_id,
                    project_id=project_id,
                    item_type=item_type,
                    status=status,
                    source_id=source_id,
                    limit=limit,
                    cursor_created_at=cursor_created_at,
                    cursor_id=cursor_id,
                )
        except ContextItemRepositoryError:
            self._repository_failed("list", context)
            raise
        if result is None:
            self._access_denied(context, project_id)
            raise ContextItemNotFound
        return result

    async def review(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        item_id: UUID,
        command: ReviewContextItemCommand,
    ) -> ContextItem:
        _require_active_context(context)
        if command.expected_updated_at.tzinfo is None:
            raise ContextItemValidationError("expected_updated_at must include a timezone")
        if command.command == "edit" and command.content is None:
            raise ContextItemValidationError("edit requires content")
        if command.command != "edit" and command.content is not None:
            raise ContextItemValidationError("content is only valid for edit")

        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                current = await unit_of_work.repository.get_current_for_update(
                    account_id=context.account_id,
                    project_id=project_id,
                    item_id=item_id,
                )
                if current is None:
                    self._access_denied(context, project_id)
                    raise ContextItemNotFound
                if current.status != "proposed":
                    raise ContextItemInvalidState
                if current.updated_at != command.expected_updated_at:
                    self._version_conflict(context, current)
                    raise ContextItemVersionConflict

                content = command.content if command.command == "edit" else current.content
                assert content is not None
                status_by_command: dict[
                    ContextReviewCommand, Literal["proposed", "confirmed", "rejected"]
                ] = {
                    "confirm": "confirmed",
                    "reject": "rejected",
                    "edit": "proposed",
                }
                next_status = status_by_command[command.command]
                persisted = await unit_of_work.repository.update_proposed(
                    account_id=context.account_id,
                    project_id=project_id,
                    item_id=item_id,
                    expected_updated_at=command.expected_updated_at,
                    content=content,
                    status=next_status,
                )
                if persisted is None:
                    self._version_conflict(context, current)
                    raise ContextItemVersionConflict
                await unit_of_work.commit()
        except ContextItemRepositoryError:
            self._repository_failed("review", context)
            raise

        event_name = {
            "confirm": "context_item.confirmed",
            "reject": "context_item.rejected",
            "edit": "context_item.edited",
        }[command.command]
        self._event_logger.emit(
            event_name,
            actor_id=str(context.subject_id),
            context_item_id=str(persisted.id),
            context_version=persisted.context_version,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    def _version_conflict(self, context: TenantContext, item: ContextItem) -> None:
        self._event_logger.emit(
            "context_item.version_conflict",
            level="WARNING",
            actor_id=str(context.subject_id),
            context_item_id=str(item.id),
            context_version=item.context_version,
            status="conflict",
            error_code="VERSION_CONFLICT",
        )

    def _access_denied(self, context: TenantContext, project_id: UUID) -> None:
        self._event_logger.emit(
            "security.context_item_access_denied",
            level="WARNING",
            actor_id=str(context.subject_id),
            project_id=str(project_id),
            status="denied",
            error_code="RESOURCE_NOT_FOUND",
        )

    def _repository_failed(self, operation: str, context: TenantContext) -> None:
        self._event_logger.emit(
            "context_item.repository_failed",
            level="ERROR",
            actor_id=str(context.subject_id),
            component="context_item_repository",
            operation=operation,
            status="failed",
            error_code="CONTEXT_ITEM_REPOSITORY_FAILURE",
        )


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ContextItemPermissionDenied
