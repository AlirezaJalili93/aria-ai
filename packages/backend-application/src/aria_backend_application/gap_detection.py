from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from types import TracebackType
from typing import Literal, Protocol, Self
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import AIExecutionPort, StructuredAIResponse
from aria_backend_application.usage_ledger import UsageLedger, UsageRecord

GapType = Literal[
    "missing_information",
    "ambiguity",
    "conflict",
    "decision_required",
    "unsupported_assumption",
    "scope_risk",
]
GapSeverity = Literal["critical", "high", "medium", "low"]
SuggestedResolutionType = Literal[
    "provide_information",
    "clarify_ambiguity",
    "resolve_conflict",
    "make_decision",
    "validate_assumption",
    "mitigate_scope_risk",
]
ContextItemStatus = Literal["proposed", "confirmed"]
RequirementStatus = Literal["draft", "confirmed"]

GAP_TYPES = frozenset(
    {
        "missing_information",
        "ambiguity",
        "conflict",
        "decision_required",
        "unsupported_assumption",
        "scope_risk",
    }
)
GAP_SEVERITIES = frozenset({"critical", "high", "medium", "low"})
SUGGESTED_RESOLUTION_TYPES = frozenset(
    {
        "provide_information",
        "clarify_ambiguity",
        "resolve_conflict",
        "make_decision",
        "validate_assumption",
        "mitigate_scope_risk",
    }
)
ELIGIBLE_CONTEXT_STATUSES = frozenset({"proposed", "confirmed"})
ELIGIBLE_REQUIREMENT_STATUSES = frozenset({"draft", "confirmed"})


class GapDetectionError(RuntimeError):
    """A safe provider-neutral Gap detection failure."""

    retryable = False

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class GapDetectionSchemaError(GapDetectionError):
    """Provider output does not satisfy the accepted J02-A schema."""


class GapDetectionProvenanceError(GapDetectionError):
    """A candidate reference is outside the exact input snapshot."""


class GapAffectedRequirementError(GapDetectionError):
    """A candidate points outside the exact active Requirement snapshot."""


class GapDuplicateError(GapDetectionError):
    code = "DUPLICATE_GAP"

    def __init__(self) -> None:
        super().__init__("duplicate_gap")


class GapSnapshotChangedError(GapDetectionError):
    code = "GAP_SNAPSHOT_CHANGED"

    def __init__(self) -> None:
        super().__init__("gap_snapshot_changed")


class GapRepairExhaustedError(GapDetectionError):
    code = "GAP_REPAIR_EXHAUSTED"

    def __init__(self) -> None:
        super().__init__("gap_repair_exhausted")


class GapDetectionRepositoryError(GapDetectionError):
    """A declared Gap detection persistence failure."""


@dataclass(frozen=True, slots=True)
class GapSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        absent = self.start_offset is None and self.end_offset is None
        present = self.start_offset is not None and self.end_offset is not None
        if not absent and not present:
            raise GapDetectionSchemaError("invalid_source_reference_shape")
        if present:
            assert self.start_offset is not None and self.end_offset is not None
            if (
                isinstance(self.start_offset, bool)
                or isinstance(self.end_offset, bool)
                or not isinstance(self.start_offset, int)
                or not isinstance(self.end_offset, int)
                or self.start_offset < 0
                or self.start_offset >= self.end_offset
            ):
                raise GapDetectionSchemaError("invalid_source_reference_offsets")

    def identity(self) -> tuple[UUID, UUID, int | None, int | None]:
        return (
            self.source_id,
            self.source_version_id,
            self.start_offset,
            self.end_offset,
        )


@dataclass(frozen=True, slots=True)
class ContextItemRevision:
    context_item_id: UUID
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Context Item revision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RequirementRevision:
    requirement_id: UUID
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Requirement revision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapContextItem:
    id: UUID
    updated_at: datetime
    item_type: str
    status: ContextItemStatus
    content: str
    source_refs: tuple[GapSourceReference, ...]

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Context Item updated_at must be timezone-aware")
        if self.status not in ELIGIBLE_CONTEXT_STATUSES:
            raise ValueError("Context Item is outside the Gap snapshot predicate")

    @property
    def revision(self) -> ContextItemRevision:
        return ContextItemRevision(self.id, self.updated_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class GapRequirement:
    id: UUID
    updated_at: datetime
    category: str
    title: str
    description: str
    priority: str
    status: RequirementStatus
    source_refs: tuple[GapSourceReference, ...]

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Requirement updated_at must be timezone-aware")
        if self.status not in ELIGIBLE_REQUIREMENT_STATUSES:
            raise ValueError("Requirement is outside the Gap snapshot predicate")

    @property
    def revision(self) -> RequirementRevision:
        return RequirementRevision(self.id, self.updated_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class GapDetectionSnapshot:
    project_type: str
    context_version: int
    completion_checklist_version: str
    context_items: tuple[GapContextItem, ...]
    requirements: tuple[GapRequirement, ...]

    @property
    def context_item_revisions(self) -> tuple[ContextItemRevision, ...]:
        return tuple(
            sorted(
                (item.revision for item in self.context_items),
                key=lambda value: value.context_item_id.int,
            )
        )

    @property
    def requirement_revisions(self) -> tuple[RequirementRevision, ...]:
        return tuple(
            sorted(
                (item.revision for item in self.requirements),
                key=lambda value: value.requirement_id.int,
            )
        )


@dataclass(frozen=True, slots=True)
class GapSnapshotRevisions:
    project_type: str
    context_item_revisions: tuple[ContextItemRevision, ...]
    requirement_revisions: tuple[RequirementRevision, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateGap:
    gap_type: GapType
    severity: GapSeverity
    explanation: str
    source_refs: tuple[GapSourceReference, ...]
    affected_requirement_ids: tuple[UUID, ...]
    suggested_resolution_type: SuggestedResolutionType

    def __post_init__(self) -> None:
        if self.gap_type not in GAP_TYPES:
            raise GapDetectionSchemaError("invalid_gap_type")
        if self.severity not in GAP_SEVERITIES:
            raise GapDetectionSchemaError("invalid_gap_severity")
        if not isinstance(self.explanation, str):
            raise GapDetectionSchemaError("invalid_gap_explanation")
        if self.suggested_resolution_type not in SUGGESTED_RESOLUTION_TYPES:
            raise GapDetectionSchemaError("invalid_suggested_resolution_type")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(reference, GapSourceReference) for reference in self.source_refs
        ):
            raise GapDetectionSchemaError("invalid_gap_source_refs")
        if not isinstance(self.affected_requirement_ids, tuple) or not all(
            isinstance(requirement_id, UUID)
            for requirement_id in self.affected_requirement_ids
        ):
            raise GapDetectionSchemaError("invalid_affected_requirement_ids")

    @property
    def exact_identity(self) -> tuple[object, ...]:
        return (
            self.gap_type,
            self.severity,
            self.explanation,
            self.suggested_resolution_type,
            tuple(sorted(reference.identity() for reference in self.source_refs)),
            tuple(sorted(self.affected_requirement_ids, key=lambda value: value.int)),
        )


@dataclass(frozen=True, slots=True)
class CandidateGapBatch:
    items: tuple[CandidateGap, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, CandidateGap) for item in self.items
        ):
            raise GapDetectionSchemaError("invalid_gap_candidate_batch")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapRepairPolicy:
    policy_version: str
    max_repairs: int

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise ValueError("Gap repair policy version is required")
        if isinstance(self.max_repairs, bool) or self.max_repairs not in (0, 1):
            raise ValueError("Sprint 1 Gap repair permits max_repairs 0 or 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectGapsCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ContextItemRevision, ...]
    requirement_revisions: tuple[RequirementRevision, ...]
    completion_checklist_version: str
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_prompt_version: str
    repair_policy: GapRepairPolicy
    pricing_version: str
    output_schema: Mapping[str, object]
    routing_policy: Mapping[str, object]
    cost_budget: Mapping[str, object]
    timeout_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")
        if not self.completion_checklist_version:
            raise ValueError("completion_checklist_version is required")
        _assert_sorted_unique_context_revisions(self.context_item_revisions)
        _assert_sorted_unique_requirement_revisions(self.requirement_revisions)


@dataclass(frozen=True, slots=True)
class CriticalGapRuleEvaluation:
    authoritative_candidate_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(set(self.authoritative_candidate_indexes)) != len(
            self.authoritative_candidate_indexes
        ) or any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0
            for index in self.authoritative_candidate_indexes
        ):
            raise ValueError(
                "Critical candidate indexes must be unique non-negative integers"
            )


class CriticalGapRuleEvaluator(Protocol):
    async def evaluate(
        self, *, snapshot: GapDetectionSnapshot, batch: CandidateGapBatch
    ) -> CriticalGapRuleEvaluation: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class GapWrite:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    gap_type: GapType
    severity: GapSeverity
    explanation: str
    source_refs: tuple[GapSourceReference, ...]
    suggested_resolution_type: SuggestedResolutionType
    generation_job_id: UUID
    affected_requirement_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class GapDetectionResult:
    gap_ids: tuple[UUID, ...]
    gap_count: int
    critical_candidate_count: int
    authoritative_critical_gap_ids: tuple[UUID, ...]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class GapDetectionReplay:
    status: Literal["succeeded", "failed"]
    gap_ids: tuple[UUID, ...]
    gap_count: int | None
    critical_candidate_count: int | None
    error_code: str | None


class GapDetectionSnapshotReader(Protocol):
    async def resolve_exact(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        completion_checklist_version: str,
    ) -> GapDetectionSnapshot | None: ...


class GapDetectionRepository(Protocol):
    async def resolve_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> GapDetectionReplay | None: ...

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> GapSnapshotRevisions | None: ...

    async def add_batch(self, gaps: tuple[GapWrite, ...]) -> None: ...

    async def mark_job_succeeded(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        gap_count: int,
        finished_at: datetime,
    ) -> None: ...


class GapDetectionUnitOfWork(Protocol):
    @property
    def repository(self) -> GapDetectionRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class GapDetectionUnitOfWorkFactory(Protocol):
    def __call__(self) -> GapDetectionUnitOfWork: ...


class GapDetectionEventLogger(Protocol):
    def emit(
        self, event_name: str, *, level: str = "INFO", **fields: object
    ) -> None: ...


class DetectGapsUseCase:
    def __init__(
        self,
        *,
        snapshot_reader: GapDetectionSnapshotReader,
        ai_execution: AIExecutionPort,
        usage_ledger: UsageLedger,
        critical_rule_evaluator: CriticalGapRuleEvaluator,
        unit_of_work_factory: GapDetectionUnitOfWorkFactory,
        event_logger: GapDetectionEventLogger,
        id_factory: Callable[[], UUID] = uuid4,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._ai_execution = ai_execution
        self._usage_ledger = usage_ledger
        self._critical_rule_evaluator = critical_rule_evaluator
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._wall_clock = wall_clock
        self._clock = monotonic_clock

    async def execute(self, command: DetectGapsCommand) -> GapDetectionResult:
        started_at = self._clock()
        self._event_logger.emit(
            "gap.detection_started",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            checklist_version=command.completion_checklist_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            status="started",
        )
        try:
            replay = await self._resolve_replay(command)
            if replay is not None:
                result = self._replay_result(replay)
                self._emit_replay(command, result, started_at)
                return result

            snapshot = await self._snapshot_reader.resolve_exact(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
                completion_checklist_version=command.completion_checklist_version,
            )
            if snapshot is None:
                raise GapDetectionError("gap_snapshot_unavailable")
            self._assert_snapshot(command, snapshot)
            batch = await self._execute_with_repair(command=command, snapshot=snapshot)
            critical = await self._critical_rule_evaluator.evaluate(
                snapshot=snapshot, batch=batch
            )
            self._validate_critical_evaluation(critical, batch)
            return await self._persist(
                command=command,
                snapshot=snapshot,
                batch=batch,
                critical=critical,
                started_at=started_at,
            )
        except Exception as error:
            reason_code = (
                error.reason_code
                if isinstance(error, GapDetectionError)
                else "gap_detection_failed"
            )
            if isinstance(error, GapSnapshotChangedError):
                event_name = "gap.snapshot_changed"
            else:
                event_name = "gap.detection_failed"
            self._event_logger.emit(
                event_name,
                level="ERROR",
                correlation_id=str(command.correlation_id),
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                context_version=command.context_version,
                checklist_version=command.completion_checklist_version,
                workflow_version=command.workflow_version,
                prompt_version=command.prompt_version,
                duration_ms=(self._clock() - started_at) * 1000,
                reason_code=reason_code,
                status="failed",
            )
            raise

    async def _resolve_replay(
        self, command: DetectGapsCommand
    ) -> GapDetectionReplay | None:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.repository.resolve_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )

    @staticmethod
    def _replay_result(replay: GapDetectionReplay) -> GapDetectionResult:
        if replay.status == "failed":
            raise GapDetectionError(replay.error_code or "gap_detection_failed")
        if replay.gap_count is None or replay.gap_count != len(replay.gap_ids):
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        return GapDetectionResult(
            gap_ids=replay.gap_ids,
            gap_count=replay.gap_count,
            critical_candidate_count=replay.critical_candidate_count or 0,
            authoritative_critical_gap_ids=(),
            replayed=True,
        )

    async def _execute_with_repair(
        self, *, command: DetectGapsCommand, snapshot: GapDetectionSnapshot
    ) -> CandidateGapBatch:
        response = await self._execute_and_meter(
            command=command,
            snapshot=snapshot,
            prompt_version=command.prompt_version,
            repair_no=0,
            repair=None,
        )
        try:
            return self._validate_response(response, snapshot)
        except GapDetectionError as error:
            if isinstance(error, GapDuplicateError):
                self._emit_duplicate_rejected(command)
            reason = _repair_reason(error)
            if reason is None or command.repair_policy.max_repairs == 0:
                raise
        rejected_output = response.data
        response = await self._execute_and_meter(
            command=command,
            snapshot=snapshot,
            prompt_version=command.repair_prompt_version,
            repair_no=1,
            repair={
                "repair_no": 1,
                "repair_policy_version": command.repair_policy.policy_version,
                "structured_error_codes": (reason,),
                "rejected_output": rejected_output,
            },
        )
        try:
            return self._validate_response(response, snapshot)
        except GapDetectionError as error:
            if isinstance(error, GapDuplicateError):
                self._emit_duplicate_rejected(command)
            if _repair_reason(error) is None:
                raise
            raise GapRepairExhaustedError from None

    async def _execute_and_meter(
        self,
        *,
        command: DetectGapsCommand,
        snapshot: GapDetectionSnapshot,
        prompt_version: str,
        repair_no: int,
        repair: Mapping[str, object] | None,
    ) -> StructuredAIResponse:
        input_context = _build_input_context(snapshot)
        if repair is not None:
            input_context = {**input_context, "repair": repair}
        response = await self._ai_execution.execute_structured(
            task_type=command.task_type,
            workflow_version=command.workflow_version,
            prompt_version=prompt_version,
            output_schema=command.output_schema,
            input_context=input_context,
            routing_policy=command.routing_policy,
            cost_budget=command.cost_budget,
            timeout_policy=command.timeout_policy,
            metadata={
                "account_id": str(command.account_id),
                "project_id": str(command.project_id),
                "job_id": str(command.job_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        await self._usage_ledger.append(
            UsageRecord(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                task_type=command.task_type,
                workflow_version=response.workflow_version,
                prompt_version=response.prompt_version,
                provider=response.provider,
                model=response.model,
                provider_request_id=response.provider_request_id,
                input_tokens=response.input_tokens,
                cached_input_tokens=response.cached_input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=Decimal(str(response.latency_ms)),
                status=response.status,
                error_code=None
                if response.status == "success"
                else "ai_execution_failed",
                retry_no=response.retry_no,
                repair_no=repair_no,
                estimated_cost=Decimal(str(response.estimated_cost)),
                pricing_version=command.pricing_version,
                correlation_id=command.correlation_id,
            )
        )
        if response.status != "success":
            raise GapDetectionError("provider_execution_failed")
        return response

    @staticmethod
    def _validate_response(
        response: StructuredAIResponse, snapshot: GapDetectionSnapshot
    ) -> CandidateGapBatch:
        if not isinstance(response.data, CandidateGapBatch):
            raise GapDetectionSchemaError("invalid_gap_candidate_batch")
        _reject_exact_duplicates(response.data)
        _validate_provenance(response.data, snapshot)
        _validate_affected_requirements(response.data, snapshot)
        return response.data

    async def _persist(
        self,
        *,
        command: DetectGapsCommand,
        snapshot: GapDetectionSnapshot,
        batch: CandidateGapBatch,
        critical: CriticalGapRuleEvaluation,
        started_at: float,
    ) -> GapDetectionResult:
        gap_ids = tuple(self._id_factory() for _ in batch.items)
        writes = tuple(
            GapWrite(
                id=gap_id,
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
                gap_type=candidate.gap_type,
                severity=candidate.severity,
                explanation=candidate.explanation,
                source_refs=candidate.source_refs,
                suggested_resolution_type=candidate.suggested_resolution_type,
                generation_job_id=command.job_id,
                affected_requirement_ids=tuple(
                    sorted(
                        candidate.affected_requirement_ids, key=lambda value: value.int
                    )
                ),
            )
            for gap_id, candidate in zip(gap_ids, batch.items, strict=True)
        )
        async with self._unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.repository
            replay = await repository.resolve_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )
            if replay is not None:
                result = self._replay_result(replay)
                self._emit_replay(command, result, started_at)
                return result
            actual = await repository.lock_snapshot_and_resolve_revisions(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            if actual is None:
                raise GapSnapshotChangedError
            self._assert_locked_snapshot(command, snapshot, actual)
            await repository.add_batch(writes)
            await repository.mark_job_succeeded(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                gap_count=len(writes),
                finished_at=self._wall_clock(),
            )
            await unit_of_work.commit()

        critical_gap_ids = tuple(
            gap_ids[index] for index in critical.authoritative_candidate_indexes
        )
        result = GapDetectionResult(
            gap_ids=gap_ids,
            gap_count=len(gap_ids),
            critical_candidate_count=sum(
                candidate.severity == "critical" for candidate in batch.items
            ),
            authoritative_critical_gap_ids=critical_gap_ids,
        )
        self._event_logger.emit(
            "gap.detection_completed",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            checklist_version=command.completion_checklist_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            candidate_count=len(batch.items),
            gap_count=result.gap_count,
            critical_candidate_count=result.critical_candidate_count,
            duration_ms=(self._clock() - started_at) * 1000,
            status="success",
        )
        return result

    @staticmethod
    def _assert_snapshot(
        command: DetectGapsCommand, snapshot: GapDetectionSnapshot
    ) -> None:
        if (
            snapshot.context_version != command.context_version
            or snapshot.completion_checklist_version
            != command.completion_checklist_version
            or snapshot.context_item_revisions != command.context_item_revisions
            or snapshot.requirement_revisions != command.requirement_revisions
        ):
            raise GapSnapshotChangedError

    @staticmethod
    def _assert_locked_snapshot(
        command: DetectGapsCommand,
        original: GapDetectionSnapshot,
        actual: GapSnapshotRevisions,
    ) -> None:
        if (
            actual.project_type != original.project_type
            or actual.context_item_revisions != command.context_item_revisions
            or actual.requirement_revisions != command.requirement_revisions
        ):
            raise GapSnapshotChangedError

    @staticmethod
    def _validate_critical_evaluation(
        evaluation: CriticalGapRuleEvaluation, batch: CandidateGapBatch
    ) -> None:
        if any(
            index >= len(batch.items)
            for index in evaluation.authoritative_candidate_indexes
        ):
            raise GapDetectionError("invalid_critical_rule_evaluation")

    def _emit_replay(
        self,
        command: DetectGapsCommand,
        result: GapDetectionResult,
        started_at: float,
    ) -> None:
        self._event_logger.emit(
            "gap.replay_served",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            checklist_version=command.completion_checklist_version,
            gap_count=result.gap_count,
            duration_ms=(self._clock() - started_at) * 1000,
            status="success",
        )

    def _emit_duplicate_rejected(self, command: DetectGapsCommand) -> None:
        self._event_logger.emit(
            "gap.duplicate_rejected",
            level="ERROR",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            checklist_version=command.completion_checklist_version,
            reason_code="duplicate_gap",
            status="rejected",
        )


def _reject_exact_duplicates(batch: CandidateGapBatch) -> None:
    identities: set[tuple[object, ...]] = set()
    for candidate in batch.items:
        if candidate.exact_identity in identities:
            raise GapDuplicateError
        identities.add(candidate.exact_identity)


def _validate_provenance(
    batch: CandidateGapBatch, snapshot: GapDetectionSnapshot
) -> None:
    allowed = {
        reference.identity()
        for item in snapshot.context_items
        for reference in item.source_refs
    }
    allowed.update(
        reference.identity()
        for item in snapshot.requirements
        for reference in item.source_refs
    )
    for candidate in batch.items:
        for reference in candidate.source_refs:
            if reference.identity() not in allowed:
                raise GapDetectionProvenanceError(
                    "source_reference_outside_gap_snapshot"
                )


def _validate_affected_requirements(
    batch: CandidateGapBatch, snapshot: GapDetectionSnapshot
) -> None:
    allowed = {requirement.id for requirement in snapshot.requirements}
    for candidate in batch.items:
        if len(set(candidate.affected_requirement_ids)) != len(
            candidate.affected_requirement_ids
        ) or any(
            requirement_id not in allowed
            for requirement_id in candidate.affected_requirement_ids
        ):
            raise GapAffectedRequirementError("requirement_outside_gap_snapshot")


def _build_input_context(snapshot: GapDetectionSnapshot) -> Mapping[str, object]:
    return {
        "project_type": snapshot.project_type,
        "context_version": snapshot.context_version,
        "completion_checklist_version": snapshot.completion_checklist_version,
        "context_items": tuple(
            {
                "context_item_id": str(item.id),
                "item_type": item.item_type,
                "status": item.status,
                "content": item.content,
                "source_refs": tuple(
                    _source_reference_dict(ref) for ref in item.source_refs
                ),
            }
            for item in snapshot.context_items
        ),
        "requirements": tuple(
            {
                "requirement_id": str(item.id),
                "category": item.category,
                "title": item.title,
                "description": item.description,
                "priority": item.priority,
                "status": item.status,
                "source_refs": tuple(
                    _source_reference_dict(ref) for ref in item.source_refs
                ),
            }
            for item in snapshot.requirements
        ),
    }


def _source_reference_dict(reference: GapSourceReference) -> Mapping[str, object]:
    value: dict[str, object] = {
        "source_id": str(reference.source_id),
        "source_version_id": str(reference.source_version_id),
    }
    if reference.start_offset is not None:
        value["start_offset"] = reference.start_offset
        value["end_offset"] = reference.end_offset
    return value


def _repair_reason(error: GapDetectionError) -> str | None:
    if isinstance(error, GapDetectionSchemaError):
        return "schema_invalid"
    if isinstance(error, GapDetectionProvenanceError):
        return "invalid_source_reference"
    if isinstance(error, GapAffectedRequirementError):
        return "invalid_affected_requirement"
    if isinstance(error, GapDuplicateError):
        return "duplicate_gap"
    return None


def _assert_sorted_unique_context_revisions(
    revisions: tuple[ContextItemRevision, ...],
) -> None:
    canonical = tuple(sorted(revisions, key=lambda value: value.context_item_id.int))
    if canonical != revisions or len(
        {value.context_item_id for value in revisions}
    ) != len(revisions):
        raise ValueError("Context Item revision vector must be sorted and unique")


def _assert_sorted_unique_requirement_revisions(
    revisions: tuple[RequirementRevision, ...],
) -> None:
    canonical = tuple(sorted(revisions, key=lambda value: value.requirement_id.int))
    if canonical != revisions or len(
        {value.requirement_id for value in revisions}
    ) != len(revisions):
        raise ValueError("Requirement revision vector must be sorted and unique")
