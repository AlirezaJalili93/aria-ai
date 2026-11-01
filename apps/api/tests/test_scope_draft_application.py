from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.scope.application.ports import ScopeDraftEditTarget
from app.modules.scope.application.scope_draft_service import (
    ScopeDraftAccessNotFound,
    ScopeDraftEditConflict,
    ScopeDraftService,
    ScopeDraftStale,
    UpdateScopeSectionCommand,
)
from app.modules.scope.domain.scope_draft import SECTION_IDS, ScopeDraft

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
        updated_by_type="system",
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


class FakeRepository:
    def __init__(self, draft: ScopeDraft | None, *, current_version: int = 2) -> None:
        self.draft = draft
        self.current_version = current_version
        self.update_kwargs: dict[str, object] | None = None

    async def get_current(self, **_: object) -> ScopeDraft | None:
        if self.draft and self.draft.context_version == self.current_version:
            return self.draft
        return None

    async def get_edit_target(self, **_: object) -> ScopeDraftEditTarget:
        return ScopeDraftEditTarget(self.current_version, self.draft)

    async def update(self, **kwargs: object) -> ScopeDraft:
        self.update_kwargs = kwargs
        assert self.draft is not None
        self.draft = ScopeDraft(
            id=self.draft.id,
            account_id=self.draft.account_id,
            project_id=self.draft.project_id,
            context_version=self.draft.context_version,
            content=kwargs["content"],
            updated_by_type="user",
            updated_by=SUBJECT,
            created_at=self.draft.created_at,
            updated_at=self.draft.updated_at + timedelta(seconds=1),
        )
        return self.draft


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


def _service(repository: FakeRepository, logger: FakeLogger) -> ScopeDraftService:
    return ScopeDraftService(lambda: FakeUnitOfWork(repository), logger)  # type: ignore[arg-type]


def _trace():
    return bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    )


def test_get_current_and_update_one_section_preserve_all_other_state() -> None:
    draft = _draft()
    summary = next(s for s in draft.content["sections"] if s["section_id"] == "summary")
    summary["trace"]["context_item_ids"] = [str(uuid4())]
    repository = FakeRepository(draft)
    logger = FakeLogger([])
    service = _service(repository, logger)

    with _trace():
        fetched = asyncio.run(service.get_current(_context(), project_id=PROJECT_ID))
        updated = asyncio.run(
            service.update_section(
                _context(),
                project_id=PROJECT_ID,
                section_id="summary",
                command=UpdateScopeSectionCommand("خلاصه ویرایش‌شده", NOW),
            )
        )

    assert fetched.id == draft.id
    updated_summary = next(
        s for s in updated.content["sections"] if s["section_id"] == "summary"
    )
    assert updated_summary["value"] == "خلاصه ویرایش‌شده"
    assert updated_summary["trace"] == summary["trace"]
    assert repository.update_kwargs is not None
    assert repository.update_kwargs["updated_by"] == SUBJECT
    assert logger.events[-1][0] == "scope_draft.section_updated"
    assert "content" not in logger.events[-1][1]


def test_stale_and_version_conflict_are_distinct_and_do_not_write() -> None:
    draft = _draft()
    stale_repository = FakeRepository(draft, current_version=3)
    stale_logger = FakeLogger([])
    with _trace(), pytest.raises(ScopeDraftStale):
        asyncio.run(
            _service(stale_repository, stale_logger).update_section(
                _context(),
                project_id=PROJECT_ID,
                section_id="summary",
                command=UpdateScopeSectionCommand("تغییر", NOW),
            )
        )
    assert stale_repository.update_kwargs is None
    assert stale_logger.events[-1][0] == "scope_draft.stale_rejected"

    conflict_repository = FakeRepository(draft)
    conflict_logger = FakeLogger([])
    with _trace(), pytest.raises(ScopeDraftEditConflict):
        asyncio.run(
            _service(conflict_repository, conflict_logger).update_section(
                _context(),
                project_id=PROJECT_ID,
                section_id="summary",
                command=UpdateScopeSectionCommand(
                    "تغییر", NOW - timedelta(seconds=1)
                ),
            )
        )
    assert conflict_repository.update_kwargs is None
    assert conflict_logger.events[-1][0] == "scope_draft.version_conflict"


def test_missing_current_draft_is_safe_not_found() -> None:
    with _trace(), pytest.raises(ScopeDraftAccessNotFound):
        asyncio.run(
            _service(FakeRepository(None), FakeLogger([])).get_current(
                _context(), project_id=PROJECT_ID
            )
        )
