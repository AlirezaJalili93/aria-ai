from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from types import TracebackType
from typing import Literal, Protocol, Self, TypedDict
from uuid import UUID, uuid4

from aria_observability import (  # type: ignore[attr-defined]
    NoOpOperationalMetrics,
    OperationalMetrics,
    emit_product_analytics,
)

from aria_backend_application.ai_execution import AIExecutionPort, StructuredAIResponse
from aria_backend_application.usage_ledger import UsageLedger, UsageRecord

RequirementCategory = Literal[
    "functional", "content", "visual", "technical", "constraint", "business"
]
RequirementPriority = Literal["must", "should", "could"]
RequirementStatus = Literal["draft", "confirmed", "superseded", "removed"]
ContextItemStatus = Literal["proposed", "confirmed"]

REQUIREMENT_CATEGORIES: tuple[RequirementCategory, ...] = (
    "functional",
    "content",
    "visual",
    "technical",
    "constraint",
    "business",
)
REQUIREMENT_PRIORITIES = frozenset({"must", "should", "could"})
ELIGIBLE_CONTEXT_STATUSES = frozenset({"proposed", "confirmed"})


class RequirementRepairEventFields(TypedDict):
    correlation_id: str
    account_id: str
    project_id: str
    job_id: str
    context_version: int
    workflow_version: str
    prompt_version: str
    repair_no: int
    reason_code: str
    status: str


class RequirementGenerationError(RuntimeError):
    """A safe, provider-neutral Requirement generation failure."""

    retryable = False

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class RequirementGenerationSchemaError(RequirementGenerationError):
    """The provider output does not satisfy the approved candidate schema."""


class RequirementGenerationProvenanceError(RequirementGenerationError):
    """A candidate reference is not part of the immutable Context snapshot."""


class RequirementDuplicateClassificationError(RequirementGenerationError):
    code = "DUPLICATE_CLASSIFICATION_CONFLICT"

    def __init__(self) -> None:
        super().__init__("duplicate_classification_conflict")


class RequirementSupportClassificationError(RequirementGenerationError):
    """The approved support-classification validator rejected the Batch."""


class RequirementSnapshotChangedError(RequirementGenerationError):
    code = "CONTEXT_SNAPSHOT_CHANGED"
    retryable = False

    def __init__(self) -> None:
        super().__init__("context_snapshot_changed")


class RequirementInsufficientContextError(RequirementGenerationError):
    code = "INSUFFICIENT_CONTEXT"
    retryable = False

    def __init__(self) -> None:
        super().__init__("insufficient_context")


class RequirementRepairExhaustedError(RequirementGenerationError):
    code = "REQUIREMENT_REPAIR_EXHAUSTED"
    retryable = False

    def __init__(self) -> None:
        super().__init__("requirement_repair_exhausted")


class RequirementGenerationRepositoryError(RequirementGenerationError):
    """A declared Requirement generation persistence failure."""


@dataclass(frozen=True, slots=True)
class RequirementSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        absent = self.start_offset is None and self.end_offset is None
        present = self.start_offset is not None and self.end_offset is not None
        if not absent and not present:
            raise RequirementGenerationSchemaError("invalid_source_reference_shape")
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
                raise RequirementGenerationSchemaError("invalid_source_reference_offsets")

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
class RequirementContextItem:
    id: UUID
    updated_at: datetime
    item_type: str
    status: ContextItemStatus
    content: str
    source_refs: tuple[RequirementSourceReference, ...]

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Context Item updated_at must be timezone-aware")
        if self.status not in ELIGIBLE_CONTEXT_STATUSES:
            raise ValueError("Context Item is not eligible for Requirement generation")
        if not isinstance(self.content, str):
            raise TypeError("Context Item content must be text")

    @property
    def revision(self) -> ContextItemRevision:
        return ContextItemRevision(self.id, self.updated_at)


@dataclass(frozen=True, slots=True)
class RequirementContextSnapshot:
    project_type: str
    context_version: int
    items: tuple[RequirementContextItem, ...]

    @property
    def revision_vector(self) -> tuple[ContextItemRevision, ...]:
        return tuple(
            sorted(
                (item.revision for item in self.items),
                key=lambda value: value.context_item_id.int,
            )
        )


@dataclass(frozen=True, slots=True)
class CandidateRequirement:
    title: str
    description: str
    category: RequirementCategory
    priority: RequirementPriority
    source_refs: tuple[RequirementSourceReference, ...]
    confidence: Decimal | None
    unsupported: bool
    duplicate_group_key: str | None = None
    conflict_group_key: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not isinstance(self.description, str):
            raise RequirementGenerationSchemaError("invalid_requirement_text")
        if self.category not in REQUIREMENT_CATEGORIES:
            raise RequirementGenerationSchemaError("invalid_requirement_category")
        if self.priority not in REQUIREMENT_PRIORITIES:
            raise RequirementGenerationSchemaError("invalid_requirement_priority")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(reference, RequirementSourceReference) for reference in self.source_refs
        ):
            raise RequirementGenerationSchemaError("invalid_requirement_source_refs")
        if self.confidence is not None and (
            not isinstance(self.confidence, Decimal)
            or self.confidence < Decimal(0)
            or self.confidence > Decimal(1)
        ):
            raise RequirementGenerationSchemaError("invalid_requirement_confidence")
        if not isinstance(self.unsupported, bool):
            raise RequirementGenerationSchemaError("invalid_requirement_support_flag")
        if self.duplicate_group_key is not None and not isinstance(
            self.duplicate_group_key, str
        ):
            raise RequirementGenerationSchemaError("invalid_duplicate_group_key")
        if self.conflict_group_key is not None and not isinstance(
            self.conflict_group_key, str
        ):
            raise RequirementGenerationSchemaError("invalid_conflict_group_key")

    @property
    def semantic_identity(self) -> tuple[str, str, str, str, bool]:
        return (
            self.title,
            self.description,
            self.category,
            self.priority,
            self.unsupported,
        )


@dataclass(frozen=True, slots=True)
class CandidateRequirementBatch:
    items: tuple[CandidateRequirement, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, CandidateRequirement) for item in self.items
        ):
            raise RequirementGenerationSchemaError("invalid_requirement_candidate_batch")


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementRepairPolicy:
    policy_version: str
    max_repairs: int

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise ValueError("Requirement repair policy version is required")
        if isinstance(self.max_repairs, bool) or self.max_repairs not in (0, 1):
            raise ValueError("Sprint 1 Requirement repair permits max_repairs 0 or 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateRequirementsCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ContextItemRevision, ...]
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_prompt_version: str
    repair_policy: RequirementRepairPolicy
    pricing_version: str
    output_schema: Mapping[str, object]
    routing_policy: Mapping[str, object]
    cost_budget: Mapping[str, object]
    timeout_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")
        canonical = tuple(
            sorted(self.context_item_revisions, key=lambda value: value.context_item_id.int)
        )
        if canonical != self.context_item_revisions or len(
            {value.context_item_id for value in canonical}
        ) != len(canonical):
            raise ValueError("Context Item revision vector must be sorted and unique")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExistingRequirement:
    id: UUID
    category: RequirementCategory
    title: str
    description: str
    priority: RequirementPriority
    status: RequirementStatus
    source_refs: tuple[RequirementSourceReference, ...]
    confidence: Decimal | None
    is_unsupported: bool
    duplicate_group_key: str | None
    generation_job_id: UUID | None

    @property
    def semantic_identity(self) -> tuple[str, str, str, str, bool]:
        return (
            self.title,
            self.description,
            self.category,
            self.priority,
            self.is_unsupported,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementWrite:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    category: RequirementCategory
    title: str
    description: str
    priority: RequirementPriority
    source_refs: tuple[RequirementSourceReference, ...]
    confidence: Decimal | None
    is_unsupported: bool
    duplicate_group_key: str | None
    generation_job_id: UUID
    status: Literal["draft"] = "draft"
    created_by_type: Literal["ai"] = "ai"
    created_by: None = None


@dataclass(frozen=True, slots=True)
class RequirementConflictEvent:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    requirement_ids: tuple[UUID, ...]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class RequirementGenerationResult:
    requirement_ids: tuple[UUID, ...]
    persisted_count: int
    unsupported_count: int
    duplicate_count: int
    conflict_count: int
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class RequirementGenerationReplay:
    status: Literal["succeeded", "failed"]
    requirements: tuple[ExistingRequirement, ...]
    error_code: str | None


class RequirementContextSnapshotReader(Protocol):
    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> RequirementContextSnapshot | None: ...


class RequirementSupportValidator(Protocol):
    async def validate(
        self,
        *,
        batch: CandidateRequirementBatch,
        snapshot: RequirementContextSnapshot,
    ) -> None: ...


class RequirementGenerationRepository(Protocol):
    async def resolve_generation_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> RequirementGenerationReplay | None: ...

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ContextItemRevision, ...] | None: ...

    async def list_existing_for_merge(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ExistingRequirement, ...]: ...

    async def replace_source_refs(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        source_refs: tuple[RequirementSourceReference, ...],
    ) -> None: ...

    async def add_batch(self, requirements: tuple[RequirementWrite, ...]) -> None: ...

    async def add_conflict_events(
        self, events: tuple[RequirementConflictEvent, ...]
    ) -> None: ...


class RequirementGenerationUnitOfWork(Protocol):
    @property
    def repository(self) -> RequirementGenerationRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class RequirementGenerationUnitOfWorkFactory(Protocol):
    def __call__(self) -> RequirementGenerationUnitOfWork: ...


class RequirementGenerationEventLogger(Protocol):
    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None: ...


class GenerateRequirementsUseCaseProtocol(Protocol):
    async def execute(
        self, command: GenerateRequirementsCommand
    ) -> RequirementGenerationResult: ...


class GenerateRequirementsUseCase:
    def __init__(
        self,
        *,
        snapshot_reader: RequirementContextSnapshotReader,
        ai_execution: AIExecutionPort,
        usage_ledger: UsageLedger,
        support_validator: RequirementSupportValidator,
        unit_of_work_factory: RequirementGenerationUnitOfWorkFactory,
        event_logger: RequirementGenerationEventLogger,
        operational_metrics: OperationalMetrics | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._ai_execution = ai_execution
        self._usage_ledger = usage_ledger
        self._support_validator = support_validator
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._operational_metrics = operational_metrics or NoOpOperationalMetrics()
        self._id_factory = id_factory
        self._wall_clock = wall_clock
        self._clock = monotonic_clock

    async def execute(
        self, command: GenerateRequirementsCommand
    ) -> RequirementGenerationResult:
        started_at = self._clock()
        self._event_logger.emit(
            "requirements.generation_started",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            repair_no=0,
            status="started",
        )
        try:
            replay = await self._resolve_replay(command)
            if replay is not None:
                result = self._resolve_replay_result(replay)
                self._event_logger.emit(
                    "requirements.replay_served",
                    correlation_id=str(command.correlation_id),
                    account_id=str(command.account_id),
                    project_id=str(command.project_id),
                    job_id=str(command.job_id),
                    context_version=command.context_version,
                    persisted_count=result.persisted_count,
                    unsupported_count=result.unsupported_count,
                    duration_ms=(self._clock() - started_at) * 1000,
                    status="success",
                )
                return result

            snapshot = await self._snapshot_reader.resolve_exact(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            if snapshot is None or snapshot.context_version != command.context_version:
                raise RequirementInsufficientContextError
            self._assert_snapshot(command, snapshot.revision_vector)
            if not snapshot.items:
                raise RequirementInsufficientContextError

            batch, duplicate_count = await self._execute_with_repair(
                command=command, snapshot=snapshot
            )
            return await self._persist(
                command=command,
                snapshot=snapshot,
                batch=batch,
                duplicate_count=duplicate_count,
                started_at=started_at,
            )
        except Exception as error:
            reason_code = (
                error.reason_code
                if isinstance(error, RequirementGenerationError)
                else "requirement_generation_failed"
            )
            event_name = (
                "requirements.snapshot_changed"
                if isinstance(error, RequirementSnapshotChangedError)
                else "requirements.generation_failed"
            )
            self._event_logger.emit(
                event_name,
                level="ERROR",
                correlation_id=str(command.correlation_id),
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                context_version=command.context_version,
                workflow_version=command.workflow_version,
                prompt_version=command.prompt_version,
                duration_ms=(self._clock() - started_at) * 1000,
                reason_code=reason_code,
                status="failed",
            )
            raise

    async def _resolve_replay(
        self, command: GenerateRequirementsCommand
    ) -> RequirementGenerationReplay | None:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.repository.resolve_generation_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )

    @staticmethod
    def _resolve_replay_result(
        replay: RequirementGenerationReplay,
    ) -> RequirementGenerationResult:
        if replay.status == "failed":
            raise RequirementGenerationError(
                replay.error_code or "requirement_generation_failed"
            )
        return _replay_result(replay.requirements)

    async def _execute_with_repair(
        self,
        *,
        command: GenerateRequirementsCommand,
        snapshot: RequirementContextSnapshot,
    ) -> tuple[CandidateRequirementBatch, int]:
        response = await self._execute_and_meter(
            command=command,
            prompt_version=command.prompt_version,
            input_context=_build_input_context(command, snapshot),
            repair_no=0,
        )
        try:
            return await self._validate_response(response=response, snapshot=snapshot)
        except RequirementGenerationError as error:
            repair_reason = _repair_reason(error)
            if repair_reason is None or command.repair_policy.max_repairs == 0:
                raise

        rejected_output = response.data
        for repair_no in range(1, command.repair_policy.max_repairs + 1):
            repair_started_at = self._clock()
            self._event_logger.emit(
                "requirements.repair_started",
                **_repair_event_fields(command, repair_no, repair_reason, "started"),
            )
            response = await self._execute_and_meter(
                command=command,
                prompt_version=command.repair_prompt_version,
                input_context=_build_repair_input_context(
                    command,
                    snapshot,
                    rejected_output,
                    repair_no,
                    repair_reason,
                ),
                repair_no=repair_no,
            )
            try:
                validated = await self._validate_response(
                    response=response, snapshot=snapshot
                )
            except RequirementGenerationError as error:
                next_reason = _repair_reason(error)
                if next_reason is None:
                    raise
                duration_ms = (self._clock() - repair_started_at) * 1000
                self._event_logger.emit(
                    "requirements.repair_failed",
                    level="ERROR",
                    duration_ms=duration_ms,
                    **_repair_event_fields(
                        command, repair_no, next_reason, "failed"
                    ),
                )
                self._event_logger.emit(
                    "requirements.repair_exhausted",
                    level="ERROR",
                    duration_ms=duration_ms,
                    **_repair_event_fields(
                        command, repair_no, next_reason, "exhausted"
                    ),
                )
                raise RequirementRepairExhaustedError from None
            self._event_logger.emit(
                "requirements.repair_succeeded",
                duration_ms=(self._clock() - repair_started_at) * 1000,
                **_repair_event_fields(
                    command, repair_no, repair_reason, "success"
                ),
            )
            return validated
        raise RequirementRepairExhaustedError

    async def _execute_and_meter(
        self,
        *,
        command: GenerateRequirementsCommand,
        prompt_version: str,
        input_context: Mapping[str, object],
        repair_no: int,
    ) -> StructuredAIResponse:
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
                provider_attempt_id=response.provider_attempt_id,
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
                error_code=None if response.status == "success" else "ai_execution_failed",
                retry_no=response.retry_no,
                repair_no=repair_no,
                estimated_cost=Decimal(str(response.estimated_cost)),
                pricing_version=command.pricing_version,
                correlation_id=command.correlation_id,
            )
        )
        if response.status != "success":
            raise RequirementGenerationError("provider_execution_failed")
        return response

    async def _validate_response(
        self,
        *,
        response: StructuredAIResponse,
        snapshot: RequirementContextSnapshot,
    ) -> tuple[CandidateRequirementBatch, int]:
        try:
            if not isinstance(response.data, CandidateRequirementBatch):
                raise RequirementGenerationSchemaError("invalid_requirement_candidate_batch")
            if not response.data.items:
                raise RequirementInsufficientContextError
            merged, duplicate_count = _merge_batch_duplicates(response.data)
            _validate_provenance(merged, snapshot)
            await self._support_validator.validate(batch=merged, snapshot=snapshot)
            return merged, duplicate_count
        except RequirementGenerationError as error:
            self._record_validation_failure(
                "schema" if isinstance(error, RequirementGenerationSchemaError) else "business"
            )
            raise

    def _record_validation_failure(self, validation_kind: str) -> None:
        with suppress(Exception):
            self._operational_metrics.record_ai_validation_failure(
                workflow="requirement_generation", validation_kind=validation_kind
            )

    async def _persist(
        self,
        *,
        command: GenerateRequirementsCommand,
        snapshot: RequirementContextSnapshot,
        batch: CandidateRequirementBatch,
        duplicate_count: int,
        started_at: float,
    ) -> RequirementGenerationResult:
        async with self._unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.repository
            replay = await repository.resolve_generation_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )
            if replay is not None:
                result = self._resolve_replay_result(replay)
                self._event_logger.emit(
                    "requirements.replay_served",
                    correlation_id=str(command.correlation_id),
                    account_id=str(command.account_id),
                    project_id=str(command.project_id),
                    job_id=str(command.job_id),
                    context_version=command.context_version,
                    persisted_count=result.persisted_count,
                    unsupported_count=result.unsupported_count,
                    duration_ms=(self._clock() - started_at) * 1000,
                    status="success",
                )
                return result
            current_revisions = await repository.lock_snapshot_and_resolve_revisions(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            if current_revisions is None:
                raise RequirementSnapshotChangedError
            self._assert_snapshot(command, current_revisions)
            existing = await repository.list_existing_for_merge(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            writes, source_updates, requirement_ids, conflict_eligible = _plan_persistence(
                command=command,
                candidates=batch.items,
                existing=existing,
                id_factory=self._id_factory,
            )
            for requirement_id, refs in source_updates:
                await repository.replace_source_refs(
                    account_id=command.account_id,
                    project_id=command.project_id,
                    requirement_id=requirement_id,
                    source_refs=refs,
                )
            await repository.add_batch(writes)

            conflict_groups = _resolve_conflict_groups(
                batch.items, requirement_ids, conflict_eligible
            )
            events = tuple(
                RequirementConflictEvent(
                    id=self._id_factory(),
                    account_id=command.account_id,
                    project_id=command.project_id,
                    context_version=command.context_version,
                    requirement_ids=ids,
                    occurred_at=self._wall_clock(),
                )
                for ids in conflict_groups
            )
            await repository.add_conflict_events(events)
            await unit_of_work.commit()

        unsupported_count = sum(item.unsupported for item in batch.items)
        result = RequirementGenerationResult(
            requirement_ids=requirement_ids,
            persisted_count=len(writes),
            unsupported_count=unsupported_count,
            duplicate_count=duplicate_count,
            conflict_count=len(events),
        )
        if events:
            self._event_logger.emit(
                "requirements.conflict_detected",
                correlation_id=str(command.correlation_id),
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                context_version=command.context_version,
                conflict_count=len(events),
                status="success",
            )
        self._event_logger.emit(
            "requirements.generation_completed",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            candidate_count=len(batch.items),
            persisted_count=result.persisted_count,
            unsupported_count=result.unsupported_count,
            duplicate_count=result.duplicate_count,
            conflict_count=result.conflict_count,
            duration_ms=(self._clock() - started_at) * 1000,
            status="success",
        )
        emit_product_analytics(
            self._event_logger,
            event_name="requirements_generated",
            logical_id=command.job_id,
            account_id=command.account_id,
            project_id=command.project_id,
            properties={"context_version": command.context_version},
        )
        return result

    @staticmethod
    def _assert_snapshot(
        command: GenerateRequirementsCommand,
        actual: tuple[ContextItemRevision, ...],
    ) -> None:
        if actual != command.context_item_revisions:
            raise RequirementSnapshotChangedError


def _merge_batch_duplicates(
    batch: CandidateRequirementBatch,
) -> tuple[CandidateRequirementBatch, int]:
    merged: list[CandidateRequirement] = []
    positions: dict[tuple[object, ...], int] = {}
    duplicate_count = 0
    for candidate in batch.items:
        identity: tuple[object, ...]
        if candidate.duplicate_group_key is not None:
            identity = ("group", candidate.duplicate_group_key)
        else:
            identity = ("exact", *candidate.semantic_identity)
        position = positions.get(identity)
        if position is None:
            positions[identity] = len(merged)
            merged.append(candidate)
            continue
        canonical = merged[position]
        if (
            canonical.semantic_identity != candidate.semantic_identity
            or canonical.conflict_group_key != candidate.conflict_group_key
        ):
            raise RequirementDuplicateClassificationError
        merged[position] = replace(
            canonical,
            source_refs=_stable_union(canonical.source_refs, candidate.source_refs),
        )
        duplicate_count += 1
    return CandidateRequirementBatch(tuple(merged)), duplicate_count


def _validate_provenance(
    batch: CandidateRequirementBatch, snapshot: RequirementContextSnapshot
) -> None:
    allowed = {
        reference.identity()
        for item in snapshot.items
        for reference in item.source_refs
    }
    for candidate in batch.items:
        if not candidate.unsupported and not candidate.source_refs:
            raise RequirementGenerationProvenanceError("supported_provenance_required")
        for reference in candidate.source_refs:
            if reference.identity() not in allowed:
                raise RequirementGenerationProvenanceError(
                    "source_reference_outside_context_snapshot"
                )


def _plan_persistence(
    *,
    command: GenerateRequirementsCommand,
    candidates: tuple[CandidateRequirement, ...],
    existing: tuple[ExistingRequirement, ...],
    id_factory: Callable[[], UUID],
) -> tuple[
    tuple[RequirementWrite, ...],
    tuple[tuple[UUID, tuple[RequirementSourceReference, ...]], ...],
    tuple[UUID, ...],
    tuple[bool, ...],
]:
    writes: list[RequirementWrite] = []
    updates: list[tuple[UUID, tuple[RequirementSourceReference, ...]]] = []
    requirement_ids: list[UUID] = []
    conflict_eligible: list[bool] = []
    mutable_existing = list(existing)
    for candidate in candidates:
        matches = [
            item
            for item in mutable_existing
            if (
                candidate.duplicate_group_key is not None
                and item.duplicate_group_key == candidate.duplicate_group_key
            )
            or (
                candidate.duplicate_group_key is None
                and item.duplicate_group_key is None
                and item.semantic_identity == candidate.semantic_identity
            )
        ]
        active = next((item for item in matches if item.status != "removed"), None)
        target = active or (matches[0] if matches else None)
        if target is not None and target.status != "removed":
            refs = _stable_union(target.source_refs, candidate.source_refs)
            if refs != target.source_refs:
                updates.append((target.id, refs))
            requirement_ids.append(target.id)
            conflict_eligible.append(True)
            continue
        if target is not None and not _has_new_evidence(
            target.source_refs, candidate.source_refs
        ):
            requirement_ids.append(target.id)
            conflict_eligible.append(False)
            continue
        requirement_id = id_factory()
        write = RequirementWrite(
            id=requirement_id,
            account_id=command.account_id,
            project_id=command.project_id,
            context_version=command.context_version,
            category=candidate.category,
            title=candidate.title,
            description=candidate.description,
            priority=candidate.priority,
            source_refs=candidate.source_refs,
            confidence=candidate.confidence,
            is_unsupported=candidate.unsupported,
            duplicate_group_key=candidate.duplicate_group_key,
            generation_job_id=command.job_id,
        )
        writes.append(write)
        requirement_ids.append(requirement_id)
        conflict_eligible.append(True)
        mutable_existing.append(
            ExistingRequirement(
                id=requirement_id,
                category=candidate.category,
                title=candidate.title,
                description=candidate.description,
                priority=candidate.priority,
                status="draft",
                source_refs=candidate.source_refs,
                confidence=candidate.confidence,
                is_unsupported=candidate.unsupported,
                duplicate_group_key=candidate.duplicate_group_key,
                generation_job_id=command.job_id,
            )
        )
    return (
        tuple(writes),
        tuple(updates),
        tuple(requirement_ids),
        tuple(conflict_eligible),
    )


def _resolve_conflict_groups(
    candidates: tuple[CandidateRequirement, ...],
    requirement_ids: tuple[UUID, ...],
    conflict_eligible: tuple[bool, ...],
) -> tuple[tuple[UUID, ...], ...]:
    groups: dict[str, list[UUID]] = {}
    for candidate, requirement_id, eligible in zip(
        candidates, requirement_ids, conflict_eligible, strict=True
    ):
        if eligible and candidate.conflict_group_key is not None:
            groups.setdefault(candidate.conflict_group_key, []).append(requirement_id)
    return tuple(
        tuple(dict.fromkeys(ids))
        for ids in groups.values()
        if len(dict.fromkeys(ids)) >= 2
    )


def _stable_union(
    left: tuple[RequirementSourceReference, ...],
    right: tuple[RequirementSourceReference, ...],
) -> tuple[RequirementSourceReference, ...]:
    result = list(left)
    seen = {reference.identity() for reference in left}
    for reference in right:
        if reference.identity() not in seen:
            result.append(reference)
            seen.add(reference.identity())
    return tuple(result)


def _has_new_evidence(
    existing: tuple[RequirementSourceReference, ...],
    candidate: tuple[RequirementSourceReference, ...],
) -> bool:
    current = {reference.identity() for reference in existing}
    return any(reference.identity() not in current for reference in candidate)


def _replay_result(
    requirements: tuple[ExistingRequirement, ...]
) -> RequirementGenerationResult:
    return RequirementGenerationResult(
        requirement_ids=tuple(item.id for item in requirements),
        persisted_count=len(requirements),
        unsupported_count=sum(item.is_unsupported for item in requirements),
        duplicate_count=0,
        conflict_count=0,
        replayed=True,
    )


def _build_input_context(
    command: GenerateRequirementsCommand,
    snapshot: RequirementContextSnapshot,
) -> Mapping[str, object]:
    return {
        "project_type": snapshot.project_type,
        "context_version": command.context_version,
        "allowed_categories": REQUIREMENT_CATEGORIES,
        "context_items": tuple(
            {
                "context_item_id": str(item.id),
                "item_type": item.item_type,
                "status": item.status,
                "content": item.content,
                "source_refs": tuple(
                    {
                        "source_id": str(reference.source_id),
                        "source_version_id": str(reference.source_version_id),
                        **(
                            {
                                "start_offset": reference.start_offset,
                                "end_offset": reference.end_offset,
                            }
                            if reference.start_offset is not None
                            else {}
                        ),
                    }
                    for reference in item.source_refs
                ),
            }
            for item in snapshot.items
        ),
    }


def _build_repair_input_context(
    command: GenerateRequirementsCommand,
    snapshot: RequirementContextSnapshot,
    rejected_output: object,
    repair_no: int,
    reason_code: str,
) -> Mapping[str, object]:
    return {
        **_build_input_context(command, snapshot),
        "repair": {
            "repair_no": repair_no,
            "repair_policy_version": command.repair_policy.policy_version,
            "structured_error_codes": (reason_code,),
            "rejected_output": rejected_output,
        },
    }


def _repair_reason(error: RequirementGenerationError) -> str | None:
    if isinstance(error, RequirementGenerationSchemaError):
        return "schema_invalid"
    if isinstance(error, RequirementGenerationProvenanceError):
        return "invalid_source_reference"
    if isinstance(error, RequirementDuplicateClassificationError):
        return "duplicate_classification_conflict"
    if isinstance(error, RequirementSupportClassificationError):
        return "support_classification_defect"
    return None


def _repair_event_fields(
    command: GenerateRequirementsCommand,
    repair_no: int,
    reason_code: str,
    status: str,
) -> RequirementRepairEventFields:
    return {
        "correlation_id": str(command.correlation_id),
        "account_id": str(command.account_id),
        "project_id": str(command.project_id),
        "job_id": str(command.job_id),
        "context_version": command.context_version,
        "workflow_version": command.workflow_version,
        "prompt_version": command.repair_prompt_version,
        "repair_no": repair_no,
        "reason_code": reason_code,
        "status": status,
    }
