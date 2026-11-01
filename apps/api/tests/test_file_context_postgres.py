from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import TraceContext, bind_trace_context, create_event_logger
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.application.file_context_ingestion import (
    CreateFileContextCommand,
    CreateFileContextUseCase,
    FileContextIdempotencyConflict,
    FileContextNotFound,
    FileContextStorageFailure,
)
from app.modules.context.application.file_upload_ports import ObjectStorageError
from app.modules.context.infrastructure.text_ingestion import (
    SqlAlchemyTextContextIngestionUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


class RecordingStorage:
    def __init__(self, *, upload_delay: float = 0) -> None:
        self.upload_delay = upload_delay
        self.puts: list[tuple[str, bytes, str]] = []
        self.deletes: list[str] = []
        self.put_error: ObjectStorageError | None = None

    async def put_private(self, *, object_key: str, content: bytes, mime_type: str) -> None:
        if self.upload_delay:
            await asyncio.sleep(self.upload_delay)
        self.puts.append((object_key, content, mime_type))
        if self.put_error is not None:
            raise self.put_error

    async def delete(self, *, object_key: str) -> None:
        self.deletes.append(object_key)


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None) -> None:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


async def _scalar(sql: str, parameters: dict[str, object] | None = None) -> object:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.connect() as connection:
            return (
                await connection.execute(text(sql), parameters or {})
            ).scalar_one()
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_file_context_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE file_upload_allocations, idempotency_records, outbox_events, jobs, "
            "context_source_versions, "
            "context_sources, project_create_requests, projects, account_memberships, profiles, "
            "accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed_project() -> tuple[TenantContext, UUID]:
    user_id, account_id, project_id, membership_id = uuid4(), uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
        "VALUES (:id, :account_id, :user_id, 'owner', 'active')",
        {
            "id": membership_id,
            "account_id": account_id,
            "user_id": user_id,
        },
    )
    await _execute(
        "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
        "VALUES (:id, :account_id, :owner_id, 'Project', 'landing')",
        {"id": project_id, "account_id": account_id, "owner_id": user_id},
    )
    return (
        TenantContext(
            subject_id=user_id,
            account_id=account_id,
            membership_id=membership_id,
            role="owner",
            membership_status="active",
        ),
        project_id,
    )


async def _run_concurrently(
    context: TenantContext,
    project_id: UUID,
    storage: RecordingStorage,
):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    stream = StringIO()
    service = CreateFileContextUseCase(
        SqlAlchemyTextContextIngestionUnitOfWorkFactory(runtime.session_factory),
        storage,
        create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=stream,
        ),
        environment="test",
        clock=lambda: datetime(2026, 9, 14, 8, 0, tzinfo=UTC),
    )
    content = "متن محرمانه پروژه".encode()

    async def execute(filename: str):
        request_id, correlation_id = uuid4(), uuid4()
        with bind_trace_context(
            TraceContext(request_id=str(request_id), correlation_id=str(correlation_id))
        ):
            return await service.execute(
                context,
                CreateFileContextCommand(
                    project_id=project_id,
                    filename=filename,
                    declared_mime_type="text/plain; charset=utf-8",
                    content=content,
                    idempotency_key="same-upload",
                    correlation_id=correlation_id,
                ),
            )

    try:
        results = await asyncio.gather(
            execute("first.txt"),
            execute("changed-display.txt"),
            return_exceptions=True,
        )
        return results, stream.getvalue(), content
    finally:
        await runtime.close()


def test_concurrent_same_upload_persists_one_pipeline_and_one_private_object() -> None:
    context, project_id = asyncio.run(_seed_project())
    storage = RecordingStorage(upload_delay=0.1)

    results, logs, content = asyncio.run(_run_concurrently(context, project_id, storage))

    accepted = [item for item in results if not isinstance(item, BaseException)]
    suppressed = [item for item in results if isinstance(item, FileContextStorageFailure)]
    assert len(accepted) >= 1
    assert len(accepted) + len(suppressed) == 2, results
    assert all(error.retryable is True for error in suppressed)
    assert len(storage.puts) == 1
    object_key, stored_content, mime_type = storage.puts[0]
    assert stored_content == content and mime_type == "text/plain"
    assert object_key.split("/")[:3] == [
        "test",
        str(context.account_id),
        str(project_id),
    ]
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_source_versions"))) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM jobs"))) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM outbox_events"))) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM idempotency_records"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM file_upload_allocations"))) == 1
    assert asyncio.run(_scalar("SELECT status FROM file_upload_allocations")) == "committed"
    assert content.decode() not in logs
    assert object_key not in logs
    assert "first.txt" not in logs and "changed-display.txt" not in logs


def test_changed_bytes_with_same_key_conflict_before_second_upload() -> None:
    context, project_id = asyncio.run(_seed_project())
    storage = RecordingStorage()

    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = CreateFileContextUseCase(
            SqlAlchemyTextContextIngestionUnitOfWorkFactory(runtime.session_factory),
            storage,
            create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
                stream=StringIO(),
            ),
            environment="test",
        )
        try:
            for content in (b"first", b"different"):
                correlation_id = uuid4()
                with bind_trace_context(
                    TraceContext(
                        request_id=str(uuid4()),
                        correlation_id=str(correlation_id),
                    )
                ):
                    command_ = CreateFileContextCommand(
                        project_id=project_id,
                        filename="brief.txt",
                        declared_mime_type="text/plain",
                        content=content,
                        idempotency_key="same-upload",
                        correlation_id=correlation_id,
                    )
                    if content == b"first":
                        await service.execute(context, command_)
                    else:
                        with pytest.raises(FileContextIdempotencyConflict):
                            await service.execute(context, command_)
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert len(storage.puts) == 1
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 1


def test_cross_tenant_project_is_safe_not_found_before_private_object_upload() -> None:
    attacker_context, _ = asyncio.run(_seed_project())
    _, foreign_project_id = asyncio.run(_seed_project())
    storage = RecordingStorage()

    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = CreateFileContextUseCase(
            SqlAlchemyTextContextIngestionUnitOfWorkFactory(runtime.session_factory),
            storage,
            create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
                stream=StringIO(),
            ),
            environment="test",
        )
        correlation_id = uuid4()
        try:
            with bind_trace_context(
                TraceContext(
                    request_id=str(uuid4()),
                    correlation_id=str(correlation_id),
                )
            ), pytest.raises(FileContextNotFound):
                await service.execute(
                    attacker_context,
                    CreateFileContextCommand(
                        project_id=foreign_project_id,
                        filename="private.txt",
                        declared_mime_type="text/plain",
                        content=b"private tenant data",
                        idempotency_key="foreign-upload",
                        correlation_id=correlation_id,
                    ),
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert storage.puts == []
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_source_versions"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM jobs"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM outbox_events"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM file_upload_allocations"))) == 0


def test_unknown_put_outcome_is_durable_and_same_key_does_not_blind_reupload() -> None:
    context, project_id = asyncio.run(_seed_project())
    storage = RecordingStorage()
    storage.put_error = ObjectStorageError(
        retryable=False,
        reason_code="provider_put_outcome_unknown",
        outcome_unknown=True,
    )

    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        allocated_at = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
        service = CreateFileContextUseCase(
            SqlAlchemyTextContextIngestionUnitOfWorkFactory(runtime.session_factory),
            storage,
            create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
                stream=StringIO(),
            ),
            environment="test",
            clock=lambda: allocated_at,
        )
        command_ = CreateFileContextCommand(
            project_id=project_id,
            filename="brief.txt",
            declared_mime_type="text/plain",
            content=b"private context",
            idempotency_key="unknown-outcome",
            correlation_id=uuid4(),
        )
        try:
            with bind_trace_context(
                TraceContext(
                    request_id=str(uuid4()),
                    correlation_id=str(command_.correlation_id),
                )
            ):
                with pytest.raises(FileContextStorageFailure) as first:
                    await service.execute(context, command_)
                assert first.value.retryable is False
                storage.put_error = None
                expired_retry_service = CreateFileContextUseCase(
                    SqlAlchemyTextContextIngestionUnitOfWorkFactory(
                        runtime.session_factory
                    ),
                    storage,
                    create_event_logger(
                        service="aria-api",
                        environment="test",
                        app_version="0.1.0",
                        release_commit_sha=None,
                        level="INFO",
                        stream=StringIO(),
                    ),
                    environment="test",
                    clock=lambda: allocated_at + timedelta(hours=25),
                )
                with pytest.raises(FileContextStorageFailure) as replay:
                    await expired_retry_service.execute(context, command_)
                assert replay.value.retryable is False
        finally:
            await runtime.close()

    asyncio.run(scenario())
    assert len(storage.puts) == 1
    row = asyncio.run(
        _scalar(
            "SELECT status || ':' || source_id::text || ':' || source_version_id::text "
            "|| ':' || job_id::text || ':' || object_key FROM file_upload_allocations"
        )
    )
    assert str(row).startswith("recovery_required:")
    assert int(asyncio.run(_scalar("SELECT count(*) FROM context_sources"))) == 0
    assert int(asyncio.run(_scalar("SELECT count(*) FROM jobs"))) == 0


def test_upload_allocation_table_is_rls_protected_from_data_api_roles() -> None:
    assert asyncio.run(
        _scalar(
            "SELECT relrowsecurity FROM pg_catalog.pg_class "
            "WHERE oid = 'public.file_upload_allocations'::regclass"
        )
    ) is True
    assert int(
        asyncio.run(
            _scalar(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_schema='public' "
                "AND table_name='file_upload_allocations' "
                "AND grantee IN ('anon','authenticated')"
            )
        )
    ) == 0
