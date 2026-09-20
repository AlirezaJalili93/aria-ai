from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from typing import Literal
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger, emit_product_analytics, enrich_trace_context

from app.modules.context.application.file_upload_ports import (
    FileUploadAllocation,
    FileUploadUnitOfWorkFactory,
    NewFileUploadAllocation,
    ObjectStorageError,
    ObjectStoragePort,
)
from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionRepositoryError,
)
from app.modules.context.domain.context_source import NewContextSource, NewContextSourceVersion
from app.modules.context.domain.file_upload import (
    FileTooLargeError,
    FileUploadValidationError,
    UnsupportedFileTypeError,
    ValidatedTextUpload,
    normalize_declared_mime_type,
    validate_text_upload,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

FILE_CONTEXT_JOB_TYPE = "context_source_parse"
FILE_CONTEXT_IDEMPOTENCY_TTL = timedelta(hours=24)
PARSER_AUTOMATIC_RETRY_ENABLED = False
FILE_CONTEXT_JOB_MAX_ATTEMPTS = 1


class FileContextNotFound(Exception):
    """The tenant-scoped active Project was not found."""


class FileContextIdempotencyConflict(Exception):
    """The idempotency key was reused with a different upload request."""


class FileContextPermissionDenied(Exception):
    """An inactive Membership cannot ingest a file Context."""


class FileContextStorageFailure(Exception):
    """A safe outward file storage failure signal."""

    def __init__(self, *, retryable: bool) -> None:
        super().__init__("Context file storage failed")
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class CreateFileContextCommand:
    project_id: UUID
    filename: str
    declared_mime_type: str | None
    content: bytes
    idempotency_key: str
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class FileContextAccepted:
    source_id: UUID
    status: Literal["uploaded"]
    job_id: UUID


class CreateFileContextUseCase:
    def __init__(
        self,
        unit_of_work_factory: FileUploadUnitOfWorkFactory,
        object_storage: ObjectStoragePort,
        event_logger: StructuredEventLogger,
        *,
        environment: str,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._object_storage = object_storage
        self._event_logger = event_logger
        self._environment = environment
        self._id_factory = id_factory
        self._clock = clock

    async def execute(
        self, context: TenantContext, command: CreateFileContextCommand
    ) -> FileContextAccepted:
        _require_active_context(context)
        started_at = perf_counter()
        enrich_trace_context(account_id=str(context.account_id), project_id=str(command.project_id))
        upload = self._validate(context, command, started_at)
        if not command.idempotency_key.strip():
            self._emit_validation_rejected(
                context=context,
                command=command,
                started_at=started_at,
                error_code="VALIDATION_FAILED",
            )
            raise FileUploadValidationError("Idempotency-Key must not be empty")

        request_hash = _file_context_request_hash(command.project_id, upload.content_digest)
        allocation = await self._allocate(
            context=context,
            command=command,
            request_hash=request_hash,
        )
        enrich_trace_context(job_id=str(allocation.job_id))
        if allocation.request_hash != request_hash:
            raise FileContextIdempotencyConflict
        if allocation.status == "committed":
            return self._replay(allocation)
        if allocation.status == "recovery_required":
            raise FileContextStorageFailure(retryable=False)
        if allocation.status == "uploading":
            raise FileContextStorageFailure(retryable=True)

        claimed, allocation = await self._claim(allocation)
        if not claimed:
            if allocation.status == "committed":
                return self._replay(allocation)
            if allocation.status == "recovery_required":
                raise FileContextStorageFailure(retryable=False)
            if allocation.status == "uploading":
                raise FileContextStorageFailure(retryable=True)
            raise TextContextIngestionRepositoryError(
                f"Unexpected upload allocation state after claim: {allocation.status}"
            )

        self._event_logger.emit(
            "storage.upload_started",
            actor_id=str(context.subject_id),
            source_id=str(allocation.source_id),
            source_version_id=str(allocation.source_version_id),
            job_id=str(allocation.job_id),
            file_size_bytes=len(upload.content),
            declared_mime_normalized=upload.mime_type,
            status="started",
        )
        try:
            await self._object_storage.put_private(
                object_key=allocation.object_key,
                content=upload.content,
                mime_type=upload.mime_type,
            )
        except ObjectStorageError as error:
            next_status: Literal["allocated", "recovery_required"] = (
                "recovery_required" if error.outcome_unknown else "allocated"
            )
            await self._transition(
                allocation,
                expected_status="uploading",
                status=next_status,
            )
            self._event_logger.emit(
                "storage.upload_failed",
                level="ERROR",
                actor_id=str(context.subject_id),
                source_id=str(allocation.source_id),
                source_version_id=str(allocation.source_version_id),
                job_id=str(allocation.job_id),
                file_size_bytes=len(upload.content),
                declared_mime_normalized=upload.mime_type,
                error_code="STORAGE_ERROR",
                reason_code=error.reason_code,
                duration_ms=(perf_counter() - started_at) * 1000,
                status=next_status,
            )
            raise FileContextStorageFailure(
                retryable=False if error.outcome_unknown else error.retryable
            ) from None

        self._event_logger.emit(
            "storage.upload_succeeded",
            actor_id=str(context.subject_id),
            source_id=str(allocation.source_id),
            source_version_id=str(allocation.source_version_id),
            job_id=str(allocation.job_id),
            file_size_bytes=len(upload.content),
            declared_mime_normalized=upload.mime_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )

        committed = False
        try:
            await self._persist_business_state(
                context=context,
                command=command,
                upload=upload,
                allocation=allocation,
            )
            committed = True
        finally:
            if not committed:
                cleanup_succeeded = await self._compensate(
                    context=context,
                    command=command,
                    allocation=allocation,
                    started_at=started_at,
                )
                await self._transition(
                    allocation,
                    expected_status="uploading",
                    status="allocated" if cleanup_succeeded else "recovery_required",
                )

        accepted = _accepted(allocation)
        self._event_logger.emit(
            "context_source.upload_committed",
            actor_id=str(context.subject_id),
            source_id=str(allocation.source_id),
            source_version_id=str(allocation.source_version_id),
            job_id=str(allocation.job_id),
            file_size_bytes=len(upload.content),
            declared_mime_normalized=upload.mime_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="uploaded",
        )
        emit_product_analytics(
            self._event_logger,
            event_name="context_added",
            logical_id=allocation.source_id,
            account_id=context.account_id,
            project_id=command.project_id,
            actor_id=context.subject_id,
            properties={"source_id": allocation.source_id, "source_surface": "system"},
        )
        return accepted

    async def _allocate(
        self,
        *,
        context: TenantContext,
        command: CreateFileContextCommand,
        request_hash: str,
    ) -> FileUploadAllocation:
        now = self._clock()
        source_id = self._id_factory()
        version_id = self._id_factory()
        new_allocation = NewFileUploadAllocation(
            id=self._id_factory(),
            account_id=context.account_id,
            actor_id=context.subject_id,
            project_id=command.project_id,
            idempotency_key=command.idempotency_key,
            request_hash=request_hash,
            source_id=source_id,
            source_version_id=version_id,
            job_id=self._id_factory(),
            object_key=build_file_object_key(
                environment=self._environment,
                account_id=context.account_id,
                project_id=command.project_id,
                source_id=source_id,
                version_id=version_id,
            ),
            expires_at=now + FILE_CONTEXT_IDEMPOTENCY_TTL,
        )
        async with self._unit_of_work_factory() as unit_of_work:
            project = await unit_of_work.projects.get(
                account_id=context.account_id,
                project_id=command.project_id,
            )
            if project is None:
                raise FileContextNotFound
            allocation = await unit_of_work.upload_allocations.allocate_or_get(
                new_allocation,
                now=now,
            )
            if allocation.request_hash != request_hash:
                raise FileContextIdempotencyConflict
            await unit_of_work.commit()
        return allocation

    async def _claim(self, allocation: FileUploadAllocation) -> tuple[bool, FileUploadAllocation]:
        now = self._clock()
        async with self._unit_of_work_factory() as unit_of_work:
            claimed = await unit_of_work.upload_allocations.transition(
                allocation_id=allocation.id,
                expected_status="allocated",
                status="uploading",
                now=now,
            )
            current = await unit_of_work.upload_allocations.get(
                account_id=allocation.account_id,
                actor_id=allocation.actor_id,
                project_id=allocation.project_id,
                idempotency_key=allocation.idempotency_key,
            )
            if current is None:
                raise TextContextIngestionRepositoryError("Upload allocation disappeared")
            await unit_of_work.commit()
        return claimed, current

    async def _persist_business_state(
        self,
        *,
        context: TenantContext,
        command: CreateFileContextCommand,
        upload: ValidatedTextUpload,
        allocation: FileUploadAllocation,
    ) -> None:
        now = self._clock()
        async with self._unit_of_work_factory() as unit_of_work:
            project = await unit_of_work.projects.get(
                account_id=context.account_id,
                project_id=command.project_id,
            )
            if project is None:
                raise FileContextNotFound
            await unit_of_work.context_sources.add_source(
                NewContextSource(
                    id=allocation.source_id,
                    account_id=context.account_id,
                    project_id=command.project_id,
                    source_type="file",
                    status="uploaded",
                    original_name=upload.original_name,
                    mime_type=upload.mime_type,
                    storage_ref=allocation.object_key,
                    raw_text=None,
                    checksum=None,
                    created_by=context.subject_id,
                )
            )
            await unit_of_work.context_sources.add_version(
                NewContextSourceVersion(
                    id=allocation.source_version_id,
                    account_id=context.account_id,
                    project_id=command.project_id,
                    source_id=allocation.source_id,
                    version_no=1,
                    content_hash=None,
                    canonical_text=None,
                    storage_ref=allocation.object_key,
                    metadata=None,
                    parse_status="pending",
                )
            )
            await unit_of_work.jobs.add(
                NewJob(
                    id=allocation.job_id,
                    account_id=context.account_id,
                    project_id=command.project_id,
                    job_type=FILE_CONTEXT_JOB_TYPE,
                    status="queued",
                    payload_ref={
                        "source_id": str(allocation.source_id),
                        "source_version_id": str(allocation.source_version_id),
                    },
                    attempt_count=0,
                    max_attempts=FILE_CONTEXT_JOB_MAX_ATTEMPTS,
                    idempotency_key=command.idempotency_key,
                    correlation_id=command.correlation_id,
                    available_at=now,
                )
            )
            await unit_of_work.outbox.add(
                NewOutboxEvent(
                    id=self._id_factory(),
                    account_id=context.account_id,
                    aggregate_type="context_source",
                    aggregate_id=allocation.source_id,
                    event_type="context_added.v1",
                    payload={
                        "jobId": str(allocation.job_id),
                        "taskType": FILE_CONTEXT_JOB_TYPE,
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
            transitioned = await unit_of_work.upload_allocations.transition(
                allocation_id=allocation.id,
                expected_status="uploading",
                status="committed",
                now=now,
                response_status=202,
            )
            if not transitioned:
                raise TextContextIngestionRepositoryError(
                    "Upload allocation could not be committed"
                )
            await unit_of_work.commit()

    async def _transition(
        self,
        allocation: FileUploadAllocation,
        *,
        expected_status: Literal["allocated", "uploading"],
        status: Literal["allocated", "recovery_required"],
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            transitioned = await unit_of_work.upload_allocations.transition(
                allocation_id=allocation.id,
                expected_status=expected_status,
                status=status,
                now=self._clock(),
            )
            if not transitioned:
                raise TextContextIngestionRepositoryError(
                    "Upload allocation recovery transition failed"
                )
            await unit_of_work.commit()

    def _validate(
        self,
        context: TenantContext,
        command: CreateFileContextCommand,
        started_at: float,
    ) -> ValidatedTextUpload:
        try:
            return validate_text_upload(
                filename=command.filename,
                declared_mime_type=command.declared_mime_type,
                content=command.content,
            )
        except FileTooLargeError:
            self._emit_validation_rejected(
                context=context,
                command=command,
                started_at=started_at,
                error_code="FILE_TOO_LARGE",
            )
            raise
        except UnsupportedFileTypeError:
            self._emit_validation_rejected(
                context=context,
                command=command,
                started_at=started_at,
                error_code="UNSUPPORTED_FILE_TYPE",
            )
            raise
        except FileUploadValidationError:
            self._emit_validation_rejected(
                context=context,
                command=command,
                started_at=started_at,
                error_code="VALIDATION_FAILED",
            )
            raise

    def _emit_validation_rejected(
        self,
        *,
        context: TenantContext,
        command: CreateFileContextCommand,
        started_at: float,
        error_code: str,
    ) -> None:
        self._event_logger.emit(
            "upload.validation_rejected",
            level="WARNING",
            actor_id=str(context.subject_id),
            file_size_bytes=len(command.content),
            declared_mime_normalized=normalize_declared_mime_type(command.declared_mime_type),
            validation_result="rejected",
            error_code=error_code,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="rejected",
        )

    async def _compensate(
        self,
        *,
        context: TenantContext,
        command: CreateFileContextCommand,
        allocation: FileUploadAllocation,
        started_at: float,
    ) -> bool:
        declared_mime = normalize_declared_mime_type(command.declared_mime_type)
        self._event_logger.emit(
            "storage.compensation_started",
            actor_id=str(context.subject_id),
            source_id=str(allocation.source_id),
            source_version_id=str(allocation.source_version_id),
            job_id=str(allocation.job_id),
            file_size_bytes=len(command.content),
            declared_mime_normalized=declared_mime,
            status="started",
        )
        try:
            await self._object_storage.delete(object_key=allocation.object_key)
        except ObjectStorageError as error:
            self._event_logger.emit(
                "storage.compensation_failed",
                level="CRITICAL",
                actor_id=str(context.subject_id),
                source_id=str(allocation.source_id),
                source_version_id=str(allocation.source_version_id),
                job_id=str(allocation.job_id),
                file_size_bytes=len(command.content),
                declared_mime_normalized=declared_mime,
                error_code="STORAGE_ERROR",
                reason_code=error.reason_code,
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
            )
            return False
        self._event_logger.emit(
            "storage.compensation_succeeded",
            actor_id=str(context.subject_id),
            source_id=str(allocation.source_id),
            source_version_id=str(allocation.source_version_id),
            job_id=str(allocation.job_id),
            file_size_bytes=len(command.content),
            declared_mime_normalized=declared_mime,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return True

    def _replay(self, allocation: FileUploadAllocation) -> FileContextAccepted:
        if allocation.response_status != 202:
            raise TextContextIngestionRepositoryError("Committed upload response is invalid")
        accepted = _accepted(allocation)
        enrich_trace_context(job_id=str(accepted.job_id))
        self._event_logger.emit(
            "context_source.upload_replayed",
            source_id=str(accepted.source_id),
            job_id=str(accepted.job_id),
            status=accepted.status,
        )
        return accepted


def _accepted(allocation: FileUploadAllocation) -> FileContextAccepted:
    return FileContextAccepted(
        source_id=allocation.source_id,
        status="uploaded",
        job_id=allocation.job_id,
    )


def build_file_object_key(
    *,
    environment: str,
    account_id: UUID,
    project_id: UUID,
    source_id: UUID,
    version_id: UUID,
) -> str:
    return "/".join(
        (environment, str(account_id), str(project_id), str(source_id), str(version_id))
    )


def _require_active_context(context: TenantContext) -> None:
    if context.membership_status != "active":
        raise FileContextPermissionDenied


def _file_context_request_hash(project_id: UUID, content_digest: str) -> str:
    canonical_request = json.dumps(
        {
            "file_hash": content_digest,
            "project_id": str(project_id),
            "source_type": "file",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical_request.encode("utf-8")).hexdigest()
