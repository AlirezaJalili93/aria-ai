from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.requirements_generation import (
    CandidateRequirement,
    CandidateRequirementBatch,
    ContextItemRevision,
    ExistingRequirement,
    GenerateRequirementsCommand,
    GenerateRequirementsUseCase,
    RequirementContextItem,
    RequirementContextSnapshot,
    RequirementDuplicateClassificationError,
    RequirementGenerationError,
    RequirementGenerationReplay,
    RequirementInsufficientContextError,
    RequirementRepairExhaustedError,
    RequirementRepairPolicy,
    RequirementSnapshotChangedError,
    RequirementSourceReference,
    RequirementSupportClassificationError,
)

ACCOUNT_ID = uuid4()
PROJECT_ID = uuid4()
JOB_ID = uuid4()
CORRELATION_ID = uuid4()
ITEM_ID = uuid4()
SOURCE_ID = uuid4()
SOURCE_VERSION_ID = uuid4()
SECOND_SOURCE_ID = uuid4()
SECOND_SOURCE_VERSION_ID = uuid4()
UPDATED_AT = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)


def _ref(*, second: bool = False) -> RequirementSourceReference:
    return RequirementSourceReference(
        source_id=SECOND_SOURCE_ID if second else SOURCE_ID,
        source_version_id=SECOND_SOURCE_VERSION_ID if second else SOURCE_VERSION_ID,
        start_offset=0,
        end_offset=4,
    )


def _snapshot() -> RequirementContextSnapshot:
    return RequirementContextSnapshot(
        project_type="landing",
        context_version=2,
        items=(
            RequirementContextItem(
                id=ITEM_ID,
                updated_at=UPDATED_AT,
                item_type="fact",
                status="proposed",
                content="محتوای محرمانه مشتری",
                source_refs=(_ref(), _ref(second=True)),
            ),
        ),
    )


def _candidate(**changes: object) -> CandidateRequirement:
    values: dict[str, object] = {
        "title": "فرم تماس",
        "description": "یک فرم تماس در صفحه وجود داشته باشد.",
        "category": "functional",
        "priority": "must",
        "source_refs": (_ref(),),
        "confidence": Decimal("0.8000"),
        "unsupported": False,
        "duplicate_group_key": None,
        "conflict_group_key": None,
    }
    values.update(changes)
    return CandidateRequirement(**values)  # type: ignore[arg-type]


def _command(*, max_repairs: int = 1) -> GenerateRequirementsCommand:
    return GenerateRequirementsCommand(
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        correlation_id=CORRELATION_ID,
        context_version=2,
        context_item_revisions=(ContextItemRevision(ITEM_ID, UPDATED_AT),),
        task_type="opaque-requirement-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        repair_prompt_version="repair-v1",
        repair_policy=RequirementRepairPolicy(
            policy_version="policy-v1", max_repairs=max_repairs
        ),
        pricing_version="pricing-v1",
        output_schema={"owned": "by-caller"},
        routing_policy={"tier": "caller-owned"},
        cost_budget={"budget": "caller-owned"},
        timeout_policy={"timeout": "caller-owned"},
    )


class FakeSnapshotReader:
    def __init__(self, snapshot: RequirementContextSnapshot | None = None) -> None:
        self.snapshot = _snapshot() if snapshot is None else snapshot
        self.calls = 0

    async def resolve_exact(self, **_: object) -> RequirementContextSnapshot | None:
        self.calls += 1
        return self.snapshot


class SequenceAI:
    def __init__(self, outcomes: list[object], *, statuses: list[str] | None = None) -> None:
        self.outcomes = outcomes
        self.statuses = statuses or ["success"] * len(outcomes)
        self.calls: list[dict[str, object]] = []

    async def execute_structured(self, **kwargs: object) -> StructuredAIResponse:
        self.calls.append(kwargs)
        index = len(self.calls) - 1
        outcome = self.outcomes[index]
        if isinstance(outcome, Exception):
            raise outcome
        return StructuredAIResponse(
            data=outcome,
            provider_attempt_id=uuid4(),
            provider="fake",
            model="fake-model",
            provider_request_id=f"fake-{index}",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            latency_ms=12.5,
            retry_no=0,
            workflow_version="workflow-v1",
            prompt_version="prompt-v1" if index == 0 else "repair-v1",
            estimated_cost=0.01,
            status=self.statuses[index],  # type: ignore[arg-type]
        )


class FakeLedger:
    def __init__(self) -> None:
        self.records = []

    async def append(self, record) -> None:
        self.records.append(record)


class FakeSupportValidator:
    def __init__(self, *, reject_calls: int = 0) -> None:
        self.reject_calls = reject_calls
        self.calls = 0

    async def validate(self, **_: object) -> None:
        self.calls += 1
        if self.calls <= self.reject_calls:
            raise RequirementSupportClassificationError("support_classification_defect")


class FakeRepository:
    def __init__(self) -> None:
        self.replay: tuple[ExistingRequirement, ...] = ()
        self.terminal_status: str | None = None
        self.terminal_error_code: str | None = None
        self.current_revisions = _snapshot().revision_vector
        self.existing: tuple[ExistingRequirement, ...] = ()
        self.pending_writes = ()
        self.pending_updates: list[tuple[UUID, tuple[RequirementSourceReference, ...]]] = []
        self.pending_events = ()
        self.persisted_writes = ()
        self.persisted_updates = []
        self.persisted_events = ()
        self.fail_outbox = False

    async def resolve_generation_replay(self, **_: object):
        if self.terminal_status is None:
            return None
        return RequirementGenerationReplay(
            status=self.terminal_status,  # type: ignore[arg-type]
            requirements=self.replay,
            error_code=self.terminal_error_code,
        )

    async def lock_snapshot_and_resolve_revisions(self, **_: object):
        return self.current_revisions

    async def list_existing_for_merge(self, **_: object):
        return self.existing

    async def replace_source_refs(self, *, requirement_id, source_refs, **_):
        self.pending_updates.append((requirement_id, source_refs))

    async def add_batch(self, requirements):
        self.pending_writes = requirements

    async def add_conflict_events(self, events):
        if self.fail_outbox:
            raise RuntimeError("outbox failure")
        self.pending_events = events

    def rollback(self) -> None:
        self.pending_writes = ()
        self.pending_updates = []
        self.pending_events = ()

    def commit(self) -> None:
        self.persisted_writes = self.pending_writes
        self.persisted_updates = list(self.pending_updates)
        self.persisted_events = self.pending_events
        self.replay = tuple(
            ExistingRequirement(
                id=item.id,
                category=item.category,
                title=item.title,
                description=item.description,
                priority=item.priority,
                status=item.status,
                source_refs=item.source_refs,
                confidence=item.confidence,
                is_unsupported=item.is_unsupported,
                duplicate_group_key=item.duplicate_group_key,
                generation_job_id=item.generation_job_id,
            )
            for item in self.pending_writes
        )


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


def _service(
    outcomes: list[object],
    *,
    repository: FakeRepository | None = None,
    snapshot: RequirementContextSnapshot | None = None,
    validator: FakeSupportValidator | None = None,
    statuses: list[str] | None = None,
):
    repository = repository or FakeRepository()
    ai = SequenceAI(outcomes, statuses=statuses)
    ledger = FakeLedger()
    logger = RecordingLogger()
    service = GenerateRequirementsUseCase(
        snapshot_reader=FakeSnapshotReader(snapshot),
        ai_execution=ai,
        usage_ledger=ledger,
        support_validator=validator or FakeSupportValidator(),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=logger,
    )
    return service, repository, ai, ledger, logger


def test_valid_batch_uses_exact_context_and_persists_ai_drafts() -> None:
    service, repository, ai, ledger, logger = _service(
        [CandidateRequirementBatch((_candidate(),))]
    )

    result = asyncio.run(service.execute(_command()))

    assert result.persisted_count == 1
    assert result.replayed is False
    persisted = repository.persisted_writes[0]
    assert persisted.context_version == 2
    assert persisted.status == "draft"
    assert persisted.created_by_type == "ai"
    assert persisted.generation_job_id == JOB_ID
    assert len(ledger.records) == 1
    assert ai.calls[0]["input_context"]["context_version"] == 2  # type: ignore[index]
    assert [name for name, _ in logger.events] == [
        "requirements.generation_started",
        "requirements.generation_completed",
        "requirements_generated",
    ]


def test_initial_revision_vector_mismatch_fails_before_ai() -> None:
    service, repository, ai, ledger, logger = _service(
        [CandidateRequirementBatch((_candidate(),))]
    )
    command = replace(
        _command(),
        context_item_revisions=(
            ContextItemRevision(ITEM_ID, datetime(2026, 9, 6, 11, 0, tzinfo=UTC)),
        ),
    )

    with pytest.raises(RequirementSnapshotChangedError) as raised:
        asyncio.run(service.execute(command))

    assert raised.value.retryable is False
    assert ai.calls == []
    assert ledger.records == []
    assert repository.persisted_writes == ()
    assert logger.events[-1][0] == "requirements.snapshot_changed"


@pytest.mark.parametrize("race", ["insert", "update", "predicate_exit"])
def test_exact_set_change_before_commit_rolls_back_every_business_write(race: str) -> None:
    repository = FakeRepository()
    if race == "insert":
        repository.current_revisions = (
            *_snapshot().revision_vector,
            ContextItemRevision(uuid4(), UPDATED_AT),
        )
    elif race == "update":
        repository.current_revisions = (
            ContextItemRevision(ITEM_ID, datetime(2026, 9, 6, 11, 0, tzinfo=UTC)),
        )
    else:
        repository.current_revisions = ()
    service, repository, _, ledger, _ = _service(
        [CandidateRequirementBatch((_candidate(),))], repository=repository
    )

    with pytest.raises(RequirementSnapshotChangedError):
        asyncio.run(service.execute(_command()))

    assert len(ledger.records) == 1
    assert repository.persisted_writes == ()
    assert repository.persisted_updates == []
    assert repository.persisted_events == ()


def test_empty_validated_batch_is_non_repairable_insufficient_context() -> None:
    service, repository, ai, ledger, _ = _service([CandidateRequirementBatch(())])

    with pytest.raises(RequirementInsufficientContextError):
        asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 1
    assert len(ledger.records) == 1
    assert repository.persisted_writes == ()


def test_unsupported_candidate_may_persist_without_provenance() -> None:
    unsupported = _candidate(unsupported=True, source_refs=())
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((unsupported,))]
    )

    result = asyncio.run(service.execute(_command()))

    assert result.unsupported_count == 1
    assert repository.persisted_writes[0].is_unsupported is True
    assert repository.persisted_writes[0].source_refs == ()


def test_supported_candidate_without_provenance_is_repairable() -> None:
    invalid = _candidate(source_refs=())
    service, repository, ai, ledger, _ = _service(
        [CandidateRequirementBatch((invalid,)), CandidateRequirementBatch((_candidate(),))]
    )

    asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 2
    assert [record.repair_no for record in ledger.records] == [0, 1]
    assert len(repository.persisted_writes) == 1


def test_duplicate_merge_preserves_first_confidence_and_stable_unions_provenance() -> None:
    first = _candidate(duplicate_group_key="opaque-1", confidence=Decimal("0.3000"))
    second = _candidate(
        duplicate_group_key="opaque-1",
        confidence=Decimal("0.9000"),
        source_refs=(_ref(second=True), _ref()),
    )
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((first, second))]
    )

    result = asyncio.run(service.execute(_command()))

    assert result.duplicate_count == 1
    assert len(repository.persisted_writes) == 1
    assert repository.persisted_writes[0].confidence == Decimal("0.3000")
    assert repository.persisted_writes[0].source_refs == (_ref(), _ref(second=True))


def test_duplicate_semantic_disagreement_is_repaired_not_silently_selected() -> None:
    conflict = _candidate(duplicate_group_key="opaque-1", title="عنوان دیگر")
    service, repository, ai, _, _ = _service(
        [
            CandidateRequirementBatch(
                (_candidate(duplicate_group_key="opaque-1"), conflict)
            ),
            CandidateRequirementBatch((_candidate(),)),
        ]
    )

    asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 2
    assert ai.calls[1]["input_context"]["repair"]["structured_error_codes"] == (  # type: ignore[index]
        "duplicate_classification_conflict",
    )
    assert len(repository.persisted_writes) == 1


def test_existing_requirement_content_is_preserved_and_only_sources_are_unioned() -> None:
    existing_id = uuid4()
    repository = FakeRepository()
    repository.existing = (
        ExistingRequirement(
            id=existing_id,
            category="functional",
            title="ویرایش کاربر",
            description="توضیح ویرایش‌شده",
            priority="could",
            status="confirmed",
            source_refs=(_ref(),),
            confidence=Decimal("0.1000"),
            is_unsupported=False,
            duplicate_group_key="opaque-1",
            generation_job_id=uuid4(),
        ),
    )
    candidate = _candidate(
        duplicate_group_key="opaque-1", source_refs=(_ref(second=True),)
    )
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((candidate,))], repository=repository
    )

    result = asyncio.run(service.execute(_command()))

    assert result.requirement_ids == (existing_id,)
    assert repository.persisted_writes == ()
    assert repository.persisted_updates == [
        (existing_id, (_ref(), _ref(second=True)))
    ]


def test_removed_requirement_without_new_evidence_is_not_reactivated() -> None:
    removed_id = uuid4()
    repository = FakeRepository()
    repository.existing = (
        ExistingRequirement(
            id=removed_id,
            category="functional",
            title="قدیمی",
            description="قدیمی",
            priority="must",
            status="removed",
            source_refs=(_ref(),),
            confidence=None,
            is_unsupported=False,
            duplicate_group_key="opaque-1",
            generation_job_id=uuid4(),
        ),
    )
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((_candidate(duplicate_group_key="opaque-1"),))],
        repository=repository,
    )

    result = asyncio.run(service.execute(_command()))

    assert result.requirement_ids == (removed_id,)
    assert repository.persisted_writes == ()
    assert repository.persisted_updates == []


def test_ignored_removed_requirement_is_excluded_from_conflict_signal() -> None:
    removed_id = uuid4()
    repository = FakeRepository()
    repository.existing = (
        ExistingRequirement(
            id=removed_id,
            category="functional",
            title="قدیمی",
            description="قدیمی",
            priority="must",
            status="removed",
            source_refs=(_ref(),),
            confidence=None,
            is_unsupported=False,
            duplicate_group_key="removed-group",
            generation_job_id=uuid4(),
        ),
    )
    ignored = _candidate(
        duplicate_group_key="removed-group", conflict_group_key="conflict-group"
    )
    new = _candidate(
        title="نیازمندی تازه",
        description="شرح تازه",
        conflict_group_key="conflict-group",
    )
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((ignored, new))], repository=repository
    )

    result = asyncio.run(service.execute(_command()))

    assert result.conflict_count == 0
    assert repository.persisted_events == ()


def test_removed_requirement_with_new_evidence_creates_new_draft() -> None:
    repository = FakeRepository()
    repository.existing = (
        ExistingRequirement(
            id=uuid4(),
            category="functional",
            title="قدیمی",
            description="قدیمی",
            priority="must",
            status="removed",
            source_refs=(_ref(),),
            confidence=None,
            is_unsupported=False,
            duplicate_group_key="opaque-1",
            generation_job_id=uuid4(),
        ),
    )
    candidate = _candidate(
        duplicate_group_key="opaque-1", source_refs=(_ref(), _ref(second=True))
    )
    service, repository, _, _, _ = _service(
        [CandidateRequirementBatch((candidate,))], repository=repository
    )

    asyncio.run(service.execute(_command()))

    assert len(repository.persisted_writes) == 1
    assert repository.persisted_writes[0].status == "draft"


def test_conflicts_persist_as_separate_requirements_and_emit_safe_outbox() -> None:
    first = _candidate(conflict_group_key="opaque-conflict")
    second = _candidate(
        title="فرم تماس ممنوع",
        description="فرم تماس نباید وجود داشته باشد.",
        conflict_group_key="opaque-conflict",
    )
    service, repository, _, _, logger = _service(
        [CandidateRequirementBatch((first, second))]
    )

    result = asyncio.run(service.execute(_command()))

    assert len(repository.persisted_writes) == 2
    assert result.conflict_count == 1
    assert len(repository.persisted_events) == 1
    assert len(repository.persisted_events[0].requirement_ids) == 2
    assert "opaque-conflict" not in repr(repository.persisted_events)
    assert "opaque-conflict" not in repr(logger.events)


def test_outbox_failure_rolls_back_requirements_and_source_mutations() -> None:
    repository = FakeRepository()
    repository.fail_outbox = True
    items = (
        _candidate(conflict_group_key="opaque-conflict"),
        _candidate(title="متناقض", conflict_group_key="opaque-conflict"),
    )
    service, repository, _, ledger, _ = _service(
        [CandidateRequirementBatch(items)], repository=repository
    )

    with pytest.raises(RuntimeError):
        asyncio.run(service.execute(_command()))

    assert len(ledger.records) == 1
    assert repository.persisted_writes == ()
    assert repository.persisted_updates == []
    assert repository.persisted_events == ()


def test_replay_returns_completed_batch_without_ai_or_usage() -> None:
    repository = FakeRepository()
    replay_id = uuid4()
    repository.replay = (
        ExistingRequirement(
            id=replay_id,
            category="functional",
            title="قبلی",
            description="قبلی",
            priority="must",
            status="draft",
            source_refs=(_ref(),),
            confidence=None,
            is_unsupported=False,
            duplicate_group_key=None,
            generation_job_id=JOB_ID,
        ),
    )
    repository.terminal_status = "succeeded"
    service, _, ai, ledger, logger = _service([], repository=repository)

    result = asyncio.run(service.execute(_command()))

    assert result.replayed is True
    assert result.requirement_ids == (replay_id,)
    assert ai.calls == []
    assert ledger.records == []
    assert logger.events[-1][0] == "requirements.replay_served"


def test_succeeded_job_with_no_generated_rows_is_a_terminal_empty_replay() -> None:
    repository = FakeRepository()
    repository.terminal_status = "succeeded"
    service, _, ai, ledger, logger = _service([], repository=repository)

    result = asyncio.run(service.execute(_command()))

    assert result.replayed is True
    assert result.requirement_ids == ()
    assert result.persisted_count == 0
    assert ai.calls == []
    assert ledger.records == []
    assert logger.events[-1][0] == "requirements.replay_served"


def test_concurrent_replay_discovered_after_ai_emits_replay_event() -> None:
    replay_id = uuid4()

    class ConcurrentReplayRepository(FakeRepository):
        def __init__(self) -> None:
            super().__init__()
            self.replay_checks = 0

        async def resolve_generation_replay(self, **_: object):
            self.replay_checks += 1
            if self.replay_checks == 1:
                return None
            return RequirementGenerationReplay(
                status="succeeded",
                requirements=(ExistingRequirement(
                    id=replay_id,
                    category="functional",
                    title="قبلی",
                    description="قبلی",
                    priority="must",
                    status="draft",
                    source_refs=(_ref(),),
                    confidence=None,
                    is_unsupported=False,
                    duplicate_group_key=None,
                    generation_job_id=JOB_ID,
                ),),
                error_code=None,
            )

    repository = ConcurrentReplayRepository()
    service, _, ai, ledger, logger = _service(
        [CandidateRequirementBatch((_candidate(),))], repository=repository
    )

    result = asyncio.run(service.execute(_command()))

    assert result.replayed is True
    assert result.requirement_ids == (replay_id,)
    assert len(ai.calls) == 1
    assert len(ledger.records) == 1
    assert logger.events[-1][0] == "requirements.replay_served"


def test_failed_terminal_job_replays_error_without_ai_or_usage() -> None:
    repository = FakeRepository()
    repository.terminal_status = "failed"
    repository.terminal_error_code = "INSUFFICIENT_CONTEXT"
    service, _, ai, ledger, logger = _service([], repository=repository)

    with pytest.raises(RequirementGenerationError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.reason_code == "INSUFFICIENT_CONTEXT"
    assert ai.calls == []
    assert ledger.records == []
    assert logger.events[-1][0] == "requirements.generation_failed"


def test_repair_exhaustion_is_non_retryable_and_writes_nothing() -> None:
    bad = CandidateRequirementBatch(
        (
            _candidate(duplicate_group_key="same"),
            _candidate(duplicate_group_key="same", priority="could"),
        )
    )
    service, repository, ai, ledger, logger = _service([bad, bad])

    with pytest.raises(RequirementRepairExhaustedError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.retryable is False
    assert len(ai.calls) == 2
    assert [record.repair_no for record in ledger.records] == [0, 1]
    assert repository.persisted_writes == ()
    assert "requirements.repair_exhausted" in [name for name, _ in logger.events]


def test_failed_provider_response_is_metered_and_not_repaired() -> None:
    service, repository, ai, ledger, _ = _service(
        [CandidateRequirementBatch((_candidate(),))], statuses=["failed"]
    )

    with pytest.raises(RequirementGenerationError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.reason_code == "provider_execution_failed"
    assert len(ai.calls) == 1
    assert len(ledger.records) == 1
    assert ledger.records[0].status == "failed"
    assert repository.persisted_writes == ()


def test_logs_do_not_contain_context_or_requirement_payloads() -> None:
    secret_title = "عنوان بسیار محرمانه"
    secret_description = "شرح خصوصی مشتری"
    secret_key = "کلید محتوایی ممنوع"
    candidate = _candidate(
        title=secret_title,
        description=secret_description,
        duplicate_group_key=secret_key,
    )
    service, _, _, _, logger = _service([CandidateRequirementBatch((candidate,))])

    asyncio.run(service.execute(_command()))

    serialized = repr(logger.events)
    assert secret_title not in serialized
    assert secret_description not in serialized
    assert secret_key not in serialized
    assert "محتوای محرمانه مشتری" not in serialized
    assert str(SOURCE_ID) not in serialized


@pytest.mark.parametrize(
    ("policy_version", "max_repairs"),
    [("", 1), ("v1", -1), ("v1", 2), ("v1", True)],
)
def test_repair_policy_has_no_hidden_or_unbounded_value(
    policy_version: str, max_repairs: int
) -> None:
    with pytest.raises(ValueError):
        RequirementRepairPolicy(
            policy_version=policy_version, max_repairs=max_repairs
        )


def test_duplicate_conflict_without_repair_preserves_stable_error() -> None:
    items = (
        _candidate(duplicate_group_key="same"),
        _candidate(duplicate_group_key="same", unsupported=True),
    )
    service, repository, _, _, _ = _service([CandidateRequirementBatch(items)])

    with pytest.raises(RequirementDuplicateClassificationError) as raised:
        asyncio.run(service.execute(_command(max_repairs=0)))

    assert raised.value.code == "DUPLICATE_CLASSIFICATION_CONFLICT"
    assert repository.persisted_writes == ()
