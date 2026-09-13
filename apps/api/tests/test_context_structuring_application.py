from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import AIExecutionError, StructuredAIResponse
from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    CandidateContextItem,
    CandidateSourceReference,
    ContextRepairExhaustedError,
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringDuplicateError,
    ContextStructuringResult,
    ContextStructuringSchemaError,
    ContextStructuringSourceError,
    ContextStructuringUseCase,
    ContextStructuringValidationError,
    ContextVersionWrite,
    SourceSnapshot,
)


class FakeSnapshotReader:
    def __init__(self, snapshot: tuple[SourceSnapshot, ...]) -> None:
        self.snapshot = snapshot
        self.calls = 0

    async def resolve_latest_ready(self, *, account_id: UUID, project_id: UUID):
        del account_id, project_id
        self.calls += 1
        return self.snapshot


class FakeAIExecution:
    def __init__(self, data: object, *, during_execute=None) -> None:
        self.data = data
        self.during_execute = during_execute
        self.input_context: object | None = None

    async def execute_structured(self, **kwargs):
        self.input_context = kwargs["input_context"]
        if self.during_execute is not None:
            self.during_execute()
        return StructuredAIResponse(
            data=self.data,
            provider="fake",
            model="fake-model",
            provider_request_id="fake-request",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=20,
            latency_ms=5,
            retry_no=0,
            workflow_version=kwargs["workflow_version"],
            prompt_version=kwargs["prompt_version"],
            estimated_cost=0,
            status="success",
        )


class SequenceAIExecution:
    def __init__(self, outcomes: list[object], *, retry_numbers: list[int] | None = None) -> None:
        self.outcomes = list(outcomes)
        self.retry_numbers = retry_numbers or [0] * len(outcomes)
        self.calls: list[dict[str, object]] = []

    async def execute_structured(self, **kwargs):
        call_no = len(self.calls)
        self.calls.append(kwargs)
        outcome = self.outcomes[call_no]
        if isinstance(outcome, Exception):
            raise outcome
        return StructuredAIResponse(
            data=outcome,
            provider="fake",
            model="fake-model",
            provider_request_id=f"fake-request-{call_no}",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=20,
            latency_ms=5,
            retry_no=self.retry_numbers[call_no],
            workflow_version=kwargs["workflow_version"],
            prompt_version=kwargs["prompt_version"],
            estimated_cost=0,
            status="success",
        )


class FakeUnsupportedClaimValidator:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject

    async def validate(self, *, batch, snapshot) -> None:
        del batch, snapshot
        if self.reject:
            raise ContextStructuringValidationError("unsupported_claim")


class FakeUsageLedger:
    def __init__(self) -> None:
        self.records = []

    async def append(self, record) -> None:
        self.records.append(record)


class FakeRepository:
    def __init__(self, *, current_version: int = 0, fail_on_add: bool = False) -> None:
        self.current_version = current_version
        self.fail_on_add = fail_on_add
        self.pending: tuple[ContextVersionWrite, ...] = ()
        self.persisted: tuple[ContextVersionWrite, ...] = ()

    async def allocate_next_version(self, *, account_id: UUID, project_id: UUID) -> int:
        del account_id, project_id
        return self.current_version + 1

    async def add_batch(self, items: tuple[ContextVersionWrite, ...]) -> None:
        if self.fail_on_add:
            raise RuntimeError("declared fake persistence failure")
        self.pending = items

    async def advance_project_version(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> None:
        del account_id, project_id
        self.current_version = context_version


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self._repository = repository
        self.committed = False

    @property
    def repository(self):
        return self._repository

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        if exc is not None or not self.committed:
            self._repository.pending = ()

    async def commit(self) -> None:
        self._repository.persisted = self._repository.pending
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


ACCOUNT_ID = uuid4()
PROJECT_ID = uuid4()
JOB_ID = uuid4()
CORRELATION_ID = uuid4()
SOURCE_ID = uuid4()
SOURCE_VERSION_ID = uuid4()


def _snapshot() -> tuple[SourceSnapshot, ...]:
    return (
        SourceSnapshot(
            source_id=SOURCE_ID,
            source_version_id=SOURCE_VERSION_ID,
            version_no=2,
            canonical_text="متن محرمانه مشتری",
            storage_ref=None,
        ),
    )


def _candidate(*, item_type: str = "fact", content: str = "محصول فارسی"):
    return CandidateContextItem(
        item_type=item_type,
        content=content,
        source_refs=(
            CandidateSourceReference(
                source_id=SOURCE_ID,
                source_version_id=SOURCE_VERSION_ID,
                start_offset=0,
                end_offset=4,
            ),
        ),
        confidence=Decimal("0.9000"),
        rationale_short="مشتق از brief محرمانه",
    )


def _command(*, max_repairs: int = 1) -> ContextStructuringCommand:
    return ContextStructuringCommand(
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        correlation_id=CORRELATION_ID,
        task_type="opaque-task",
        workflow_version="caller-workflow",
        prompt_version="caller-prompt",
        repair_prompt_version="caller-repair-prompt",
        repair_policy=ContextRepairPolicy(
            policy_version="caller-repair-policy",
            max_repairs=max_repairs,
        ),
        pricing_version="caller-pricing",
        output_schema={"caller": "owned"},
        routing_policy={"caller": "owned"},
        cost_budget={"caller": "owned"},
        timeout_policy={"caller": "owned"},
    )


def _repair_service(
    *,
    outcomes: list[object],
    retry_numbers: list[int] | None = None,
    snapshot: tuple[SourceSnapshot, ...] | None = None,
    reject_unsupported: bool = False,
    repository: FakeRepository | None = None,
    logger: RecordingLogger | None = None,
):
    repository = repository or FakeRepository()
    logger = logger or RecordingLogger()
    reader = FakeSnapshotReader(_snapshot() if snapshot is None else snapshot)
    ai = SequenceAIExecution(outcomes, retry_numbers=retry_numbers)
    ledger = FakeUsageLedger()
    service = ContextStructuringUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=ledger,
        unsupported_claim_validator=FakeUnsupportedClaimValidator(
            reject=reject_unsupported
        ),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=logger,
        id_factory=uuid4,
    )
    return service, reader, ai, ledger, repository, logger


def _service(*, data: object, reject_unsupported: bool = False, repository=None, logger=None):
    repository = repository or FakeRepository()
    logger = logger or RecordingLogger()
    reader = FakeSnapshotReader(_snapshot())
    return (
        ContextStructuringUseCase(
            snapshot_reader=reader,
            ai_execution=FakeAIExecution(data),
            usage_ledger=FakeUsageLedger(),
            unsupported_claim_validator=FakeUnsupportedClaimValidator(
                reject=reject_unsupported
            ),
            unit_of_work_factory=FakeUnitOfWorkFactory(repository),
            event_logger=logger,
            id_factory=uuid4,
        ),
        reader,
        repository,
        logger,
    )


def test_full_valid_batch_is_persisted_as_one_context_version() -> None:
    service, reader, repository, logger = _service(
        data=CandidateContextBatch(
            items=(_candidate(), _candidate(item_type="unknown", content="ابهام"))
        )
    )
    result = asyncio.run(service.execute(_command()))

    assert result.context_version == 1
    assert result.item_count == 2
    assert reader.calls == 1
    assert repository.current_version == 1
    assert len(repository.persisted) == 2
    assert all(item.context_version == 1 for item in repository.persisted)
    assert all(
        item.created_by_type == "ai" and item.status == "proposed"
        for item in repository.persisted
    )
    assert [event[0] for event in logger.events] == [
        "context.structuring_started",
        "structuring_started",
        "context.structuring_completed",
        "structuring_completed",
    ]


@pytest.mark.parametrize(
    ("data", "error_type"),
    [
        ({"items": []}, ContextStructuringSchemaError),
        (CandidateContextBatch(items=(_candidate(item_type="fact"),)), None),
    ],
)
def test_invalid_schema_or_fact_without_provenance_writes_nothing(data, error_type) -> None:
    if error_type is None:
        data = CandidateContextBatch(items=(replace(_candidate(), source_refs=()),))
        error_type = ContextStructuringSourceError
    service, _, repository, _ = _service(data=data)
    with pytest.raises(error_type):
        asyncio.run(service.execute(_command(max_repairs=0)))
    assert repository.persisted == ()
    assert repository.current_version == 0


def test_invalid_or_out_of_bounds_reference_rejects_whole_batch() -> None:
    invalid = replace(
        _candidate(),
        source_refs=(
            CandidateSourceReference(
                source_id=SOURCE_ID,
                source_version_id=SOURCE_VERSION_ID,
                start_offset=0,
                end_offset=500,
            ),
        ),
    )
    service, _, repository, _ = _service(
        data=CandidateContextBatch(items=(_candidate(item_type="unknown"), invalid))
    )
    with pytest.raises(ContextStructuringSourceError):
        asyncio.run(service.execute(_command(max_repairs=0)))
    assert repository.persisted == ()


def test_unsupported_claim_rejects_whole_batch() -> None:
    service, _, repository, _ = _service(
        data=CandidateContextBatch(items=(_candidate(),)), reject_unsupported=True
    )
    with pytest.raises(ContextStructuringValidationError):
        asyncio.run(service.execute(_command(max_repairs=0)))
    assert repository.persisted == ()


def test_exact_duplicate_rejects_whole_batch_with_stable_error() -> None:
    duplicate = _candidate()
    service, _, repository, _ = _service(
        data=CandidateContextBatch(items=(duplicate, duplicate))
    )
    with pytest.raises(ContextStructuringDuplicateError) as raised:
        asyncio.run(service.execute(_command(max_repairs=0)))
    assert raised.value.code == "DUPLICATE_CONTEXT_ITEM"
    assert repository.persisted == ()
    assert repository.current_version == 0


def test_non_exact_content_is_not_classified_as_duplicate() -> None:
    service, _, repository, _ = _service(
        data=CandidateContextBatch(
            items=(
                _candidate(content="متن"),
                _candidate(content=" متن"),
                _candidate(content="متن "),
                _candidate(content="ي"),
                _candidate(content="ی"),
            )
        )
    )
    result = asyncio.run(service.execute(_command()))
    assert result.item_count == 5
    assert len(repository.persisted) == 5


def test_persistence_failure_does_not_consume_version() -> None:
    repository = FakeRepository(fail_on_add=True)
    service, _, _, _ = _service(
        data=CandidateContextBatch(items=(_candidate(),)), repository=repository
    )
    with pytest.raises(RuntimeError):
        asyncio.run(service.execute(_command()))
    assert repository.current_version == 0
    assert repository.persisted == ()


def test_source_snapshot_is_resolved_once_before_ai_execution() -> None:
    reader = FakeSnapshotReader(_snapshot())
    added_later = SourceSnapshot(
        source_id=uuid4(),
        source_version_id=uuid4(),
        version_no=1,
        canonical_text="later",
        storage_ref=None,
    )
    ai = FakeAIExecution(
        CandidateContextBatch(items=(_candidate(),)),
        during_execute=lambda: setattr(reader, "snapshot", (*reader.snapshot, added_later)),
    )
    repository = FakeRepository()
    service = ContextStructuringUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=FakeUsageLedger(),
        unsupported_claim_validator=FakeUnsupportedClaimValidator(),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=RecordingLogger(),
        id_factory=uuid4,
    )
    asyncio.run(service.execute(_command()))
    assert reader.calls == 1
    assert str(added_later.source_version_id) not in str(ai.input_context)


def test_logs_never_receive_content_refs_or_rationale() -> None:
    logger = RecordingLogger()
    service, _, _, _ = _service(
        data=CandidateContextBatch(items=(_candidate(),)), logger=logger
    )
    asyncio.run(service.execute(_command()))
    serialized = repr(logger.events)
    assert "محصول فارسی" not in serialized
    assert "مشتق از brief محرمانه" not in serialized
    assert str(SOURCE_ID) not in serialized
    assert str(SOURCE_VERSION_ID) not in serialized


def test_provider_execution_is_recorded_in_usage_ledger() -> None:
    ledger = FakeUsageLedger()
    reader = FakeSnapshotReader(_snapshot())
    repository = FakeRepository()
    service = ContextStructuringUseCase(
        snapshot_reader=reader,
        ai_execution=FakeAIExecution(CandidateContextBatch(items=(_candidate(),))),
        usage_ledger=ledger,
        unsupported_claim_validator=FakeUnsupportedClaimValidator(),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=RecordingLogger(),
        id_factory=uuid4,
    )
    asyncio.run(service.execute(_command()))
    assert len(ledger.records) == 1
    record = ledger.records[0]
    assert record.account_id == ACCOUNT_ID
    assert record.project_id == PROJECT_ID
    assert record.job_id == JOB_ID
    assert record.pricing_version == "caller-pricing"
    assert record.provider == "fake"
    assert record.repair_no == 0


def test_disabled_repair_preserves_original_validation_failure() -> None:
    service, _, ai, ledger, repository, logger = _repair_service(outcomes=[{"bad": True}])
    command = replace(
        _command(),
        repair_policy=ContextRepairPolicy(
            policy_version="repair-disabled",
            max_repairs=0,
        ),
    )

    with pytest.raises(ContextStructuringSchemaError) as raised:
        asyncio.run(service.execute(command))

    assert raised.value.reason_code == "invalid_context_candidate_batch"
    assert len(ai.calls) == 1
    assert [record.repair_no for record in ledger.records] == [0]
    assert repository.persisted == ()
    assert all(not name.startswith("context.repair_") for name, _ in logger.events)


@pytest.mark.parametrize(
    ("policy_version", "max_repairs"),
    [("", 1), ("policy-v1", -1), ("policy-v1", 2), ("policy-v1", True)],
)
def test_repair_policy_has_no_hidden_or_unbounded_sprint_value(
    policy_version: str, max_repairs: int
) -> None:
    with pytest.raises(ValueError):
        ContextRepairPolicy(
            policy_version=policy_version,
            max_repairs=max_repairs,
        )


def test_schema_failure_repairs_once_through_same_ai_contract() -> None:
    repaired = CandidateContextBatch(items=(_candidate(),))
    service, reader, ai, ledger, repository, logger = _repair_service(
        outcomes=[{"bad": True}, repaired]
    )

    result = asyncio.run(service.execute(_command()))

    assert result == ContextStructuringResult(context_version=1, item_count=1)
    assert reader.calls == 1
    assert len(ai.calls) == 2
    original, repair = ai.calls
    assert original["workflow_version"] == repair["workflow_version"] == "caller-workflow"
    assert original["routing_policy"] is repair["routing_policy"]
    assert original["cost_budget"] is repair["cost_budget"]
    assert original["timeout_policy"] is repair["timeout_policy"]
    assert original["prompt_version"] == "caller-prompt"
    assert repair["prompt_version"] == "caller-repair-prompt"
    repair_context = repair["input_context"]
    assert repair_context["repair"]["repair_no"] == 1
    assert repair_context["repair"]["structured_error_codes"] == ("schema_invalid",)
    assert repair_context["repair"]["rejected_output"] == {"bad": True}
    assert [record.repair_no for record in ledger.records] == [0, 1]
    assert len(repository.persisted) == 1
    assert [name for name, _ in logger.events if name.startswith("context.repair_")] == [
        "context.repair_started",
        "context.repair_succeeded",
    ]


def test_repair_exhaustion_is_non_retryable_and_writes_no_context() -> None:
    logger = RecordingLogger()
    secret = "خروجی محرمانه ردشده"
    service, _, ai, ledger, repository, _ = _repair_service(
        outcomes=[{"secret": secret}, {"secret": secret}],
        logger=logger,
    )

    with pytest.raises(ContextRepairExhaustedError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.code == "CONTEXT_REPAIR_EXHAUSTED"
    assert raised.value.retryable is False
    assert len(ai.calls) == 2
    assert [record.repair_no for record in ledger.records] == [0, 1]
    assert repository.persisted == ()
    assert repository.current_version == 0
    repair_events = [event for event in logger.events if event[0].startswith("context.repair_")]
    assert [name for name, _ in repair_events] == [
        "context.repair_started",
        "context.repair_failed",
        "context.repair_exhausted",
    ]
    serialized = repr(repair_events)
    assert secret not in serialized
    assert "caller-prompt" not in serialized
    assert "caller-repair-prompt" in serialized
    assert all(
        fields.get("reason_code") == "schema_invalid"
        for name, fields in repair_events
        if name != "context.repair_started"
    )


@pytest.mark.parametrize(
    ("invalid_batch", "reason_code"),
    [
        (
            CandidateContextBatch(
                items=(replace(_candidate(), source_refs=()),)
            ),
            "invalid_source_reference",
        ),
        (
            CandidateContextBatch(items=(_candidate(), _candidate())),
            "duplicate_candidate",
        ),
    ],
)
def test_model_output_provenance_and_duplicate_defects_are_repairable(
    invalid_batch: CandidateContextBatch, reason_code: str
) -> None:
    service, _, ai, _, repository, _ = _repair_service(
        outcomes=[invalid_batch, CandidateContextBatch(items=(_candidate(),))]
    )

    asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 2
    assert ai.calls[1]["input_context"]["repair"]["structured_error_codes"] == (
        reason_code,
    )
    assert len(repository.persisted) == 1


def test_unsupported_claim_is_repairable() -> None:
    class RejectFirstUnsupportedClaim:
        def __init__(self) -> None:
            self.calls = 0

        async def validate(self, *, batch, snapshot) -> None:
            del batch, snapshot
            self.calls += 1
            if self.calls == 1:
                raise ContextStructuringValidationError("unsupported_claim")

    repository = FakeRepository()
    ai = SequenceAIExecution(
        [
            CandidateContextBatch(items=(_candidate(),)),
            CandidateContextBatch(items=(_candidate(content="اصلاح‌شده"),)),
        ]
    )
    service = ContextStructuringUseCase(
        snapshot_reader=FakeSnapshotReader(_snapshot()),
        ai_execution=ai,
        usage_ledger=FakeUsageLedger(),
        unsupported_claim_validator=RejectFirstUnsupportedClaim(),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=RecordingLogger(),
    )

    asyncio.run(service.execute(_command()))

    assert ai.calls[1]["input_context"]["repair"]["structured_error_codes"] == (
        "unsupported_claim",
    )
    assert len(repository.persisted) == 1


def test_provider_failure_does_not_trigger_repair() -> None:
    provider_error = AIExecutionError("provider_unavailable", retryable=True)
    service, _, ai, ledger, repository, _ = _repair_service(outcomes=[provider_error])

    with pytest.raises(AIExecutionError):
        asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 1
    assert ledger.records == []
    assert repository.persisted == ()


def test_missing_ready_source_does_not_invoke_ai_or_repair() -> None:
    service, _, ai, ledger, repository, _ = _repair_service(
        outcomes=[], snapshot=()
    )

    with pytest.raises(ContextStructuringSourceError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.reason_code == "ready_source_required"
    assert ai.calls == []
    assert ledger.records == []
    assert repository.persisted == ()


def test_insufficient_context_does_not_trigger_repair() -> None:
    class InsufficientContextValidator:
        async def validate(self, *, batch, snapshot) -> None:
            del batch, snapshot
            raise ContextStructuringValidationError("insufficient_context")

    ai = SequenceAIExecution([CandidateContextBatch(items=(_candidate(),))])
    repository = FakeRepository()
    service = ContextStructuringUseCase(
        snapshot_reader=FakeSnapshotReader(_snapshot()),
        ai_execution=ai,
        usage_ledger=FakeUsageLedger(),
        unsupported_claim_validator=InsufficientContextValidator(),
        unit_of_work_factory=FakeUnitOfWorkFactory(repository),
        event_logger=RecordingLogger(),
    )

    with pytest.raises(ContextStructuringValidationError) as raised:
        asyncio.run(service.execute(_command()))

    assert raised.value.reason_code == "insufficient_context"
    assert len(ai.calls) == 1
    assert repository.persisted == ()


def test_repository_failure_after_valid_repair_does_not_start_another_repair() -> None:
    repository = FakeRepository(fail_on_add=True)
    service, _, ai, _, _, _ = _repair_service(
        outcomes=[{"bad": True}, CandidateContextBatch(items=(_candidate(),))],
        repository=repository,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(service.execute(_command()))

    assert len(ai.calls) == 2
    assert repository.current_version == 0
    assert repository.persisted == ()


def test_provider_retry_number_is_independent_inside_repair_usage() -> None:
    service, _, _, ledger, _, _ = _repair_service(
        outcomes=[{"bad": True}, CandidateContextBatch(items=(_candidate(),))],
        retry_numbers=[2, 3],
    )

    asyncio.run(service.execute(_command()))

    assert [(record.repair_no, record.retry_no) for record in ledger.records] == [
        (0, 2),
        (1, 3),
    ]
