from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from typing import cast
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionRepositoryError,
    TextContextIngestionUnitOfWorkFactory,
)
from app.modules.context.domain.context_source import (
    ContextSourceStatus,
    NewContextSource,
    NewContextSourceVersion,
    text_context_checksum,
    validate_text_context,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

TEXT_CONTEXT_ROUTE_KEY = "POST /api/v1/projects/{project_id}/context-sources"
TEXT_CONTEXT_JOB_TYPE = "context_source_parse"
TEXT_CONTEXT_IDEMPOTENCY_TTL = timedelta(hours=24)
TEXT_CONTEXT_JOB_MAX_ATTEMPTS = 3


class TextContextNotFound(Exception):
    """The tenant-scoped active Project was not found."""


class TextContextIdempotencyConflict(Exception):
    """The idempotency key was reused with different exact text."""


class TextContextPermissionDenied(Exception):
    """An inactive Membership cannot ingest Context."""


@dataclass(frozen=True, slots=True)
class CreateTextContextCommand:
    project_id: UUID
    raw_text: str
    idempotency_key: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class TextContextAccepted:
    source_id: UUID
    status: ContextSourceStatus
    job_id: UUID


class CreateTextContextUseCase:
    def __init__(
        self,
        unit_of_work_factory: TextContextIngestionUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(
        self, context: TenantContext, command: CreateTextContextCommand
    ) -> TextContextAccepted:
        _require_active_context(context)
        raw_text = validate_text_context(command.raw_text)
        if not command.idempotency_key.strip():
            raise ValueError("Idempotency-Key must not be empty")
        checksum = text_context_checksum(raw_text)
        request_hash = _text_context_request_hash(command.project_id, raw_text)
        now = self._clock()
        source_id = self._id_factory()
        version_id = self._id_factory()
        job_id = self._id_factory()
        outbox_id = self._id_factory()
        idempotency_id = self._id_factory()
        enrich_trace_context(
            account_id=str(context.account_id),
            project_id=str(command.project_id),
        )
        started_at = perf_counter()
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                reservation = await unit_of_work.idempotency.reserve(
                    record_id=idempotency_id,
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=TEXT_CONTEXT_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    now=now,
                    expires_at=now + TEXT_CONTEXT_IDEMPOTENCY_TTL,
                )
                if not reservation.acquired:
                    if reservation.request_hash != request_hash:
                        raise TextContextIdempotencyConflict
                    return self._replay(reservation.response_status, reservation.response_ref)

                project = await unit_of_work.projects.get(
                    account_id=context.account_id,
                    project_id=command.project_id,
                )
                if project is None:
                    raise TextContextNotFound

                await unit_of_work.context_sources.add_source(
                    NewContextSource(
                        id=source_id,
                        account_id=context.account_id,
                        project_id=command.project_id,
                        source_type="text",
                        status="uploaded",
                        original_name=None,
                        mime_type=None,
                        storage_ref=None,
                        raw_text=raw_text,
                        checksum=checksum,
                        created_by=context.subject_id,
                    )
                )
                await unit_of_work.context_sources.add_version(
                    NewContextSourceVersion(
                        id=version_id,
                        account_id=context.account_id,
                        project_id=command.project_id,
                        source_id=source_id,
                        version_no=1,
                        content_hash=None,
                        canonical_text=None,
                        storage_ref=None,
                        metadata=None,
                        parse_status="pending",
                    )
                )
                await unit_of_work.jobs.add(
                    NewJob(
                        id=job_id,
                        account_id=context.account_id,
                        project_id=command.project_id,
                        job_type=TEXT_CONTEXT_JOB_TYPE,
                        status="queued",
                        payload_ref={
                            "source_id": str(source_id),
                            "source_version_id": str(version_id),
                        },
                        attempt_count=0,
                        max_attempts=TEXT_CONTEXT_JOB_MAX_ATTEMPTS,
                        idempotency_key=command.idempotency_key,
                        correlation_id=command.correlation_id,
                        available_at=now,
                    )
                )
                await unit_of_work.outbox.add(
                    NewOutboxEvent(
                        id=outbox_id,
                        account_id=context.account_id,
                        aggregate_type="context_source",
                        aggregate_id=source_id,
                        event_type="context_added.v1",
                        payload={
                            "jobId": str(job_id),
                            "taskType": TEXT_CONTEXT_JOB_TYPE,
                            "payloadVersion": "1",
                            "accountId": str(context.account_id),
                            "projectId": str(command.project_id),
                            "correlationId": str(command.correlation_id),
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                accepted = TextContextAccepted(
                    source_id=source_id,
                    status="uploaded",
                    job_id=job_id,
                )
                await unit_of_work.idempotency.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=TEXT_CONTEXT_ROUTE_KEY,
                    idempotency_key=command.idempotency_key,
                    request_hash=request_hash,
                    response_status=202,
                    response_ref={
                        "source_id": str(accepted.source_id),
                        "status": accepted.status,
                        "job_id": str(accepted.job_id),
                    },
                )
                await unit_of_work.commit()
        except TextContextIngestionRepositoryError:
            self._event_logger.emit(
                "context_source.ingestion_failed",
                level="ERROR",
                actor_id=str(context.subject_id),
                component="text_context_ingestion",
                operation="create",
                error_code="CONTEXT_SOURCE_REPOSITORY_FAILURE",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
            )
            raise

        enrich_trace_context(job_id=str(job_id))
        self._event_logger.emit(
            "context_source.created",
            actor_id=str(context.subject_id),
            source_id=str(source_id),
            duration_ms=(perf_counter() - started_at) * 1000,
            status="uploaded",
        )
        self._event_logger.emit(
            "context_source_version.created",
            actor_id=str(context.subject_id),
            source_id=str(source_id),
            version_no=1,
            status="pending",
        )
        self._event_logger.emit(
            "job.queued",
            actor_id=str(context.subject_id),
            task_type=TEXT_CONTEXT_JOB_TYPE,
            status="queued",
        )
        return accepted

    def _replay(
        self,
        response_status: int | None,
        response_ref: dict[str, object] | None,
    ) -> TextContextAccepted:
        if response_status != 202 or response_ref is None:
            raise TextContextIngestionRepositoryError
        try:
            status = response_ref["status"]
            if status != "uploaded":
                raise ValueError
            accepted = TextContextAccepted(
                source_id=UUID(str(response_ref["source_id"])),
                status=cast(ContextSourceStatus, status),
                job_id=UUID(str(response_ref["job_id"])),
            )
        except (KeyError, TypeError, ValueError):
            raise TextContextIngestionRepositoryError from None
        enrich_trace_context(job_id=str(accepted.job_id))
        self._event_logger.emit(
            "context_source.create_replayed",
            source_id=str(accepted.source_id),
            status=accepted.status,
        )
        return accepted


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise TextContextPermissionDenied


def _text_context_request_hash(project_id: UUID, raw_text: str) -> str:
    """Hash every request input that can change the command's target or result."""
    canonical_request = json.dumps(
        {
            "project_id": str(project_id),
            "raw_text": raw_text,
            "source_type": "text",
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical_request.encode("utf-8")).hexdigest()
