from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.requirements_generation import (
    RequirementContextItem,
    RequirementContextSnapshot,
    RequirementSourceReference,
)
from aria_observability import create_event_logger

from app.modules.requirements.application.generation_jobs import (
    ExplicitSyntheticRequirementGenerationProjects,
    RequirementGenerationSyntheticFixtureRequired,
    ScheduleRequirementGenerationCommand,
    ScheduleRequirementGenerationUseCase,
)


class _SnapshotReader:
    def __init__(self, snapshot: RequirementContextSnapshot) -> None:
        self.snapshot = snapshot

    async def resolve_exact(self, **_: object) -> RequirementContextSnapshot:
        return self.snapshot


class _Collector:
    def __init__(self) -> None:
        self.values: list[object] = []

    async def add(self, value: object) -> None:
        self.values.append(value)


class _UnitOfWork:
    def __init__(self) -> None:
        self.jobs = _Collector()
        self.outbox = _Collector()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _snapshot() -> RequirementContextSnapshot:
    source_id, version_id = uuid4(), uuid4()
    return RequirementContextSnapshot(
        project_type="landing",
        context_version=2,
        items=(
            RequirementContextItem(
                id=uuid4(),
                updated_at=datetime(2026, 9, 22, tzinfo=UTC),
                item_type="fact",
                status="confirmed",
                content="synthetic fixture",
                source_refs=(RequirementSourceReference(source_id, version_id),),
            ),
        ),
    )


def test_internal_scheduler_binds_exact_revision_and_identifier_only_outbox() -> None:
    account_id, project_id = uuid4(), uuid4()
    uow = _UnitOfWork()
    ids = iter((uuid4(), uuid4()))
    service = ScheduleRequirementGenerationUseCase(
        snapshot_reader=_SnapshotReader(_snapshot()),
        unit_of_work_factory=lambda: uow,  # type: ignore[arg-type]
        synthetic_authorizer=ExplicitSyntheticRequirementGenerationProjects(
            frozenset({(account_id, project_id)})
        ),
        event_logger=create_event_logger(
            service="aria-api",
            environment="test",
            app_version="0.1.0",
            release_commit_sha=None,
            level="INFO",
            stream=StringIO(),
        ),
        id_factory=lambda: next(ids),
    )
    result = asyncio.run(
        service.execute(
            ScheduleRequirementGenerationCommand(
                account_id=account_id,
                project_id=project_id,
                context_version=2,
                correlation_id=uuid4(),
            )
        )
    )
    job = uow.jobs.values[0]
    event = uow.outbox.values[0]
    assert uow.committed is True
    assert job.id == result.job_id  # type: ignore[attr-defined]
    assert job.job_type == "requirement_generation"  # type: ignore[attr-defined]
    assert job.max_attempts == 1  # type: ignore[attr-defined]
    assert job.payload_ref["context_version"] == 2  # type: ignore[attr-defined,index]
    assert len(job.payload_ref["context_item_revisions"]) == 1  # type: ignore[attr-defined,index]
    assert event.payload == {  # type: ignore[attr-defined]
        "jobId": str(result.job_id),
        "taskType": "requirement_generation",
        "payloadVersion": "1",
    }
    assert "content" not in str(event.payload).lower()  # type: ignore[attr-defined]


def test_internal_scheduler_is_fail_closed_for_unapproved_project() -> None:
    with pytest.raises(RequirementGenerationSyntheticFixtureRequired):
        asyncio.run(
            ScheduleRequirementGenerationUseCase(
                snapshot_reader=_SnapshotReader(_snapshot()),
                unit_of_work_factory=lambda: _UnitOfWork(),  # type: ignore[arg-type]
                synthetic_authorizer=ExplicitSyntheticRequirementGenerationProjects(
                    frozenset()
                ),
                event_logger=create_event_logger(
                    service="aria-api",
                    environment="test",
                    app_version="0.1.0",
                    release_commit_sha=None,
                    level="INFO",
                    stream=StringIO(),
                ),
            ).execute(
                ScheduleRequirementGenerationCommand(
                    account_id=uuid4(),
                    project_id=uuid4(),
                    context_version=1,
                    correlation_id=uuid4(),
                )
            )
        )
