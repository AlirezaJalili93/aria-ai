from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.scope_revision_ports import (
    ScopeRevisionReservation,
    ScopeRevisionTarget,
)
from app.modules.scope.application.scope_revision_service import (
    CreateScopeRevisionCommand,
    ScopeRevisionIdempotencyConflict,
    ScopeRevisionNotReady,
    ScopeRevisionService,
    ScopeRevisionStale,
    ScopeRevisionUnchanged,
    ScopeRevisionVersionConflict,
)
from app.modules.scope.domain.readiness import ScopeReadinessGap
from app.modules.scope.domain.scope_draft import SECTION_IDS, ScopeDraft
from app.modules.scope.domain.scope_version import ScopeVersion, hash_scope_snapshot

ACCOUNT_ID, PROJECT_ID, SUBJECT = uuid4(), uuid4(), uuid4()
TARGET_ID, CHANGE_REQUEST_ID = uuid4(), uuid4()
NOW = datetime.now(UTC)


def _content(summary: str = "نسخه نخست") -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": summary
                if section_id == "summary"
                else ("" if section_id == "visual_direction" else []),
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


def _version(*, status: str = "changes_requested", content=None) -> ScopeVersion:
    snapshot = content or _content()
    return ScopeVersion(
        id=TARGET_ID,
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        version_no=1,
        context_version=2,
        status=status,  # type: ignore[arg-type]
        snapshot_data=snapshot,
        snapshot_hash=hash_scope_snapshot(snapshot),
        created_by=SUBJECT,
        created_at=NOW,
    )


def _draft(*, content=None, updated_at: datetime = NOW) -> ScopeDraft:
    return ScopeDraft(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=2,
        content=content or _content("نسخه اصلاح‌شده"),
        updated_by_type="user",
        updated_by=SUBJECT,
        created_at=NOW,
        updated_at=updated_at,
    )


def _target(
    *,
    draft: ScopeDraft | None = None,
    latest_id=TARGET_ID,
    change_request_scope_id=TARGET_ID,
    consumed: bool = False,
    gaps: tuple[ScopeReadinessGap, ...] = (),
) -> ScopeRevisionTarget:
    return ScopeRevisionTarget(
        project_current_context_version=2,
        target=_version(),
        latest_scope_version_id=latest_id,
        change_request_scope_version_id=change_request_scope_id,
        change_request_consumed=consumed,
        draft=draft or _draft(),
        gaps=gaps,
    )


class FakeRepository:
    def __init__(self, target: ScopeRevisionTarget | None) -> None:
        self.target = target
        self.visible = _version()
        self.reservation = ScopeRevisionReservation(
            acquired=True,
            request_hash="",
            scope_version_id=uuid4(),
            response=None,
        )
        self.added = None
        self.superseded = False
        self.completed = False
        self.target_calls = 0

    async def lock_visible_target(self, **_: object):
        return self.visible

    async def reserve_revision(self, **kwargs: object):
        self.reservation = ScopeRevisionReservation(
            acquired=self.reservation.acquired,
            request_hash=self.reservation.request_hash or str(kwargs["request_hash"]),
            scope_version_id=self.reservation.scope_version_id,
            response=self.reservation.response,
        )
        return self.reservation

    async def get_revision_target(self, **_: object):
        self.target_calls += 1
        return self.target

    async def add_revision(self, version):
        self.added = version
        return ScopeVersion(
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
            revision_of_scope_version_id=version.revision_of_scope_version_id,
            change_request_id=version.change_request_id,
        )

    async def supersede_target(self, **_: object) -> None:
        self.superseded = True

    async def complete_revision_reservation(self, **_: object) -> None:
        self.completed = True


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


def _context() -> TenantContext:
    return TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _command(*, at: datetime = NOW, key: str = "revise-1") -> CreateScopeRevisionCommand:
    return CreateScopeRevisionCommand(CHANGE_REQUEST_ID, at, key)


def _service(repository: FakeRepository) -> ScopeRevisionService:
    return ScopeRevisionService(
        lambda: FakeUnitOfWork(repository), FakeLogger([])  # type: ignore[arg-type]
    )


def _trace():
    return bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4())))


def test_revision_snapshots_draft_and_persists_exact_lineage() -> None:
    repository = FakeRepository(_target())
    with _trace():
        result = asyncio.run(
            _service(repository).create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )
    assert result.replayed is False
    assert result.version.version_no == 2
    assert result.version.status == "awaiting_approval"
    assert result.version.revision_of_scope_version_id == TARGET_ID
    assert result.version.change_request_id == CHANGE_REQUEST_ID
    assert repository.superseded is True
    assert repository.completed is True


def test_revision_replay_precedes_stale_state_and_changed_semantics_conflicts() -> None:
    revision = ScopeVersion(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        version_no=2,
        context_version=2,
        status="awaiting_approval",
        snapshot_data=_content("اصلاح"),
        snapshot_hash=hash_scope_snapshot(_content("اصلاح")),
        created_by=SUBJECT,
        created_at=NOW,
        revision_of_scope_version_id=TARGET_ID,
        change_request_id=CHANGE_REQUEST_ID,
    )
    repository = FakeRepository(_target(latest_id=revision.id, consumed=True))
    service = _service(repository)
    request_hash = service.request_hash(PROJECT_ID, 1, _command())
    repository.reservation = ScopeRevisionReservation(
        acquired=False,
        request_hash=request_hash,
        scope_version_id=revision.id,
        response=revision,
    )
    with _trace():
        replay = asyncio.run(
            service.create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )
    assert replay.replayed is True
    assert replay.version == revision
    assert repository.target_calls == 0

    repository.reservation = ScopeRevisionReservation(
        acquired=False,
        request_hash="different",
        scope_version_id=revision.id,
        response=revision,
    )
    with _trace(), pytest.raises(ScopeRevisionIdempotencyConflict):
        asyncio.run(
            service.create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )


def test_revision_stale_cas_readiness_and_unchanged_are_distinct() -> None:
    with _trace(), pytest.raises(ScopeRevisionStale):
        asyncio.run(
            _service(FakeRepository(_target(latest_id=uuid4()))).create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )

    with _trace(), pytest.raises(ScopeRevisionVersionConflict):
        asyncio.run(
            _service(FakeRepository(_target())).create(
                _context(),
                project_id=PROJECT_ID,
                target_version_no=1,
                command=_command(at=NOW - timedelta(seconds=1)),
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
    with _trace(), pytest.raises(ScopeRevisionNotReady):
        asyncio.run(
            _service(FakeRepository(_target(gaps=(blocking,)))).create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )

    unchanged = _draft(content=deepcopy(_version().snapshot_data))
    with _trace(), pytest.raises(ScopeRevisionUnchanged):
        asyncio.run(
            _service(FakeRepository(_target(draft=unchanged))).create(
                _context(), project_id=PROJECT_ID, target_version_no=1, command=_command()
            )
        )
