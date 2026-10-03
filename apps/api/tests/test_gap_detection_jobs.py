from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    GapContextItem,
    GapDetectionSnapshot,
)
from aria_observability import create_event_logger

from app.modules.gaps.application.detection_jobs import (
    ExplicitSyntheticGapDetectionProjects,
    GapDetectionContextRequired,
    GapDetectionSyntheticFixtureRequired,
    ScheduleGapDetectionCommand,
    ScheduleGapDetectionUseCase,
)


class _SnapshotReader:
    def __init__(self, snapshot: GapDetectionSnapshot | None) -> None:
        self.snapshot = snapshot

    async def resolve_exact(self, **_: object) -> GapDetectionSnapshot | None:
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


def _snapshot(*, context_items: bool = True) -> GapDetectionSnapshot:
    items = (
        (
            GapContextItem(
                id=UUID(int=10),
                updated_at=datetime(2026, 9, 22, tzinfo=UTC),
                item_type="fact",
                status="confirmed",
                content="synthetic fixture",
                source_refs=(),
            ),
        )
        if context_items
        else ()
    )
    return GapDetectionSnapshot(
        project_type="landing",
        context_version=2,
        completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
        context_items=items,
        requirements=(),
    )


def _logger():
    return create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=StringIO(),
    )


def test_internal_scheduler_pins_empty_requirement_snapshot_and_identifier_only_outbox() -> None:
    account_id, project_id = uuid4(), uuid4()
    uow = _UnitOfWork()
    ids = iter((uuid4(), uuid4()))
    service = ScheduleGapDetectionUseCase(
        snapshot_reader=_SnapshotReader(_snapshot()),
        unit_of_work_factory=lambda: uow,  # type: ignore[arg-type]
        synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(
            frozenset({(account_id, project_id)})
        ),
        event_logger=_logger(),
        id_factory=lambda: next(ids),
    )

    result = asyncio.run(
        service.execute(
            ScheduleGapDetectionCommand(
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
    assert job.job_type == "gap_detection"  # type: ignore[attr-defined]
    assert job.max_attempts == 1  # type: ignore[attr-defined]
    assert job.payload_ref == {  # type: ignore[attr-defined]
        "context_version": 2,
        "context_item_revisions": [
            {
                "context_item_id": str(UUID(int=10)),
                "updated_at": datetime(2026, 9, 22, tzinfo=UTC).isoformat(),
            }
        ],
        "requirement_revisions": [],
        "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
        "critical_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
    }
    assert event.payload == {  # type: ignore[attr-defined]
        "jobId": str(result.job_id),
        "taskType": "gap_detection",
        "payloadVersion": "1",
    }
    assert "content" not in str(event.payload).lower()  # type: ignore[attr-defined]


def test_internal_scheduler_requires_context_but_not_requirements() -> None:
    account_id, project_id = uuid4(), uuid4()
    with pytest.raises(GapDetectionContextRequired):
        asyncio.run(
            ScheduleGapDetectionUseCase(
                snapshot_reader=_SnapshotReader(_snapshot(context_items=False)),
                unit_of_work_factory=lambda: _UnitOfWork(),  # type: ignore[arg-type]
                synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(
                    frozenset({(account_id, project_id)})
                ),
                event_logger=_logger(),
            ).execute(
                ScheduleGapDetectionCommand(
                    account_id=account_id,
                    project_id=project_id,
                    context_version=2,
                    correlation_id=uuid4(),
                )
            )
        )


def test_internal_scheduler_is_fail_closed_for_unapproved_project() -> None:
    with pytest.raises(GapDetectionSyntheticFixtureRequired):
        asyncio.run(
            ScheduleGapDetectionUseCase(
                snapshot_reader=_SnapshotReader(_snapshot()),
                unit_of_work_factory=lambda: _UnitOfWork(),  # type: ignore[arg-type]
                synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(frozenset()),
                event_logger=_logger(),
            ).execute(
                ScheduleGapDetectionCommand(
                    account_id=uuid4(),
                    project_id=uuid4(),
                    context_version=2,
                    correlation_id=uuid4(),
                )
            )
        )
