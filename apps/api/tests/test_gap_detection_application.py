from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.gap_detection import (
    CandidateGap,
    CandidateGapBatch,
    CriticalGapRuleEvaluation,
    DetectGapsCommand,
    DetectGapsUseCase,
    GapAffectedRequirementError,
    GapContextItem,
    GapDetectionError,
    GapDetectionReplay,
    GapDetectionSnapshot,
    GapDuplicateError,
    GapRepairPolicy,
    GapRequirement,
    GapSnapshotChangedError,
    GapSnapshotRevisions,
    GapSourceReference,
    RequirementRevision,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)


class FakeAI:
    def __init__(self, *batches: CandidateGapBatch) -> None:
        self.batches = list(batches)
        self.calls = 0

    async def execute_structured(self, **_: object) -> StructuredAIResponse:
        batch = self.batches[self.calls]
        self.calls += 1
        return StructuredAIResponse(
            data=batch,
            provider_attempt_id=uuid4(),
            provider="fake",
            model="fake-model",
            provider_request_id=f"request-{self.calls}",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            latency_ms=10,
            retry_no=0,
            workflow_version="workflow-v1",
            prompt_version="prompt-v1",
            estimated_cost=0.01,
            status="success",
        )


class FakeLedger:
    def __init__(self) -> None:
        self.records = []

    async def append(self, record) -> None:
        self.records.append(record)


class FakeCriticalRules:
    def __init__(self, indexes: tuple[int, ...] = ()) -> None:
        self.indexes = indexes
        self.calls = 0

    async def evaluate(self, **_: object) -> CriticalGapRuleEvaluation:
        self.calls += 1
        return CriticalGapRuleEvaluation(self.indexes)


class FakeSnapshotReader:
    def __init__(self, snapshot: GapDetectionSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    async def resolve_exact(self, **_: object) -> GapDetectionSnapshot:
        self.calls += 1
        return self.snapshot


class FakeRepository:
    def __init__(self, snapshot: GapDetectionSnapshot) -> None:
        self.replay: GapDetectionReplay | None = None
        self.locked = GapSnapshotRevisions(
            project_type=snapshot.project_type,
            context_item_revisions=snapshot.context_item_revisions,
            requirement_revisions=snapshot.requirement_revisions,
        )
        self.pending_writes = []
        self.committed_writes = []
        self.pending_gap_count: int | None = None
        self.committed_gap_count: int | None = None

    async def resolve_replay(self, **_: object):
        return self.replay

    async def lock_snapshot_and_resolve_revisions(self, **_: object):
        return self.locked

    async def add_batch(self, gaps) -> None:
        self.pending_writes.extend(gaps)

    async def mark_job_succeeded(self, *, gap_count: int, **_: object) -> None:
        self.pending_gap_count = gap_count

    def commit(self) -> None:
        self.committed_writes.extend(self.pending_writes)
        self.pending_writes.clear()
        self.committed_gap_count = self.pending_gap_count
        self.pending_gap_count = None

    def rollback(self) -> None:
        self.pending_writes.clear()
        self.pending_gap_count = None


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc_type, traceback
        if exc is not None or not self.committed:
            self.repository.rollback()

    async def commit(self) -> None:
        self.repository.commit()
        self.committed = True


class FakeUnitOfWorkFactory:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository

    def __call__(self):
        return FakeUnitOfWork(self.repository)


class RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        self.events.append((event_name, {"level": level, **fields}))


def _fixture() -> tuple[dict[str, UUID], GapDetectionSnapshot, GapSourceReference, CandidateGap]:
    values = {
        "account": uuid4(),
        "project": uuid4(),
        "job": uuid4(),
        "correlation": uuid4(),
        "context_item": uuid4(),
        "requirement": uuid4(),
        "source": uuid4(),
        "source_version": uuid4(),
    }
    reference = GapSourceReference(values["source"], values["source_version"])
    snapshot = GapDetectionSnapshot(
        project_type="landing",
        context_version=1,
        completion_checklist_version="checklist-v1",
        context_items=(
            GapContextItem(
                id=values["context_item"],
                updated_at=NOW,
                item_type="fact",
                status="confirmed",
                content="متن کانتکست",
                source_refs=(reference,),
            ),
        ),
        requirements=(
            GapRequirement(
                id=values["requirement"],
                updated_at=NOW,
                category="functional",
                title="عنوان نیازمندی",
                description="شرح نیازمندی",
                priority="must",
                status="confirmed",
                source_refs=(reference,),
            ),
        ),
    )
    candidate = CandidateGap(
        gap_type="ambiguity",
        severity="critical",
        explanation="ابهام شناسایی شد",
        source_refs=(reference,),
        affected_requirement_ids=(values["requirement"],),
        suggested_resolution_type="clarify_ambiguity",
    )
    return values, snapshot, reference, candidate


def _command(values: dict[str, UUID], snapshot: GapDetectionSnapshot) -> DetectGapsCommand:
    return DetectGapsCommand(
        account_id=values["account"],
        project_id=values["project"],
        job_id=values["job"],
        correlation_id=values["correlation"],
        context_version=1,
        context_item_revisions=snapshot.context_item_revisions,
        requirement_revisions=snapshot.requirement_revisions,
        completion_checklist_version="checklist-v1",
        critical_rule_pack_version="critical-gap-rules-v1",
        task_type="opaque-gap-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        repair_prompt_version="repair-v1",
        repair_policy=GapRepairPolicy(policy_version="repair-policy-v1", max_repairs=0),
        pricing_version="pricing-v1",
        output_schema={},
        routing_policy={},
        cost_budget={},
        timeout_policy={},
    )


def _service(snapshot, repository, ai, ledger, critical, logger):
    ids = iter([UUID(int=101), UUID(int=102), UUID(int=103)])
    return DetectGapsUseCase(
        snapshot_reader=FakeSnapshotReader(snapshot),
        ai_execution=ai,
        usage_ledger=ledger,
        critical_rule_evaluator=critical,
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=logger,
        id_factory=lambda: next(ids),
        wall_clock=lambda: NOW,
        monotonic_clock=lambda: 1.0,
    )


def test_empty_batch_is_successful_and_replayable_metadata_is_committed() -> None:
    values, snapshot, _, _ = _fixture()
    repository = FakeRepository(snapshot)
    ai, ledger = FakeAI(CandidateGapBatch(())), FakeLedger()
    critical, logger = FakeCriticalRules(), RecordingLogger()
    result = asyncio.run(
        _service(snapshot, repository, ai, ledger, critical, logger).execute(
            _command(values, snapshot)
        )
    )

    assert result.gap_count == 0
    assert repository.committed_writes == []
    assert repository.committed_gap_count == 0
    assert ai.calls == critical.calls == len(ledger.records) == 1
    assert logger.events[-1][0] == "gap.detection_completed"


def test_model_critical_is_not_authoritative_without_rule_match() -> None:
    values, snapshot, _, candidate = _fixture()
    repository = FakeRepository(snapshot)
    ai, ledger = FakeAI(CandidateGapBatch((candidate,))), FakeLedger()
    result = asyncio.run(
        _service(snapshot, repository, ai, ledger, FakeCriticalRules(), RecordingLogger()).execute(
            _command(values, snapshot)
        )
    )

    assert result.critical_candidate_count == 1
    assert result.authoritative_critical_gap_ids == ()
    assert repository.committed_writes[0].severity == "high"
    assert repository.committed_writes[0].affected_requirement_ids == (values["requirement"],)


def test_exact_duplicate_rejects_the_entire_batch_without_writes() -> None:
    values, snapshot, _, candidate = _fixture()
    repository = FakeRepository(snapshot)
    logger = RecordingLogger()
    service = _service(
        snapshot,
        repository,
        FakeAI(CandidateGapBatch((candidate, candidate))),
        FakeLedger(),
        FakeCriticalRules(),
        logger,
    )

    with pytest.raises(GapDuplicateError):
        asyncio.run(service.execute(_command(values, snapshot)))
    assert repository.committed_writes == []
    assert any(name == "gap.duplicate_rejected" for name, _ in logger.events)


def test_affected_requirement_outside_snapshot_is_rejected_atomically() -> None:
    values, snapshot, reference, _ = _fixture()
    candidate = CandidateGap(
        gap_type="scope_risk",
        severity="high",
        explanation="ریسک دامنه",
        source_refs=(reference,),
        affected_requirement_ids=(uuid4(),),
        suggested_resolution_type="mitigate_scope_risk",
    )
    repository = FakeRepository(snapshot)
    service = _service(
        snapshot,
        repository,
        FakeAI(CandidateGapBatch((candidate,))),
        FakeLedger(),
        FakeCriticalRules(),
        RecordingLogger(),
    )
    with pytest.raises(GapAffectedRequirementError):
        asyncio.run(service.execute(_command(values, snapshot)))
    assert repository.committed_writes == []


def test_snapshot_membership_or_revision_change_rolls_back_all_writes() -> None:
    values, snapshot, _, candidate = _fixture()
    repository = FakeRepository(snapshot)
    repository.locked = GapSnapshotRevisions(
        project_type=snapshot.project_type,
        context_item_revisions=snapshot.context_item_revisions,
        requirement_revisions=(RequirementRevision(values["requirement"], NOW.replace(day=10)),),
    )
    logger = RecordingLogger()
    service = _service(
        snapshot,
        repository,
        FakeAI(CandidateGapBatch((candidate,))),
        FakeLedger(),
        FakeCriticalRules(),
        logger,
    )
    with pytest.raises(GapSnapshotChangedError):
        asyncio.run(service.execute(_command(values, snapshot)))
    assert repository.committed_writes == []
    assert repository.committed_gap_count is None
    assert any(name == "gap.snapshot_changed" for name, _ in logger.events)


def test_successful_empty_replay_bypasses_snapshot_ai_usage_and_writes() -> None:
    values, snapshot, _, _ = _fixture()
    repository = FakeRepository(snapshot)
    repository.replay = GapDetectionReplay("succeeded", (), 0, 0, None)
    ai, ledger = FakeAI(CandidateGapBatch(())), FakeLedger()
    critical, logger = FakeCriticalRules(), RecordingLogger()
    reader = FakeSnapshotReader(snapshot)
    service = DetectGapsUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=ledger,
        critical_rule_evaluator=critical,
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=logger,
    )
    result = asyncio.run(service.execute(_command(values, snapshot)))

    assert result.replayed is True and result.gap_count == 0
    assert reader.calls == ai.calls == critical.calls == len(ledger.records) == 0
    assert repository.committed_writes == []
    assert logger.events[-1][0] == "gap.replay_served"


def test_duplicate_batch_can_be_repaired_once_and_each_call_is_metered() -> None:
    values, snapshot, _, candidate = _fixture()
    repository = FakeRepository(snapshot)
    ai = FakeAI(
        CandidateGapBatch((candidate, candidate)),
        CandidateGapBatch((candidate,)),
    )
    ledger, logger = FakeLedger(), RecordingLogger()
    command_value = replace(
        _command(values, snapshot),
        repair_policy=GapRepairPolicy(policy_version="repair-policy-v1", max_repairs=1),
    )
    result = asyncio.run(
        _service(snapshot, repository, ai, ledger, FakeCriticalRules(), logger).execute(
            command_value
        )
    )

    assert result.gap_count == 1
    assert ai.calls == len(ledger.records) == 2
    assert sum(name == "gap.duplicate_rejected" for name, _ in logger.events) == 1


def test_failed_terminal_replay_returns_safe_error_without_side_effects() -> None:
    values, snapshot, _, _ = _fixture()
    repository = FakeRepository(snapshot)
    repository.replay = GapDetectionReplay("failed", (), None, None, "INSUFFICIENT_CONTEXT")
    ai, ledger = FakeAI(CandidateGapBatch(())), FakeLedger()
    critical, logger = FakeCriticalRules(), RecordingLogger()
    service = _service(snapshot, repository, ai, ledger, critical, logger)

    with pytest.raises(GapDetectionError) as raised:
        asyncio.run(service.execute(_command(values, snapshot)))
    assert raised.value.reason_code == "INSUFFICIENT_CONTEXT"
    assert ai.calls == critical.calls == len(ledger.records) == 0
    assert repository.committed_writes == []
