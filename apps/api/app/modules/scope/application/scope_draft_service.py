from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.ports import (
    ScopeDraftHistorical,
    ScopeDraftNotFound,
    ScopeDraftRepositoryError,
    ScopeDraftUnitOfWorkFactory,
    ScopeDraftVersionConflict,
)
from app.modules.scope.domain.scope_draft import (
    ScopeDraft,
    ScopeDraftValidationError,
    replace_scope_section_value,
)


class ScopeDraftAccessNotFound(Exception):
    """The current tenant-scoped Draft is unavailable."""


class ScopeDraftPermissionDenied(Exception):
    """The caller lacks an active Membership."""


class ScopeDraftStale(Exception):
    """The editable Draft belongs to a historical Context Version."""


class ScopeDraftEditConflict(Exception):
    """The Draft changed after the caller read it."""


@dataclass(frozen=True, slots=True)
class UpdateScopeSectionCommand:
    value: object
    expected_updated_at: datetime


class ScopeDraftService:
    def __init__(
        self,
        unit_of_work_factory: ScopeDraftUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory

    async def get_current(self, context: TenantContext, *, project_id: UUID) -> ScopeDraft:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                draft = await unit_of_work.repository.get_current(
                    account_id=context.account_id, project_id=project_id
                )
        except ScopeDraftRepositoryError:
            self._persistence_failed(context, "get_current", None, started_at)
            raise
        if draft is None:
            raise ScopeDraftAccessNotFound
        return draft

    async def update_section(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        section_id: str,
        command: UpdateScopeSectionCommand,
    ) -> ScopeDraft:
        _require_active_context(context)
        if command.expected_updated_at.tzinfo is None:
            raise ScopeDraftValidationError("expected_updated_at must include a timezone")
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        draft_id: UUID | None = None
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                target = await unit_of_work.repository.get_edit_target(
                    account_id=context.account_id, project_id=project_id
                )
                if target is None or target.draft is None:
                    raise ScopeDraftAccessNotFound
                current = target.draft
                draft_id = current.id
                if current.context_version != target.project_current_context_version:
                    self._event_logger.emit(
                        "scope_draft.stale_rejected",
                        level="WARNING",
                        actor_id=str(context.subject_id),
                        draft_id=str(current.id),
                        section_id=section_id,
                        context_version=current.context_version,
                        status="rejected",
                        error_code="SCOPE_DRAFT_STALE",
                    )
                    raise ScopeDraftStale
                if current.updated_at != command.expected_updated_at:
                    self._version_conflict(context, current, section_id)
                    raise ScopeDraftEditConflict
                content = replace_scope_section_value(
                    current.content,
                    section_id=section_id,
                    value=command.value,
                    id_factory=self._id_factory,
                )
                try:
                    persisted = await unit_of_work.repository.update(
                        account_id=context.account_id,
                        project_id=project_id,
                        draft_id=current.id,
                        expected_updated_at=command.expected_updated_at,
                        content=content,
                        updated_by_type="user",
                        updated_by=context.subject_id,
                    )
                except ScopeDraftHistorical:
                    raise ScopeDraftStale from None
                except ScopeDraftVersionConflict:
                    self._version_conflict(context, current, section_id)
                    raise ScopeDraftEditConflict from None
                except ScopeDraftNotFound:
                    raise ScopeDraftAccessNotFound from None
                await unit_of_work.commit()
        except ScopeDraftRepositoryError:
            self._persistence_failed(context, "update_section", draft_id, started_at)
            raise
        self._event_logger.emit(
            "scope_draft.section_updated",
            actor_id=str(context.subject_id),
            draft_id=str(persisted.id),
            section_id=section_id,
            context_version=persisted.context_version,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    def _version_conflict(self, context: TenantContext, draft: ScopeDraft, section_id: str) -> None:
        self._event_logger.emit(
            "scope_draft.version_conflict",
            level="WARNING",
            actor_id=str(context.subject_id),
            draft_id=str(draft.id),
            section_id=section_id,
            context_version=draft.context_version,
            status="conflict",
            error_code="VERSION_CONFLICT",
        )

    def _persistence_failed(
        self,
        context: TenantContext,
        operation: str,
        draft_id: UUID | None,
        started_at: float,
    ) -> None:
        fields: dict[str, object] = {
            "actor_id": str(context.subject_id),
            "component": "scope_draft_repository",
            "operation": operation,
            "duration_ms": (perf_counter() - started_at) * 1000,
            "status": "failed",
            "error_code": "SCOPE_DRAFT_PERSISTENCE_FAILURE",
        }
        if draft_id is not None:
            fields["draft_id"] = str(draft_id)
        self._event_logger.emit("scope_draft.persistence_failed", level="ERROR", **fields)


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ScopeDraftPermissionDenied
