from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from app.modules.context.application.context_item_ports import (
    ContextItemRepository,
    ContextItemUnitOfWork,
    ProvenanceTarget,
)
from app.modules.context.application.context_item_service import (
    ContextItemProvenanceError,
    CreateContextItemUseCase,
)
from app.modules.context.domain.context_item import ContextItem, NewContextItem, SourceReference


class FakeContextItems(ContextItemRepository):
    def __init__(self) -> None:
        self.targets: dict[tuple[UUID, UUID], ProvenanceTarget] = {}
        self.rows: list[ContextItem] = []

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> ProvenanceTarget | None:
        target = self.targets.get((source_id, source_version_id))
        if target is None or target.account_id != account_id or target.project_id != project_id:
            return None
        return target

    async def add(self, item: NewContextItem) -> ContextItem:
        values = asdict(item)
        values["source_refs"] = item.source_refs
        persisted = ContextItem(**values, created_at=datetime.now(UTC))  # type: ignore[arg-type]
        self.rows.append(persisted)
        return persisted


class FakeUnitOfWork(ContextItemUnitOfWork):
    def __init__(self, repository: FakeContextItems) -> None:
        self._repository = repository
        self.commits = 0

    @property
    def repository(self) -> ContextItemRepository:
        return self._repository

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


def _target(
    *,
    account_id: UUID,
    project_id: UUID,
    source_id: UUID,
    version_id: UUID,
    text_length: int | None,
) -> ProvenanceTarget:
    return ProvenanceTarget(
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        source_version_id=version_id,
        canonical_text_length=text_length,
    )


def _new_item(
    *, account_id: UUID, project_id: UUID, refs: tuple[SourceReference, ...]
) -> NewContextItem:
    return NewContextItem(
        id=uuid4(),
        account_id=account_id,
        project_id=project_id,
        context_version=1,
        item_type="fact",
        content="محتوای محرمانه",
        source_refs=refs,
        confidence=Decimal("0.9000"),
        status="confirmed",
        created_by_type="ai",
        created_by=None,
    )


def test_use_case_validates_ready_provenance_then_persists_atomically() -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeContextItems()
    repository.targets[(source_id, version_id)] = _target(
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
        text_length=12,
    )
    unit_of_work = FakeUnitOfWork(repository)
    item = _new_item(
        account_id=account_id,
        project_id=project_id,
        refs=(SourceReference(source_id, version_id, 0, 12),),
    )

    persisted = asyncio.run(CreateContextItemUseCase(lambda: unit_of_work).execute(item))

    assert persisted.id == item.id
    assert unit_of_work.commits == 1
    assert repository.rows == [persisted]


@pytest.mark.parametrize("case", ["missing", "cross_tenant", "offset_out_of_range", "no_text"])
def test_use_case_rejects_semantically_invalid_provenance_without_persisting(case: str) -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeContextItems()
    if case != "missing":
        repository.targets[(source_id, version_id)] = _target(
            account_id=uuid4() if case == "cross_tenant" else account_id,
            project_id=project_id,
            source_id=source_id,
            version_id=version_id,
            text_length=None if case == "no_text" else 3,
        )
    ref = SourceReference(source_id, version_id, 0, 4)
    unit_of_work = FakeUnitOfWork(repository)

    with pytest.raises(ContextItemProvenanceError):
        asyncio.run(
            CreateContextItemUseCase(lambda: unit_of_work).execute(
                _new_item(account_id=account_id, project_id=project_id, refs=(ref,))
            )
        )

    assert unit_of_work.commits == 0
    assert not repository.rows


def test_whole_version_reference_and_empty_non_fact_provenance_are_valid() -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeContextItems()
    repository.targets[(source_id, version_id)] = _target(
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        version_id=version_id,
        text_length=None,
    )
    first_uow = FakeUnitOfWork(repository)
    whole = _new_item(
        account_id=account_id,
        project_id=project_id,
        refs=(SourceReference(source_id, version_id),),
    )
    asyncio.run(CreateContextItemUseCase(lambda: first_uow).execute(whole))

    second_uow = FakeUnitOfWork(repository)
    assumption = NewContextItem(
        id=uuid4(),
        account_id=account_id,
        project_id=project_id,
        context_version=1,
        item_type="assumption",
        content="بدون provenance",
        source_refs=(),
        confidence=None,
        status="proposed",
        created_by_type="system",
        created_by=None,
    )
    asyncio.run(CreateContextItemUseCase(lambda: second_uow).execute(assumption))
    assert first_uow.commits == second_uow.commits == 1
