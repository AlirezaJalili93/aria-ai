from __future__ import annotations

import asyncio
import io
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.context.application.context_item_ports import (
    ContextItemRepository,
    ContextItemUnitOfWork,
    CurrentContextItems,
    ProvenanceTarget,
)
from app.modules.context.application.context_item_service import (
    ContextItemInvalidState,
    ContextItemNotFound,
    ContextItemReviewService,
    ContextItemVersionConflict,
    ReviewContextItemCommand,
)
from app.modules.context.domain.context_item import ContextItem, NewContextItem, SourceReference
from app.modules.identity.application.tenant_context import TenantContext


class ReviewRepository(ContextItemRepository):
    def __init__(self, item: ContextItem, project_id: UUID) -> None:
        self.item = item
        self.project_id = project_id

    async def resolve_provenance(self, **kwargs: object) -> ProvenanceTarget | None:
        del kwargs
        return None

    async def add(self, item: NewContextItem) -> ContextItem:
        del item
        raise NotImplementedError

    async def list_current(self, **kwargs: object) -> CurrentContextItems | None:
        if kwargs["project_id"] != self.project_id:
            return None
        item_type = kwargs["item_type"]
        status = kwargs["status"]
        source_id = kwargs["source_id"]
        rows = [self.item]
        if item_type is not None:
            rows = [row for row in rows if row.item_type == item_type]
        if status is not None:
            rows = [row for row in rows if row.status == status]
        if source_id is not None:
            rows = [
                row
                for row in rows
                if any(reference.source_id == source_id for reference in row.source_refs)
            ]
        return CurrentContextItems(context_version=1, items=tuple(rows[: int(kwargs["limit"])]))

    async def get_current_for_update(self, **kwargs: object) -> ContextItem | None:
        if kwargs["project_id"] != self.project_id or kwargs["item_id"] != self.item.id:
            return None
        return self.item

    async def update_proposed(self, **kwargs: object) -> ContextItem | None:
        if kwargs["expected_updated_at"] != self.item.updated_at:
            return None
        now = self.item.updated_at + timedelta(seconds=1)
        self.item = replace(
            self.item,
            content=str(kwargs["content"]),
            status=str(kwargs["status"]),
            updated_at=now,
        )
        return self.item


class ReviewUnitOfWork(ContextItemUnitOfWork):
    def __init__(self, repository: ReviewRepository) -> None:
        self._repository = repository

    @property
    def repository(self) -> ContextItemRepository:
        return self._repository

    async def __aenter__(self) -> ReviewUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        return None


def _context(item: ContextItem) -> TenantContext:
    return TenantContext(
        subject_id=item.created_by or uuid4(),
        account_id=item.account_id,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _item() -> ContextItem:
    now = datetime.now(UTC)
    return ContextItem(
        id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        context_version=1,
        item_type="fact",
        content="قدیمی",
        source_refs=(SourceReference(uuid4(), uuid4(), 0, 3),),
        confidence=Decimal("0.9000"),
        status="proposed",
        created_by_type="ai",
        created_by=None,
        created_at=now,
        updated_at=now,
    )


def _service(item: ContextItem, repository: ReviewRepository) -> ContextItemReviewService:
    stream = io.StringIO()
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return ContextItemReviewService(lambda: ReviewUnitOfWork(repository), logger)


def test_review_edit_preserves_provenance_and_keeps_item_proposed() -> None:
    item = _item()
    repository = ReviewRepository(item, item.project_id)
    service = _service(item, repository)

    with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
        reviewed = asyncio.run(
            service.review(
                _context(item),
                project_id=item.project_id,
                item_id=item.id,
                command=ReviewContextItemCommand(
                    command="edit", expected_updated_at=item.updated_at, content="جدید"
                ),
            )
        )

    assert reviewed.content == "جدید"
    assert reviewed.status == "proposed"
    assert reviewed.source_refs == item.source_refs
    assert reviewed.updated_at > item.updated_at


def test_review_conflict_and_immutable_state_are_distinct() -> None:
    item = _item()
    repository = ReviewRepository(item, item.project_id)
    service = _service(item, repository)
    stale = item.updated_at - timedelta(seconds=1)
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(ContextItemVersionConflict):
        asyncio.run(
            service.review(
                _context(item),
                project_id=item.project_id,
                item_id=item.id,
                command=ReviewContextItemCommand(command="confirm", expected_updated_at=stale),
            )
        )

    repository.item = replace(item, status="confirmed")
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(ContextItemInvalidState):
        asyncio.run(
            service.review(
                _context(item),
                project_id=item.project_id,
                item_id=item.id,
                command=ReviewContextItemCommand(
                    command="reject", expected_updated_at=repository.item.updated_at
                ),
            ),
        )


def test_list_current_applies_source_filter_and_safe_not_found() -> None:
    item = _item()
    repository = ReviewRepository(item, item.project_id)
    service = _service(item, repository)
    with bind_trace_context(TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))):
        result = asyncio.run(
            service.list_current(
                _context(item),
                project_id=item.project_id,
                item_type="fact",
                status="proposed",
                source_id=item.source_refs[0].source_id,
                limit=20,
                cursor_created_at=None,
                cursor_id=None,
            )
        )
    assert result.items == (item,)
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(ContextItemNotFound):
        asyncio.run(
            service.list_current(
                _context(item),
                project_id=uuid4(),
                item_type=None,
                status=None,
                source_id=None,
                limit=20,
                cursor_created_at=None,
                cursor_id=None,
            )
        )
