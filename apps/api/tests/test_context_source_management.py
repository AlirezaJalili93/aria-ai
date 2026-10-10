from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.context_source_management import (
    ContextSourceBusy,
    ContextSourceManagementService,
    ContextSourceNotFound,
    ContextSourceView,
)
from app.modules.identity.application.tenant_context import TenantContext


class FakeRepository:
    def __init__(self, row: ContextSourceView) -> None:
        self.row: ContextSourceView | None = row
        self.project_visible = True
        self.active_job = False
        self.archives = 0

    async def project_exists(self, **values) -> bool:
        del values
        return self.project_visible

    async def list_sources(self, **values) -> tuple[ContextSourceView, ...]:
        del values
        return (self.row,) if self.row is not None and self.row.status != "deleted" else ()

    async def get_source(self, **values) -> ContextSourceView | None:
        include_deleted = bool(values.get("include_deleted", False))
        if self.row is None or (self.row.status == "deleted" and not include_deleted):
            return None
        return self.row

    async def has_active_parser_job(self, **values) -> bool:
        del values
        return self.active_job

    async def archive_source(self, **values) -> bool:
        del values
        if self.row is None or self.row.status == "deleted":
            return False
        self.row = replace(self.row, status="deleted")
        self.archives += 1
        return True


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.commits = 0

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
        self.commits += 1


def _fixture(*, role: str = "member", own: bool = True):
    now = datetime.now(UTC)
    actor_id = uuid4()
    row = ContextSourceView(
        id=uuid4(),
        source_type="text",
        status="ready",
        original_name=None,
        mime_type=None,
        created_at=now,
        updated_at=now,
        created_by=actor_id if own else uuid4(),
        latest_version=None,
        current_ready_version=None,
        latest_job=None,
    )
    repository = FakeRepository(row)
    uow = FakeUnitOfWork(repository)
    stream = StringIO()
    service = ContextSourceManagementService(
        lambda: uow,  # type: ignore[arg-type]
        create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=stream,
        ),
    )
    context = TenantContext(
        subject_id=actor_id,
        account_id=uuid4(),
        membership_id=uuid4(),
        role=role,  # type: ignore[arg-type]
        membership_status="active",
    )
    return service, repository, uow, context, row, stream


def _archive(service, context, project_id, source_id):
    async def scenario():
        with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
            return await service.archive(context, project_id=project_id, source_id=source_id)

    return asyncio.run(scenario())


def test_member_can_archive_only_own_source_and_repeat_is_idempotent() -> None:
    service, repository, uow, context, row, _ = _fixture()
    project_id = uuid4()
    _archive(service, context, project_id, row.id)
    _archive(service, context, project_id, row.id)
    assert repository.archives == 1
    assert uow.commits == 1

    service, repository, uow, context, row, _ = _fixture(own=False)
    with pytest.raises(ContextSourceNotFound):
        _archive(service, context, project_id, row.id)
    assert repository.archives == 0
    assert uow.commits == 0


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_can_archive_any_visible_source(role: str) -> None:
    service, repository, uow, context, row, _ = _fixture(role=role, own=False)
    _archive(service, context, uuid4(), row.id)
    assert repository.archives == 1
    assert uow.commits == 1


def test_active_parser_job_blocks_archive_without_mutation() -> None:
    service, repository, uow, context, row, stream = _fixture()
    repository.active_job = True
    with pytest.raises(ContextSourceBusy):
        _archive(service, context, uuid4(), row.id)
    assert repository.archives == 0
    assert uow.commits == 0
    assert "context_source.archive_blocked" in stream.getvalue()


def test_list_and_detail_compute_archive_capability_without_exposing_creator() -> None:
    async def scenario(role: str, own: bool) -> tuple[bool, bool]:
        service, _, _, context, row, _ = _fixture(role=role, own=own)
        with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
            listed = await service.list(
                context,
                project_id=uuid4(),
                limit=20,
                cursor_created_at=None,
                cursor_id=None,
            )
            detailed = await service.get(context, project_id=uuid4(), source_id=row.id)
        return listed[0].can_archive, detailed.can_archive

    assert asyncio.run(scenario("member", True)) == (True, True)
    assert asyncio.run(scenario("member", False)) == (False, False)
    assert asyncio.run(scenario("owner", False)) == (True, True)
