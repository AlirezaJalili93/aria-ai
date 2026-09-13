from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from types import TracebackType
from typing import Literal, Protocol, Self, TypedDict
from uuid import UUID, uuid4

from aria_observability import emit_product_analytics  # type: ignore[attr-defined]

from aria_backend_application.ai_execution import AIExecutionPort, StructuredAIResponse
from aria_backend_application.usage_ledger import UsageLedger, UsageRecord

ContextItemType = Literal[
    "fact", "assumption", "decision", "constraint", "reference", "unknown"
]


class ContextRepairEventFields(TypedDict):
    correlation_id: str
    account_id: str
    project_id: str
    job_id: str
    task_type: str
    workflow_version: str
    repair_prompt_version: str
    repair_policy_version: str
    repair_no: int
    max_repairs: int
    reason_code: str
    status: str
CONTEXT_ITEM_TYPES = frozenset(
    {"fact", "assumption", "decision", "constraint", "reference", "unknown"}
)


class ContextStructuringError(RuntimeError):
    """Safe provider-neutral Context Structuring failure."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class ContextStructuringSchemaError(ContextStructuringError):
    """The AI result did not satisfy the approved candidate schema."""


class ContextStructuringSourceError(ContextStructuringError):
    """The immutable Source snapshot or candidate provenance is invalid."""


class ContextStructuringValidationError(ContextStructuringError):
    """A business or unsupported-claim validation rejected the Batch."""


class ContextStructuringDuplicateError(ContextStructuringValidationError):
    code = "DUPLICATE_CONTEXT_ITEM"

    def __init__(self) -> None:
        super().__init__("duplicate_context_item")


class ContextStructuringRepositoryError(ContextStructuringError):
    """A declared Context Structuring persistence failure."""


class ContextRepairExhaustedError(ContextStructuringError):
    """All approved semantic Repair executions failed deterministic validation."""

    code = "CONTEXT_REPAIR_EXHAUSTED"
    retryable = False

    def __init__(self) -> None:
        super().__init__("context_repair_exhausted")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextRepairPolicy:
    policy_version: str
    max_repairs: int

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise ValueError("repair policy version is required")
        if isinstance(self.max_repairs, bool) or self.max_repairs not in (0, 1):
            raise ValueError("Sprint 1 repair policy permits max_repairs 0 or 1")


@dataclass(frozen=True, slots=True)
class CandidateSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        absent = self.start_offset is None and self.end_offset is None
        present = self.start_offset is not None and self.end_offset is not None
        if not absent and not present:
            raise ContextStructuringSchemaError("invalid_source_reference_shape")
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
                raise ContextStructuringSchemaError("invalid_source_reference_offsets")


@dataclass(frozen=True, slots=True)
class CandidateContextItem:
    item_type: ContextItemType
    content: str
    source_refs: tuple[CandidateSourceReference, ...]
    confidence: Decimal | None
    rationale_short: str | None = None

    def __post_init__(self) -> None:
        if self.item_type not in CONTEXT_ITEM_TYPES:
            raise ContextStructuringSchemaError("invalid_context_item_type")
        if not isinstance(self.content, str):
            raise ContextStructuringSchemaError("invalid_context_item_content")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(reference, CandidateSourceReference) for reference in self.source_refs
        ):
            raise ContextStructuringSchemaError("invalid_context_item_source_refs")
        if self.confidence is not None and (
            not isinstance(self.confidence, Decimal)
            or self.confidence < Decimal(0)
            or self.confidence > Decimal(1)
        ):
            raise ContextStructuringSchemaError("invalid_context_item_confidence")
        if self.rationale_short is not None and not isinstance(self.rationale_short, str):
            raise ContextStructuringSchemaError("invalid_context_item_rationale")


@dataclass(frozen=True, slots=True)
class CandidateContextBatch:
    items: tuple[CandidateContextItem, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, CandidateContextItem) for item in self.items
        ):
            raise ContextStructuringSchemaError("invalid_context_candidate_batch")


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    source_id: UUID
    source_version_id: UUID
    version_no: int
    canonical_text: str | None
    storage_ref: str | None

    def __post_init__(self) -> None:
        if (
            isinstance(self.version_no, bool)
            or not isinstance(self.version_no, int)
            or self.version_no < 1
        ):
            raise ContextStructuringSourceError("invalid_source_version")
        if self.canonical_text is None and self.storage_ref is None:
            raise ContextStructuringSourceError("ready_source_content_missing")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextStructuringCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_prompt_version: str
    repair_policy: ContextRepairPolicy
    pricing_version: str
    output_schema: Mapping[str, object]
    routing_policy: Mapping[str, object]
    cost_budget: Mapping[str, object]
    timeout_policy: Mapping[str, object]


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextVersionWrite:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    item_type: ContextItemType
    content: str
    source_refs: tuple[CandidateSourceReference, ...]
    confidence: Decimal | None
    status: Literal["proposed"] = "proposed"
    created_by_type: Literal["ai"] = "ai"
    created_by: None = None


@dataclass(frozen=True, slots=True)
class ContextStructuringResult:
    context_version: int
    item_count: int


class ContextSnapshotReader(Protocol):
    async def resolve_latest_ready(
        self, *, account_id: UUID, project_id: UUID
    ) -> tuple[SourceSnapshot, ...]: ...


class UnsupportedClaimValidator(Protocol):
    async def validate(
        self,
        *,
        batch: CandidateContextBatch,
        snapshot: tuple[SourceSnapshot, ...],
    ) -> None: ...


class ContextStructuringRepository(Protocol):
    async def allocate_next_version(self, *, account_id: UUID, project_id: UUID) -> int: ...

    async def add_batch(self, items: tuple[ContextVersionWrite, ...]) -> None: ...

    async def advance_project_version(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> None: ...


class ContextStructuringUnitOfWork(Protocol):
    @property
    def repository(self) -> ContextStructuringRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ContextStructuringUnitOfWorkFactory(Protocol):
    def __call__(self) -> ContextStructuringUnitOfWork: ...


class ContextStructuringEventLogger(Protocol):
    def emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None: ...


class ContextStructuringUseCaseProtocol(Protocol):
    async def execute(self, command: ContextStructuringCommand) -> ContextStructuringResult: ...


class ContextStructuringUseCase:
    def __init__(
        self,
        *,
        snapshot_reader: ContextSnapshotReader,
        ai_execution: AIExecutionPort,
        usage_ledger: UsageLedger,
        unsupported_claim_validator: UnsupportedClaimValidator,
        unit_of_work_factory: ContextStructuringUnitOfWorkFactory,
        event_logger: ContextStructuringEventLogger,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._ai_execution = ai_execution
        self._usage_ledger = usage_ledger
        self._unsupported_claim_validator = unsupported_claim_validator
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._clock = clock

    async def execute(self, command: ContextStructuringCommand) -> ContextStructuringResult:
        started_at = self._clock()
        self._event_logger.emit(
            "context.structuring_started",
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
        )
        emit_product_analytics(
            self._event_logger,
            event_name="structuring_started",
            logical_id=command.job_id,
            account_id=command.account_id,
            project_id=command.project_id,
            properties={},
        )
        try:
            snapshot = await self._snapshot_reader.resolve_latest_ready(
                account_id=command.account_id,
                project_id=command.project_id,
            )
            if not snapshot:
                raise ContextStructuringSourceError("ready_source_required")

            batch = await self._execute_with_repair(command=command, snapshot=snapshot)

            async with self._unit_of_work_factory() as unit_of_work:
                context_version = await unit_of_work.repository.allocate_next_version(
                    account_id=command.account_id,
                    project_id=command.project_id,
                )
                writes = tuple(
                    ContextVersionWrite(
                        id=self._id_factory(),
                        account_id=command.account_id,
                        project_id=command.project_id,
                        context_version=context_version,
                        item_type=item.item_type,
                        content=item.content,
                        source_refs=item.source_refs,
                        confidence=item.confidence,
                    )
                    for item in batch.items
                )
                await unit_of_work.repository.add_batch(writes)
                await unit_of_work.repository.advance_project_version(
                    account_id=command.account_id,
                    project_id=command.project_id,
                    context_version=context_version,
                )
                await unit_of_work.commit()

            result = ContextStructuringResult(
                context_version=context_version,
                item_count=len(batch.items),
            )
            self._event_logger.emit(
                "context.structuring_completed",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                context_version=context_version,
                duration_ms=(self._clock() - started_at) * 1000,
                status="success",
            )
            emit_product_analytics(
                self._event_logger,
                event_name="structuring_completed",
                logical_id=command.job_id,
                account_id=command.account_id,
                project_id=command.project_id,
                properties={"context_version": context_version},
            )
            return result
        except Exception as error:
            reason_code = (
                error.reason_code
                if isinstance(error, ContextStructuringError)
                else "context_structuring_failed"
            )
            self._event_logger.emit(
                "context.structuring_failed",
                level="ERROR",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                duration_ms=(self._clock() - started_at) * 1000,
                reason_code=reason_code,
                status="failed",
            )
            raise

    async def _execute_with_repair(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
    ) -> CandidateContextBatch:
        response = await self._execute_and_meter(
            command=command,
            prompt_version=command.prompt_version,
            input_context=_build_input_context(command, snapshot),
            repair_no=0,
        )
        try:
            return await self._validate_response(response=response, snapshot=snapshot)
        except ContextStructuringError as error:
            repair_reason = _repair_reason(error)
            if repair_reason is None or command.repair_policy.max_repairs == 0:
                raise

        rejected_output = response.data
        for repair_no in range(1, command.repair_policy.max_repairs + 1):
            repair_started_at = self._clock()
            self._event_logger.emit(
                "context.repair_started",
                **_repair_event_fields(
                    command=command,
                    repair_no=repair_no,
                    reason_code=repair_reason,
                    status="started",
                ),
            )
            response = await self._execute_and_meter(
                command=command,
                prompt_version=command.repair_prompt_version,
                input_context=_build_repair_input_context(
                    command=command,
                    snapshot=snapshot,
                    rejected_output=rejected_output,
                    repair_no=repair_no,
                    reason_code=repair_reason,
                ),
                repair_no=repair_no,
            )
            try:
                batch = await self._validate_response(response=response, snapshot=snapshot)
            except ContextStructuringError as error:
                next_reason = _repair_reason(error)
                if next_reason is None:
                    raise
                duration_ms = (self._clock() - repair_started_at) * 1000
                self._event_logger.emit(
                    "context.repair_failed",
                    level="ERROR",
                    duration_ms=duration_ms,
                    **_repair_event_fields(
                        command=command,
                        repair_no=repair_no,
                        reason_code=next_reason,
                        status="failed",
                    ),
                )
                if repair_no == command.repair_policy.max_repairs:
                    self._event_logger.emit(
                        "context.repair_exhausted",
                        level="ERROR",
                        duration_ms=duration_ms,
                        **_repair_event_fields(
                            command=command,
                            repair_no=repair_no,
                            reason_code=next_reason,
                            status="exhausted",
                        ),
                    )
                    raise ContextRepairExhaustedError from None
                rejected_output = response.data
                repair_reason = next_reason
                continue

            self._event_logger.emit(
                "context.repair_succeeded",
                duration_ms=(self._clock() - repair_started_at) * 1000,
                **_repair_event_fields(
                    command=command,
                    repair_no=repair_no,
                    reason_code=repair_reason,
                    status="success",
                ),
            )
            return batch

        raise ContextRepairExhaustedError

    async def _execute_and_meter(
        self,
        *,
        command: ContextStructuringCommand,
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
                error_code=None,
                retry_no=response.retry_no,
                repair_no=repair_no,
                estimated_cost=Decimal(str(response.estimated_cost)),
                pricing_version=command.pricing_version,
                correlation_id=command.correlation_id,
            )
        )
        return response

    async def _validate_response(
        self,
        *,
        response: StructuredAIResponse,
        snapshot: tuple[SourceSnapshot, ...],
    ) -> CandidateContextBatch:
        batch = _require_candidate_batch(response.data)
        _validate_candidate_batch(batch, snapshot)
        await self._unsupported_claim_validator.validate(batch=batch, snapshot=snapshot)
        return batch


def _require_candidate_batch(data: object) -> CandidateContextBatch:
    if not isinstance(data, CandidateContextBatch):
        raise ContextStructuringSchemaError("invalid_context_candidate_batch")
    return data


def _validate_candidate_batch(
    batch: CandidateContextBatch,
    snapshot: tuple[SourceSnapshot, ...],
) -> None:
    targets = {(source.source_id, source.source_version_id): source for source in snapshot}
    identities: set[tuple[str, str]] = set()
    for item in batch.items:
        identity = (item.item_type, item.content)
        if identity in identities:
            raise ContextStructuringDuplicateError
        identities.add(identity)
        if item.item_type == "fact" and not item.source_refs:
            raise ContextStructuringSourceError("fact_provenance_required")
        for reference in item.source_refs:
            target = targets.get((reference.source_id, reference.source_version_id))
            if target is None:
                raise ContextStructuringSourceError("source_reference_outside_snapshot")
            if reference.end_offset is not None and (
                target.canonical_text is None
                or reference.end_offset > len(target.canonical_text)
            ):
                raise ContextStructuringSourceError("source_reference_out_of_bounds")


def _build_input_context(
    command: ContextStructuringCommand,
    snapshot: tuple[SourceSnapshot, ...],
) -> Mapping[str, object]:
    return {
        "account_id": str(command.account_id),
        "project_id": str(command.project_id),
        "sources": tuple(
            {
                "source_id": str(source.source_id),
                "source_version_id": str(source.source_version_id),
                "version_no": source.version_no,
                "canonical_text": source.canonical_text,
                "storage_ref": source.storage_ref,
            }
            for source in snapshot
        ),
    }


def _build_repair_input_context(
    *,
    command: ContextStructuringCommand,
    snapshot: tuple[SourceSnapshot, ...],
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
            "original_execution_context": {
                "account_id": str(command.account_id),
                "project_id": str(command.project_id),
                "job_id": str(command.job_id),
                "correlation_id": str(command.correlation_id),
            },
        },
    }


def _repair_reason(error: ContextStructuringError) -> str | None:
    if isinstance(error, ContextStructuringDuplicateError):
        return "duplicate_candidate"
    if isinstance(error, ContextStructuringSchemaError):
        return "schema_invalid"
    if isinstance(error, ContextStructuringSourceError) and error.reason_code in {
        "fact_provenance_required",
        "source_reference_outside_snapshot",
        "source_reference_out_of_bounds",
    }:
        return "invalid_source_reference"
    if (
        isinstance(error, ContextStructuringValidationError)
        and error.reason_code == "unsupported_claim"
    ):
        return "unsupported_claim"
    return None


def _repair_event_fields(
    *,
    command: ContextStructuringCommand,
    repair_no: int,
    reason_code: str,
    status: str,
) -> ContextRepairEventFields:
    return {
        "correlation_id": str(command.correlation_id),
        "account_id": str(command.account_id),
        "project_id": str(command.project_id),
        "job_id": str(command.job_id),
        "task_type": command.task_type,
        "workflow_version": command.workflow_version,
        "repair_prompt_version": command.repair_prompt_version,
        "repair_policy_version": command.repair_policy.policy_version,
        "repair_no": repair_no,
        "max_repairs": command.repair_policy.max_repairs,
        "reason_code": reason_code,
        "status": status,
    }
