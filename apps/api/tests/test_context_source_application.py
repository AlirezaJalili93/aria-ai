from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.context_source_service import (
    CompleteContextSourceVersionCommand,
    ContextSourceApplicationService,
    ContextSourceTypeUnavailable,
    CreateContextSourceCommand,
    CreateContextSourceVersionCommand,
)
from app.modules.context.application.ports import (
    ContextSourceRepository,
    ContextSourceRepositoryError,
    ContextSourceUnitOfWork,
)
from app.modules.context.domain.context_source import (
    ContextSource,
    ContextSourceStatus,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
)
from app.modules.identity.application.tenant_context import TenantContext


class FakeContextSourceRepository(ContextSourceRepository):
    def __init__(self) -> None:
        self.sources: dict[UUID, ContextSource] = {}
        self.versions: dict[UUID, ContextSourceVersion] = {}
        self.fail = False

    def _check(self) -> None:
        if self.fail:
            raise ContextSourceRepositoryError

    async def add_source(self, source: NewContextSource) -> ContextSource:
        self._check()
        now = datetime.now(UTC)
        persisted = ContextSource(**asdict(source), created_at=now, updated_at=now)
        self.sources[source.id] = persisted
        return persisted

    async def get_source(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSource | None:
        self._check()
        source = self.sources.get(source_id)
        if (
            source is None
            or source.account_id != account_id
            or source.project_id != project_id
            or source.status == "deleted"
        ):
            return None
        return source

    async def set_source_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        status: ContextSourceStatus,
    ) -> ContextSource | None:
        source = await self.get_source(
            account_id=account_id, project_id=project_id, source_id=source_id
        )
        if source is None:
            return None
        persisted = replace(source, status=status, updated_at=datetime.now(UTC))
        self.sources[source_id] = persisted
        return persisted

    async def add_version(self, version: NewContextSourceVersion) -> ContextSourceVersion:
        self._check()
        persisted = ContextSourceVersion(**asdict(version), created_at=datetime.now(UTC))
        self.versions[version.id] = persisted
        return persisted

    async def mark_version_ready(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
        content_hash: str | None,
        canonical_text: str | None,
        storage_ref: str | None,
        metadata: dict[str, object] | None,
    ) -> ContextSourceVersion | None:
        self._check()
        version = self.versions.get(version_id)
        if (
            version is None
            or version.account_id != account_id
            or version.project_id != project_id
            or version.source_id != source_id
            or version.parse_status == "ready"
        ):
            return None
        persisted = replace(
            version,
            content_hash=content_hash,
            canonical_text=canonical_text,
            storage_ref=storage_ref,
            metadata=metadata,
            parse_status="ready",
        )
        self.versions[version_id] = persisted
        return persisted

    async def mark_version_failed(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
    ) -> ContextSourceVersion | None:
        self._check()
        version = self.versions.get(version_id)
        if (
            version is None
            or version.account_id != account_id
            or version.project_id != project_id
            or version.source_id != source_id
            or version.parse_status == "ready"
        ):
            return None
        persisted = replace(version, parse_status="failed")
        self.versions[version_id] = persisted
        return persisted

    async def get_current_ready_version(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSourceVersion | None:
        self._check()
        rows = [
            row
            for row in self.versions.values()
            if row.account_id == account_id
            and row.project_id == project_id
            and row.source_id == source_id
            and row.parse_status == "ready"
        ]
        return max(rows, key=lambda row: row.version_no, default=None)


class FakeContextSourceUnitOfWork(ContextSourceUnitOfWork):
    def __init__(self, repository: FakeContextSourceRepository) -> None:
        self._repository = repository
        self.commits = 0

    @property
    def repository(self) -> ContextSourceRepository:
        return self._repository

    async def __aenter__(self) -> FakeContextSourceUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.commits += 1


def _context() -> TenantContext:
    return TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _service(
    repository: FakeContextSourceRepository, stream: StringIO, ids: list[UUID]
) -> ContextSourceApplicationService:
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    iterator = iter(ids)
    return ContextSourceApplicationService(
        lambda: FakeContextSourceUnitOfWork(repository), logger, id_factory=lambda: next(iterator)
    )


def _trace() -> TraceContext:
    return TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))


def test_application_admits_text_only_and_logs_source_without_content() -> None:
    repository = FakeContextSourceRepository()
    stream = StringIO()
    source_id = uuid4()
    context = _context()
    project_id = uuid4()
    service = _service(repository, stream, [source_id])

    async def scenario() -> ContextSource:
        with bind_trace_context(_trace()):
            return await service.create_source(
                context,
                CreateContextSourceCommand(
                    project_id=project_id,
                    source_type="text",
                    raw_text="محتوای بسیار محرمانه",
                ),
            )

    source = asyncio.run(scenario())
    assert source.status == "uploaded"
    event = json.loads(stream.getvalue().splitlines()[-1])
    assert event["event_name"] == "context_source.created"
    assert event["account_id"] == str(context.account_id)
    assert event["project_id"] == str(project_id)
    assert event["source_id"] == str(source_id)
    assert event["request_id"] and event["correlation_id"]
    assert "محتوای بسیار محرمانه" not in stream.getvalue()

    for source_type in ("file", "message", "url_reference"):
        with pytest.raises(ContextSourceTypeUnavailable):
            asyncio.run(
                service.create_source(
                    context,
                    CreateContextSourceCommand(
                        project_id=project_id,
                        source_type=source_type,  # type: ignore[arg-type]
                    ),
                )
            )


def test_version_lifecycle_uses_derived_current_and_safe_events() -> None:
    repository = FakeContextSourceRepository()
    stream = StringIO()
    source_id, version_one_id, version_two_id = uuid4(), uuid4(), uuid4()
    context = _context()
    project_id = uuid4()
    service = _service(repository, stream, [source_id, version_one_id, version_two_id])

    async def scenario() -> tuple[ContextSourceVersion, ContextSourceVersion | None]:
        with bind_trace_context(_trace()):
            await service.create_source(
                context,
                CreateContextSourceCommand(
                    project_id=project_id, source_type="text", raw_text="raw private"
                ),
            )
            first = await service.create_version(
                context,
                CreateContextSourceVersionCommand(
                    project_id=project_id, source_id=source_id, version_no=1
                ),
            )
            ready = await service.complete_version(
                context,
                CompleteContextSourceVersionCommand(
                    project_id=project_id,
                    source_id=source_id,
                    version_id=first.id,
                    content_hash=None,
                    canonical_text="canonical private",
                    storage_ref="storage/private/key",
                    metadata={"private": "metadata"},
                ),
            )
            second = await service.create_version(
                context,
                CreateContextSourceVersionCommand(
                    project_id=project_id, source_id=source_id, version_no=2
                ),
            )
            await service.fail_version(
                context,
                project_id=project_id,
                source_id=source_id,
                version_id=second.id,
            )
            current = await service.get_current_version(
                context, project_id=project_id, source_id=source_id
            )
            await service.mark_source_deleted(context, project_id=project_id, source_id=source_id)
            return ready, current

    ready, current = asyncio.run(scenario())
    assert current == ready
    event_names = [json.loads(line)["event_name"] for line in stream.getvalue().splitlines()]
    assert {
        "context_source.created",
        "context_source.deleted",
        "context_source_version.created",
        "context_source_version.ready",
        "context_source_version.failed",
    }.issubset(event_names)
    assert "raw private" not in stream.getvalue()
    assert "canonical private" not in stream.getvalue()
    assert "storage/private/key" not in stream.getvalue()
    assert "metadata" not in stream.getvalue()
    for event in map(json.loads, stream.getvalue().splitlines()):
        if event["event_name"].startswith("context_source_version."):
            assert event["source_id"] == str(source_id)
            assert event["version_no"] in {1, 2}


def test_repository_failure_is_mapped_to_safe_structured_event() -> None:
    repository = FakeContextSourceRepository()
    repository.fail = True
    stream = StringIO()
    context = _context()
    service = _service(repository, stream, [uuid4()])

    async def scenario() -> None:
        with bind_trace_context(_trace()), pytest.raises(ContextSourceRepositoryError):
            await service.create_source(
                context,
                CreateContextSourceCommand(
                    project_id=uuid4(), source_type="text", raw_text="do not log"
                ),
            )

    asyncio.run(scenario())
    event = json.loads(stream.getvalue().splitlines()[-1])
    assert event["event_name"] == "context_source.repository_failed"
    assert event["error_code"] == "CONTEXT_SOURCE_REPOSITORY_FAILURE"
    assert "do not log" not in stream.getvalue()
