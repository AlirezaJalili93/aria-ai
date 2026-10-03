from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.scope_generation import ScopeDraftAlreadyExistsError
from aria_observability import create_event_logger

from app.modules.scope.application.generation_jobs import (
    ExplicitSyntheticScopeProjects,
    ScheduleScopeGenerationCommand,
    ScheduleScopeGenerationUseCase,
    ScopeGenerationActiveJobConflict,
    ScopeGenerationInputRevision,
    ScopeGenerationPreflight,
    ScopeGenerationRequirementsRequired,
    ScopeGenerationSyntheticFixtureRequired,
)


class _Reader:
    def __init__(self, preflight: ScopeGenerationPreflight | None) -> None:
        self.preflight = preflight

    async def resolve_exact(self, **_: object) -> ScopeGenerationPreflight | None:
        return self.preflight


class _Repository:
    def __init__(self) -> None:
        self.rows: list[object] = []

    async def add(self, row: object) -> object:
        self.rows.append(row)
        return row


class _UnitOfWork:
    def __init__(self, *, fail: bool = False) -> None:
        self.jobs = _Repository()
        self.outbox = _Repository()
        self.fail = fail
        self.committed = False

    async def verify_draft_absent(self, **_: object) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        if self.fail:
            raise ScopeGenerationActiveJobConflict
        self.committed = True


def _preflight(
    *, requirements: bool = True, ready: bool = True, draft: bool = False
) -> ScopeGenerationPreflight:
    revision = ScopeGenerationInputRevision(uuid4(), datetime(2026, 9, 27, tzinfo=UTC))
    return ScopeGenerationPreflight(
        context_item_revisions=(revision,),
        requirement_revisions=(revision,) if requirements else (),
        gap_revisions=(),
        ready_for_share=ready,
        draft_exists=draft,
    )


def _setup(
    preflight: ScopeGenerationPreflight | None,
    *,
    allow: bool = True,
    uow: _UnitOfWork | None = None,
):
    account_id, project_id = uuid4(), uuid4()
    unit = uow or _UnitOfWork()
    use_case = ScheduleScopeGenerationUseCase(
        preflight_reader=_Reader(preflight),
        unit_of_work_factory=lambda: unit,
        synthetic_authorizer=ExplicitSyntheticScopeProjects(
            frozenset({(account_id, project_id)}) if allow else frozenset()
        ),
        event_logger=create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        ),
    )
    command = ScheduleScopeGenerationCommand(account_id, project_id, 1, uuid4())
    return use_case, command, unit


def test_schedule_pins_exact_revisions_and_creates_job_outbox_together() -> None:
    use_case, command, uow = _setup(_preflight())
    result = asyncio.run(use_case.execute(command))
    assert uow.committed
    job, event = uow.jobs.rows[0], uow.outbox.rows[0]
    assert job.id == result.job_id
    assert job.job_type == "scope_generation"
    assert len(job.payload_ref["context_item_revisions"]) == 1
    assert len(job.payload_ref["requirement_revisions"]) == 1
    assert job.payload_ref["gap_revisions"] == []
    assert event.event_type == "scope.generation_requested.v1"
    assert event.delivery_channel == "job_queue"
    assert set(event.payload) == {"jobId", "taskType", "payloadVersion"}


def test_empty_requirements_fail_before_job_or_outbox() -> None:
    use_case, command, uow = _setup(_preflight(requirements=False))
    with pytest.raises(ScopeGenerationRequirementsRequired) as error:
        asyncio.run(use_case.execute(command))
    assert error.value.reason_code == "SCOPE_REQUIREMENTS_REQUIRED"
    assert uow.jobs.rows == [] and uow.outbox.rows == []


def test_existing_draft_fails_before_scheduling() -> None:
    use_case, command, uow = _setup(_preflight(draft=True))
    with pytest.raises(ScopeDraftAlreadyExistsError):
        asyncio.run(use_case.execute(command))
    assert uow.jobs.rows == []


def test_synthetic_authorization_is_fail_closed() -> None:
    use_case, command, uow = _setup(_preflight(), allow=False)
    with pytest.raises(ScopeGenerationSyntheticFixtureRequired):
        asyncio.run(use_case.execute(command))
    assert uow.jobs.rows == []


def test_active_job_unique_conflict_never_commits_outbox() -> None:
    use_case, command, uow = _setup(_preflight(), uow=_UnitOfWork(fail=True))
    with pytest.raises(ScopeGenerationActiveJobConflict):
        asyncio.run(use_case.execute(command))
    assert not uow.committed
