from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.file_context_ingestion import (
    CreateFileContextCommand,
    CreateFileContextUseCase,
    FileContextIdempotencyConflict,
    FileContextNotFound,
    FileContextStorageFailure,
    build_file_object_key,
)
from app.modules.context.application.file_upload_ports import (
    FileUploadAllocation,
    NewFileUploadAllocation,
    ObjectStorageError,
    UploadAllocationStatus,
)
from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionRepositoryError,
)
from app.modules.context.domain.context_source import (
    ContextSource,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
)
from app.modules.context.domain.file_upload import FileUploadValidationError
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent


class FakeRepository:
    def __init__(self) -> None:
        self.sources: list[ContextSource] = []
        self.versions: list[ContextSourceVersion] = []

    async def add_source(self, source: NewContextSource) -> ContextSource:
        now = datetime.now(UTC)
        row = ContextSource(**asdict(source), created_at=now, updated_at=now)
        self.sources.append(row)
        return row

    async def add_version(self, version: NewContextSourceVersion) -> ContextSourceVersion:
        row = ContextSourceVersion(**asdict(version), created_at=datetime.now(UTC))
        self.versions.append(row)
        return row


class FakeProjects:
    def __init__(self, *, exists: bool) -> None:
        self.exists = exists

    async def get(self, *, account_id: UUID, project_id: UUID) -> object | None:
        del account_id, project_id
        return object() if self.exists else None


class FakeJobs:
    def __init__(self) -> None:
        self.rows: list[Job] = []

    async def add(self, job: NewJob) -> Job:
        row = Job(
            **asdict(job),
            started_at=None,
            finished_at=None,
            error_code=None,
            error_detail=None,
            created_at=datetime.now(UTC),
        )
        self.rows.append(row)
        return row


class FakeOutbox:
    def __init__(self) -> None:
        self.rows: list[OutboxEvent] = []

    async def add(self, event: NewOutboxEvent) -> OutboxEvent:
        row = OutboxEvent(
            **asdict(event),
            created_at=datetime.now(UTC),
            published_at=None,
        )
        self.rows.append(row)
        return row

    async def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        del event_id, published_at


class FakeUploadAllocations:
    def __init__(self) -> None:
        self.row: FileUploadAllocation | None = None

    async def allocate_or_get(
        self,
        allocation: NewFileUploadAllocation,
        *,
        now: datetime,
    ) -> FileUploadAllocation:
        if self.row is not None:
            return self.row
        self.row = FileUploadAllocation(
            **asdict(allocation),
            status="allocated",
            response_status=None,
            created_at=now,
            updated_at=now,
        )
        return self.row

    async def get(self, **kwargs: object) -> FileUploadAllocation | None:
        del kwargs
        return self.row

    async def transition(
        self,
        *,
        allocation_id: UUID,
        expected_status: UploadAllocationStatus,
        status: UploadAllocationStatus,
        now: datetime,
        response_status: int | None = None,
    ) -> bool:
        if self.row is None or self.row.id != allocation_id or self.row.status != expected_status:
            return False
        self.row = FileUploadAllocation(
            **{
                **asdict(self.row),
                "status": status,
                "response_status": response_status,
                "updated_at": now,
            }
        )
        return True


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        project_exists: bool = True,
        commit_fails_on: int | None = None,
    ) -> None:
        self.projects = FakeProjects(exists=project_exists)
        self.context_sources = FakeRepository()
        self.jobs = FakeJobs()
        self.outbox = FakeOutbox()
        self.upload_allocations = FakeUploadAllocations()
        self.commit_fails_on = commit_fails_on
        self.commits = 0
        self.commit_attempts = 0

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.commit_attempts += 1
        if self.commit_fails_on == self.commit_attempts:
            row = self.upload_allocations.row
            if row is not None and row.status == "committed":
                self.upload_allocations.row = FileUploadAllocation(
                    **{
                        **asdict(row),
                        "status": "uploading",
                        "response_status": None,
                    }
                )
            raise TextContextIngestionRepositoryError
        self.commits += 1


class FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes, str]] = []
        self.deletes: list[str] = []
        self.put_error: ObjectStorageError | None = None
        self.delete_error: ObjectStorageError | None = None

    async def put_private(self, *, object_key: str, content: bytes, mime_type: str) -> None:
        self.puts.append((object_key, content, mime_type))
        if self.put_error is not None:
            raise self.put_error

    async def delete(self, *, object_key: str) -> None:
        self.deletes.append(object_key)
        if self.delete_error is not None:
            raise self.delete_error


def _context() -> TenantContext:
    return TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _command(
    project_id: UUID,
    *,
    content: bytes = "متن محرمانه".encode(),
) -> CreateFileContextCommand:
    return CreateFileContextCommand(
        project_id=project_id,
        filename="private-brief.txt",
        declared_mime_type="text/plain; charset=utf-8",
        content=content,
        idempotency_key="upload-key",
        correlation_id=uuid4(),
    )


def _execute(
    service: CreateFileContextUseCase,
    context: TenantContext,
    command: CreateFileContextCommand,
):
    async def scenario():
        with bind_trace_context(
            TraceContext(request_id=str(uuid4()), correlation_id=str(command.correlation_id))
        ):
            return await service.execute(context, command)

    return asyncio.run(scenario())


def _logger(stream: StringIO):
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def test_file_ingestion_uploads_then_atomically_persists_content_free_job() -> None:
    unit_of_work, storage, stream = FakeUnitOfWork(), FakeStorage(), StringIO()
    context, project_id = _context(), uuid4()
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(stream),
        environment="test",
    )
    command = _command(project_id)

    accepted = _execute(service, context, command)

    assert unit_of_work.commits == 3
    assert unit_of_work.upload_allocations.row is not None
    assert unit_of_work.upload_allocations.row.status == "committed"
    source = unit_of_work.context_sources.sources[0]
    version = unit_of_work.context_sources.versions[0]
    job = unit_of_work.jobs.rows[0]
    outbox = unit_of_work.outbox.rows[0]
    assert source.source_type == "file" and source.raw_text is None and source.checksum is None
    assert source.original_name == "private-brief.txt" and source.mime_type == "text/plain"
    assert source.storage_ref == version.storage_ref == storage.puts[0][0]
    assert storage.puts[0] == (source.storage_ref, command.content, "text/plain")
    assert source.storage_ref == build_file_object_key(
        environment="test",
        account_id=context.account_id,
        project_id=project_id,
        source_id=source.id,
        version_id=version.id,
    )
    assert job.payload_ref == {
        "source_id": str(source.id),
        "source_version_id": str(version.id),
    }
    assert job.max_attempts == 1
    assert outbox.payload["jobId"] == str(job.id)
    assert accepted.source_id == source.id and accepted.job_id == job.id
    serialized = json.dumps({"job": job.payload_ref, "outbox": outbox.payload})
    assert command.content.decode() not in serialized
    logs = stream.getvalue()
    assert "private-brief.txt" not in logs
    assert command.content.decode() not in logs
    assert source.storage_ref not in logs
    events = [json.loads(line) for line in logs.splitlines()]
    assert {item["event_name"] for item in events} == {
        "storage.upload_started",
        "storage.upload_succeeded",
        "context_source.upload_committed",
        "context_added",
    }
    upload_event = next(item for item in events if item["event_name"] == "storage.upload_succeeded")
    assert upload_event["source_version_id"] == str(version.id)
    assert upload_event["file_size_bytes"] == len(command.content)
    assert upload_event["declared_mime_normalized"] == "text/plain"


def test_same_semantic_upload_replays_without_second_object_and_changed_bytes_conflict() -> None:
    unit_of_work, storage = FakeUnitOfWork(), FakeStorage()
    context, project_id = _context(), uuid4()
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(StringIO()),
        environment="test",
    )
    command = _command(project_id)
    first = _execute(service, context, command)
    replay = _execute(
        service,
        context,
        CreateFileContextCommand(**{**asdict(command), "filename": "display-name-changed.txt"}),
    )
    assert replay == first
    assert len(storage.puts) == 1
    assert len(unit_of_work.context_sources.sources) == 1

    with pytest.raises(FileContextIdempotencyConflict):
        _execute(service, context, _command(project_id, content=b"different"))
    assert len(storage.puts) == 1


def test_missing_project_or_storage_failure_persists_no_business_state() -> None:
    context, project_id = _context(), uuid4()
    missing_uow, missing_storage = FakeUnitOfWork(project_exists=False), FakeStorage()
    with pytest.raises(FileContextNotFound):
        _execute(
            CreateFileContextUseCase(
                lambda: missing_uow,
                missing_storage,
                _logger(StringIO()),
                environment="test",
            ),
            context,
            _command(project_id),
        )
    assert not missing_storage.puts
    assert not missing_uow.context_sources.sources

    failed_uow, failed_storage, failed_stream = FakeUnitOfWork(), FakeStorage(), StringIO()
    failed_storage.put_error = ObjectStorageError(
        retryable=True,
        reason_code="provider_network_transient",
    )
    with pytest.raises(FileContextStorageFailure, match="Context file storage failed") as error:
        _execute(
            CreateFileContextUseCase(
                lambda: failed_uow,
                failed_storage,
                _logger(failed_stream),
                environment="test",
            ),
            context,
            _command(project_id),
        )
    assert error.value.retryable is True
    assert not failed_uow.context_sources.sources
    assert failed_uow.upload_allocations.row is not None
    assert failed_uow.upload_allocations.row.status == "allocated"
    failed_log = failed_stream.getvalue()
    assert "storage.upload_failed" in failed_log
    assert "provider_network_transient" in failed_log
    assert "private-brief.txt" not in failed_log


def test_unknown_put_outcome_requires_recovery_and_same_key_never_reuploads() -> None:
    unit_of_work, storage = FakeUnitOfWork(), FakeStorage()
    context, project_id = _context(), uuid4()
    storage.put_error = ObjectStorageError(
        retryable=False,
        reason_code="provider_put_outcome_unknown",
        outcome_unknown=True,
    )
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(StringIO()),
        environment="test",
    )
    command = _command(project_id)

    with pytest.raises(FileContextStorageFailure) as first_error:
        _execute(service, context, command)
    allocation = unit_of_work.upload_allocations.row
    assert allocation is not None
    assert allocation.status == "recovery_required"
    assert first_error.value.retryable is False

    storage.put_error = None
    with pytest.raises(FileContextStorageFailure) as replay_error:
        _execute(service, context, command)
    assert replay_error.value.retryable is False
    assert len(storage.puts) == 1
    assert unit_of_work.upload_allocations.row == allocation


def test_definite_retryable_failure_reuses_allocation_and_can_retry() -> None:
    unit_of_work, storage = FakeUnitOfWork(), FakeStorage()
    context, project_id = _context(), uuid4()
    storage.put_error = ObjectStorageError(
        retryable=True,
        reason_code="provider_network_transient",
    )
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(StringIO()),
        environment="test",
    )
    command = _command(project_id)

    with pytest.raises(FileContextStorageFailure) as first_error:
        _execute(service, context, command)
    allocation = unit_of_work.upload_allocations.row
    assert allocation is not None and allocation.status == "allocated"
    assert first_error.value.retryable is True

    storage.put_error = None
    result = _execute(service, context, command)

    assert result.source_id == allocation.source_id
    assert result.job_id == allocation.job_id
    assert [put[0] for put in storage.puts] == [allocation.object_key, allocation.object_key]


def test_compensated_retry_reuses_allocation_ids_and_object_key() -> None:
    unit_of_work, storage = FakeUnitOfWork(commit_fails_on=3), FakeStorage()
    context, project_id = _context(), uuid4()
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(StringIO()),
        environment="test",
    )
    command = _command(project_id)

    with pytest.raises(TextContextIngestionRepositoryError):
        _execute(service, context, command)
    allocation = unit_of_work.upload_allocations.row
    assert allocation is not None and allocation.status == "allocated"

    result = _execute(service, context, command)

    assert result.source_id == allocation.source_id
    assert result.job_id == allocation.job_id
    assert [put[0] for put in storage.puts] == [allocation.object_key, allocation.object_key]
    assert unit_of_work.upload_allocations.row is not None
    assert unit_of_work.upload_allocations.row.status == "committed"


def test_validation_rejection_logs_no_filename_content_or_storage_reference() -> None:
    unit_of_work, storage, stream = FakeUnitOfWork(), FakeStorage(), StringIO()
    context, project_id = _context(), uuid4()
    service = CreateFileContextUseCase(
        lambda: unit_of_work,
        storage,
        _logger(stream),
        environment="test",
    )
    filename = "customer-secret-name.txt"
    content = b"customer-secret-content\x00"
    command = CreateFileContextCommand(
        project_id=project_id,
        filename=filename,
        declared_mime_type="text/plain",
        content=content,
        idempotency_key="rejected-upload",
        correlation_id=uuid4(),
    )

    with pytest.raises(FileUploadValidationError):
        _execute(service, context, command)

    logs = stream.getvalue()
    assert filename not in logs
    assert "customer-secret-content" not in logs
    assert "storage_ref" not in logs
    assert "object_key" not in logs
    assert storage.puts == []
    event = json.loads(logs)
    assert event["event_name"] == "upload.validation_rejected"
    assert event["error_code"] == "VALIDATION_FAILED"
    assert event["file_size_bytes"] == len(content)


def test_db_failure_compensates_and_cleanup_failure_is_a_safe_discoverable_incident() -> None:
    context, project_id = _context(), uuid4()
    for delete_error, expected_event in (
        (None, "storage.compensation_succeeded"),
        (
            ObjectStorageError(
                retryable=True,
                reason_code="compensation_network_transient",
            ),
            "storage.compensation_failed",
        ),
    ):
        unit_of_work, storage, stream = (
            FakeUnitOfWork(commit_fails_on=3),
            FakeStorage(),
            StringIO(),
        )
        storage.delete_error = delete_error
        with pytest.raises(TextContextIngestionRepositoryError):
            _execute(
                CreateFileContextUseCase(
                    lambda unit_of_work=unit_of_work: unit_of_work,
                    storage,
                    _logger(stream),
                    environment="test",
                ),
                context,
                _command(project_id),
            )
        assert storage.deletes == [storage.puts[0][0]]
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        assert "storage.compensation_started" in {item["event_name"] for item in events}
        assert expected_event in {item["event_name"] for item in events}
        incident = next(item for item in events if item["event_name"] == expected_event)
        assert incident["source_id"] is not None
        assert incident["source_version_id"] is not None
        assert storage.puts[0][0] not in stream.getvalue()
        assert unit_of_work.upload_allocations.row is not None
        expected_status = "allocated" if delete_error is None else "recovery_required"
        assert unit_of_work.upload_allocations.row.status == expected_status
