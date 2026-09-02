from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.context.application.ports import (
    ContextSourceRepository,
    ContextSourceRepositoryError,
    ContextSourceUnitOfWorkFactory,
)
from app.modules.context.domain.context_source import (
    ContextSource,
    ContextSourceType,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
    validate_ready_content,
    validate_source_type,
    validate_version_number,
)
from app.modules.identity.application.tenant_context import TenantContext

APPLICATION_SOURCE_TYPES = frozenset({"text"})


class ContextSourceNotFound(Exception):
    """The tenant-scoped active Context Source or Version was not found."""


class ContextSourcePermissionDenied(Exception):
    """An inactive Membership cannot use Context Application services."""


class ContextSourceTypeUnavailable(Exception):
    """The schema-known Source type is not enabled in this increment."""


@dataclass(frozen=True, slots=True)
class CreateContextSourceCommand:
    project_id: UUID
    source_type: ContextSourceType
    original_name: str | None = None
    mime_type: str | None = None
    storage_ref: str | None = None
    raw_text: str | None = None
    checksum: str | None = None


@dataclass(frozen=True, slots=True)
class CreateContextSourceVersionCommand:
    project_id: UUID
    source_id: UUID
    version_no: int


@dataclass(frozen=True, slots=True)
class CompleteContextSourceVersionCommand:
    project_id: UUID
    source_id: UUID
    version_id: UUID
    content_hash: str | None
    canonical_text: str | None
    storage_ref: str | None
    metadata: dict[str, object] | None


class ContextSourceApplicationService:
    def __init__(
        self,
        unit_of_work_factory: ContextSourceUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory

    async def create_source(
        self, context: TenantContext, command: CreateContextSourceCommand
    ) -> ContextSource:
        _require_active_context(context)
        source_type = validate_source_type(command.source_type)
        if source_type not in APPLICATION_SOURCE_TYPES:
            raise ContextSourceTypeUnavailable
        enrich_trace_context(account_id=str(context.account_id), project_id=str(command.project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.add_source(
                    NewContextSource(
                        id=self._id_factory(),
                        account_id=context.account_id,
                        project_id=command.project_id,
                        source_type=source_type,
                        status="uploaded",
                        original_name=command.original_name,
                        mime_type=command.mime_type,
                        storage_ref=command.storage_ref,
                        raw_text=command.raw_text,
                        checksum=command.checksum,
                        created_by=context.subject_id,
                    )
                )
                await unit_of_work.commit()
        except ContextSourceRepositoryError:
            self._repository_failed("create_source", context, started_at)
            raise
        self._event_logger.emit(
            "context_source.created",
            actor_id=str(context.subject_id),
            source_id=str(persisted.id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status=persisted.status,
        )
        return persisted

    async def create_version(
        self, context: TenantContext, command: CreateContextSourceVersionCommand
    ) -> ContextSourceVersion:
        _require_active_context(context)
        validate_version_number(command.version_no)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(command.project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await self._require_source(
                    unit_of_work.repository,
                    context=context,
                    project_id=command.project_id,
                    source_id=command.source_id,
                )
                persisted = await unit_of_work.repository.add_version(
                    NewContextSourceVersion(
                        id=self._id_factory(),
                        account_id=context.account_id,
                        project_id=command.project_id,
                        source_id=command.source_id,
                        version_no=command.version_no,
                        content_hash=None,
                        canonical_text=None,
                        storage_ref=None,
                        metadata=None,
                        parse_status="pending",
                    )
                )
                await unit_of_work.commit()
        except ContextSourceRepositoryError:
            self._repository_failed("create_version", context, started_at, command.source_id)
            raise
        self._emit_version_event("created", context, persisted, started_at)
        return persisted

    async def complete_version(
        self, context: TenantContext, command: CompleteContextSourceVersionCommand
    ) -> ContextSourceVersion:
        _require_active_context(context)
        validate_ready_content(command.canonical_text, command.storage_ref)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(command.project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await self._require_source(
                    unit_of_work.repository,
                    context=context,
                    project_id=command.project_id,
                    source_id=command.source_id,
                )
                persisted = await unit_of_work.repository.mark_version_ready(
                    account_id=context.account_id,
                    project_id=command.project_id,
                    source_id=command.source_id,
                    version_id=command.version_id,
                    content_hash=command.content_hash,
                    canonical_text=command.canonical_text,
                    storage_ref=command.storage_ref,
                    metadata=command.metadata,
                )
                if persisted is None:
                    raise ContextSourceNotFound
                source = await unit_of_work.repository.set_source_status(
                    account_id=context.account_id,
                    project_id=command.project_id,
                    source_id=command.source_id,
                    status="ready",
                )
                if source is None:
                    raise ContextSourceNotFound
                await unit_of_work.commit()
        except ContextSourceRepositoryError:
            self._repository_failed("complete_version", context, started_at, command.source_id)
            raise
        self._emit_version_event("ready", context, persisted, started_at)
        return persisted

    async def fail_version(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
    ) -> ContextSourceVersion:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await self._require_source(
                    unit_of_work.repository,
                    context=context,
                    project_id=project_id,
                    source_id=source_id,
                )
                persisted = await unit_of_work.repository.mark_version_failed(
                    account_id=context.account_id,
                    project_id=project_id,
                    source_id=source_id,
                    version_id=version_id,
                )
                if persisted is None:
                    raise ContextSourceNotFound
                source = await unit_of_work.repository.set_source_status(
                    account_id=context.account_id,
                    project_id=project_id,
                    source_id=source_id,
                    status="failed",
                )
                if source is None:
                    raise ContextSourceNotFound
                await unit_of_work.commit()
        except ContextSourceRepositoryError:
            self._repository_failed("fail_version", context, started_at, source_id)
            raise
        self._emit_version_event("failed", context, persisted, started_at)
        return persisted

    async def mark_source_deleted(
        self, context: TenantContext, *, project_id: UUID, source_id: UUID
    ) -> ContextSource:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                persisted = await unit_of_work.repository.set_source_status(
                    account_id=context.account_id,
                    project_id=project_id,
                    source_id=source_id,
                    status="deleted",
                )
                if persisted is None:
                    raise ContextSourceNotFound
                await unit_of_work.commit()
        except ContextSourceRepositoryError:
            self._repository_failed("mark_source_deleted", context, started_at, source_id)
            raise
        self._event_logger.emit(
            "context_source.deleted",
            actor_id=str(context.subject_id),
            source_id=str(source_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status=persisted.status,
        )
        return persisted

    async def get_current_version(
        self, context: TenantContext, *, project_id: UUID, source_id: UUID
    ) -> ContextSourceVersion | None:
        _require_active_context(context)
        enrich_trace_context(account_id=str(context.account_id), project_id=str(project_id))
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await self._require_source(
                    unit_of_work.repository,
                    context=context,
                    project_id=project_id,
                    source_id=source_id,
                )
                return await unit_of_work.repository.get_current_ready_version(
                    account_id=context.account_id,
                    project_id=project_id,
                    source_id=source_id,
                )
        except ContextSourceRepositoryError:
            self._repository_failed("get_current_version", context, started_at, source_id)
            raise

    async def _require_source(
        self,
        repository: ContextSourceRepository,
        *,
        context: TenantContext,
        project_id: UUID,
        source_id: UUID,
    ) -> ContextSource:
        source = await repository.get_source(
            account_id=context.account_id, project_id=project_id, source_id=source_id
        )
        if source is None:
            raise ContextSourceNotFound
        return source

    def _emit_version_event(
        self,
        outcome: str,
        context: TenantContext,
        version: ContextSourceVersion,
        started_at: float,
    ) -> None:
        self._event_logger.emit(
            f"context_source_version.{outcome}",
            actor_id=str(context.subject_id),
            source_id=str(version.source_id),
            version_no=version.version_no,
            duration_ms=(perf_counter() - started_at) * 1000,
            status=version.parse_status,
        )

    def _repository_failed(
        self,
        operation: str,
        context: TenantContext,
        started_at: float,
        source_id: UUID | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "actor_id": str(context.subject_id),
            "component": "context_source_repository",
            "operation": operation,
            "error_code": "CONTEXT_SOURCE_REPOSITORY_FAILURE",
            "duration_ms": (perf_counter() - started_at) * 1000,
            "status": "failed",
        }
        if source_id is not None:
            fields["source_id"] = str(source_id)
        self._event_logger.emit("context_source.repository_failed", level="ERROR", **fields)


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise ContextSourcePermissionDenied
