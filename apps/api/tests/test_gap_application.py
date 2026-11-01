from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.gaps.application.gap_service import GapProvenanceError, PersistGapUseCase
from app.modules.gaps.application.ports import (
    GapProvenanceTarget,
    GapRepository,
    GapUnitOfWork,
)
from app.modules.gaps.domain.gap import Gap, GapSourceReference, NewGap


class FakeGapRepository(GapRepository):
    def __init__(self) -> None:
        self.targets: dict[tuple[UUID, UUID], GapProvenanceTarget] = {}
        self.rows: list[Gap] = []

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> GapProvenanceTarget | None:
        target = self.targets.get((source_id, source_version_id))
        if target is None or target.account_id != account_id or target.project_id != project_id:
            return None
        return target

    async def add(self, gap: NewGap) -> Gap:
        values = asdict(gap)
        values["source_refs"] = gap.source_refs
        now = datetime.now(UTC)
        persisted = Gap(**values, created_at=now, updated_at=now)  # type: ignore[arg-type]
        self.rows.append(persisted)
        return persisted


class FakeGapUnitOfWork(GapUnitOfWork):
    def __init__(self, repository: FakeGapRepository) -> None:
        self._repository = repository
        self.commits = 0

    @property
    def repository(self) -> GapRepository:
        return self._repository

    async def __aenter__(self) -> FakeGapUnitOfWork:
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


def _gap(
    *, account_id: UUID, project_id: UUID, refs: tuple[GapSourceReference, ...] = ()
) -> NewGap:
    return NewGap(
        id=uuid4(),
        account_id=account_id,
        project_id=project_id,
        context_version=2,
        gap_type="missing_information",
        severity="critical",
        source_refs=refs,
    )


def _service(
    repository: FakeGapRepository,
) -> tuple[PersistGapUseCase, FakeGapUnitOfWork, StringIO]:
    stream = StringIO()
    unit_of_work = FakeGapUnitOfWork(repository)
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return PersistGapUseCase(lambda: unit_of_work, logger), unit_of_work, stream


def _run_with_trace(coroutine):
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        return asyncio.run(coroutine)


def test_empty_provenance_is_valid_and_creation_log_is_safe() -> None:
    account_id, project_id = uuid4(), uuid4()
    repository = FakeGapRepository()
    service, unit_of_work, stream = _service(repository)
    gap = _gap(account_id=account_id, project_id=project_id)

    persisted = _run_with_trace(service.execute(gap))

    assert persisted.id == gap.id
    assert unit_of_work.commits == 1
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "gap.created"
    assert event["account_id"] == str(account_id)
    assert event["project_id"] == str(project_id)
    assert event["gap_id"] == str(gap.id)
    assert event["gap_type"] == "missing_information"
    assert event["severity"] == "critical"
    assert "source_refs" not in event


def test_valid_same_tenant_ready_provenance_is_persisted() -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeGapRepository()
    repository.targets[(source_id, version_id)] = GapProvenanceTarget(
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        source_version_id=version_id,
        canonical_text_length=8,
    )
    service, unit_of_work, _ = _service(repository)

    persisted = _run_with_trace(
        service.execute(
            _gap(
                account_id=account_id,
                project_id=project_id,
                refs=(GapSourceReference(source_id, version_id, 0, 8),),
            )
        )
    )

    assert persisted.source_refs[0].end_offset == 8
    assert unit_of_work.commits == 1


@pytest.mark.parametrize("case", ["missing", "cross_tenant", "offset", "no_text"])
def test_invalid_provenance_rejects_the_write(case: str) -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeGapRepository()
    if case != "missing":
        repository.targets[(source_id, version_id)] = GapProvenanceTarget(
            account_id=uuid4() if case == "cross_tenant" else account_id,
            project_id=project_id,
            source_id=source_id,
            source_version_id=version_id,
            canonical_text_length=None if case == "no_text" else 3,
        )
    service, unit_of_work, _ = _service(repository)

    with pytest.raises(GapProvenanceError):
        _run_with_trace(
            service.execute(
                _gap(
                    account_id=account_id,
                    project_id=project_id,
                    refs=(GapSourceReference(source_id, version_id, 0, 4),),
                )
            )
        )

    assert not repository.rows
    assert unit_of_work.commits == 0


def test_whole_version_reference_does_not_require_inline_canonical_text() -> None:
    account_id, project_id, source_id, version_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeGapRepository()
    repository.targets[(source_id, version_id)] = GapProvenanceTarget(
        account_id=account_id,
        project_id=project_id,
        source_id=source_id,
        source_version_id=version_id,
        canonical_text_length=None,
    )
    service, unit_of_work, _ = _service(repository)
    _run_with_trace(
        service.execute(
            _gap(
                account_id=account_id,
                project_id=project_id,
                refs=(GapSourceReference(source_id, version_id),),
            )
        )
    )
    assert unit_of_work.commits == 1
