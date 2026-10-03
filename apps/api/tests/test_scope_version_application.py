from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_version_service import (
    CreateScopeVersionCommand,
    ScopeVersionAccessNotFound,
    ScopeVersionCreateConflict,
    ScopeVersionIdempotencyConflict,
    ScopeVersionNotReady,
    ScopeVersionService,
    ScopeVersionUnchanged,
)
from app.modules.scope.application.version_ports import (
    ScopeVersionCreateReservation,
    ScopeVersionFreezeTarget,
)
from app.modules.scope.domain.readiness import ScopeReadinessGap
from app.modules.scope.domain.scope_draft import SECTION_IDS, ScopeDraft
from app.modules.scope.domain.scope_version import ScopeVersion, hash_scope_snapshot

ACCOUNT_ID, PROJECT_ID, SUBJECT = uuid4(), uuid4(), uuid4()
NOW = datetime.now(UTC)


def _content() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


def _draft() -> ScopeDraft:
    return ScopeDraft(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=2,
        content=_content(),
        updated_by_type="user",
        updated_by=SUBJECT,
        created_at=NOW,
        updated_at=NOW,
    )


def _context() -> TenantContext:
    return TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _version(version_no: int = 1) -> ScopeVersion:
    data = _content()
    return ScopeVersion(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        version_no=version_no,
        context_version=2,
        status="awaiting_approval",
        snapshot_data=data,
        snapshot_hash=hash_scope_snapshot(data),
        created_by=SUBJECT,
        created_at=NOW,
    )


class FakeRepository:
    def __init__(self, target: ScopeVersionFreezeTarget | None) -> None:
        self.target = target
        self.reservation = ScopeVersionCreateReservation(
            acquired=True,
            request_hash="",
            scope_version_id=uuid4(),
            response=None,
        )
        self.added = None
        self.completed = False
        self.target_calls = 0
        self.rows: tuple[ScopeVersion, ...] = ()

    async def reserve_create(self, **kwargs: object) -> ScopeVersionCreateReservation:
        self.reservation = ScopeVersionCreateReservation(
            acquired=self.reservation.acquired,
            request_hash=self.reservation.request_hash or str(kwargs["request_hash"]),
            scope_version_id=self.reservation.scope_version_id,
            response=self.reservation.response,
        )
        return self.reservation

    async def get_freeze_target(self, **_: object) -> ScopeVersionFreezeTarget | None:
        self.target_calls += 1
        return self.target

    async def add(self, version):
        self.added = version
        persisted = ScopeVersion(
            id=version.id,
            account_id=version.account_id,
            project_id=version.project_id,
            version_no=version.version_no,
            context_version=version.context_version,
            status=version.status,
            snapshot_data=version.snapshot_data,
            snapshot_hash=version.snapshot_hash,
            created_by=version.created_by,
            created_at=NOW,
        )
        self.rows = (persisted, *self.rows)
        return persisted

    async def complete_create_reservation(self, **_: object) -> None:
        self.completed = True

    async def get(self, **kwargs: object) -> ScopeVersion | None:
        return next((row for row in self.rows if row.version_no == kwargs["version_no"]), None)

    async def list(self, **_: object) -> tuple[ScopeVersion, ...]:
        return self.rows


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


@dataclass
class FakeLogger:
    events: list[tuple[str, dict[str, object]]]

    def emit(self, event_name: str, **fields: object) -> None:
        self.events.append((event_name, fields))


def _target(
    *,
    draft: ScopeDraft | None = None,
    gaps: tuple[ScopeReadinessGap, ...] = (),
    latest_hash: str | None = None,
) -> ScopeVersionFreezeTarget:
    return ScopeVersionFreezeTarget(
        project_current_context_version=2,
        draft=draft or _draft(),
        gaps=gaps,
        latest_snapshot_hash=latest_hash,
        next_version_no=1,
    )


def _trace():
    return bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4())))


def _service(repository: FakeRepository, logger: FakeLogger) -> ScopeVersionService:
    return ScopeVersionService(lambda: FakeUnitOfWork(repository), logger)  # type: ignore[arg-type]


def test_create_freezes_exact_ready_current_draft() -> None:
    repository = FakeRepository(_target())
    logger = FakeLogger([])
    with _trace():
        version = asyncio.run(
            _service(repository, logger).create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "freeze-1"),
            )
        )

    assert version.version_no == 1
    assert version.status == "awaiting_approval"
    assert version.snapshot_data == _content()
    assert version.snapshot_data is not repository.target.draft.content
    assert repository.completed is True
    created_event = next(
        fields for name, fields in logger.events if name == "scope_version.created"
    )
    assert "snapshot_data" not in created_event
    assert "snapshot_hash" not in created_event


def test_missing_stale_not_ready_and_unchanged_are_distinct() -> None:
    missing = FakeRepository(None)
    with _trace(), pytest.raises(ScopeVersionAccessNotFound):
        asyncio.run(
            _service(missing, FakeLogger([])).create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "missing"),
            )
        )

    stale = FakeRepository(_target())
    with _trace(), pytest.raises(ScopeVersionCreateConflict):
        asyncio.run(
            _service(stale, FakeLogger([])).create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW - timedelta(seconds=1), "stale"),
            )
        )

    blocking = ScopeReadinessGap(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=2,
        severity="critical",
        status="open",
    )
    not_ready = FakeRepository(_target(gaps=(blocking,)))
    with _trace(), pytest.raises(ScopeVersionNotReady):
        asyncio.run(
            _service(not_ready, FakeLogger([])).create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "blocked"),
            )
        )

    duplicate = FakeRepository(_target(latest_hash=hash_scope_snapshot(_content())))
    with _trace(), pytest.raises(ScopeVersionUnchanged):
        asyncio.run(
            _service(duplicate, FakeLogger([])).create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "duplicate"),
            )
        )


def test_idempotency_precedes_snapshot_duplicate_detection() -> None:
    replayed = _version()
    repository = FakeRepository(_target(latest_hash=replayed.snapshot_hash))
    repository.reservation = ScopeVersionCreateReservation(
        acquired=False,
        request_hash="expected",
        scope_version_id=replayed.id,
        response=replayed,
    )
    service = _service(repository, FakeLogger([]))
    request_hash = service.request_hash(PROJECT_ID, NOW)
    repository.reservation = ScopeVersionCreateReservation(
        acquired=False,
        request_hash=request_hash,
        scope_version_id=replayed.id,
        response=replayed,
    )
    with _trace():
        result = asyncio.run(
            service.create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "replay"),
            )
        )
    assert result == replayed
    assert repository.target_calls == 0

    repository.reservation = ScopeVersionCreateReservation(
        acquired=False,
        request_hash="different",
        scope_version_id=replayed.id,
        response=replayed,
    )
    with _trace(), pytest.raises(ScopeVersionIdempotencyConflict):
        asyncio.run(
            service.create(
                _context(),
                project_id=PROJECT_ID,
                command=CreateScopeVersionCommand(NOW, "replay"),
            )
        )


def test_tenant_scoped_get_and_list_return_only_repository_results() -> None:
    first, second = _version(1), _version(2)
    repository = FakeRepository(_target())
    repository.rows = (second, first)
    service = _service(repository, FakeLogger([]))
    with _trace():
        listed = asyncio.run(
            service.list(_context(), project_id=PROJECT_ID, limit=21, before_version_no=None)
        )
        fetched = asyncio.run(service.get(_context(), project_id=PROJECT_ID, version_no=1))
        with pytest.raises(ScopeVersionAccessNotFound):
            asyncio.run(service.get(_context(), project_id=PROJECT_ID, version_no=3))
    assert listed == (second, first)
    assert fetched == first
