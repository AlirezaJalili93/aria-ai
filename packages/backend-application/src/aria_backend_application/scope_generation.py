from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.ai_execution import AIExecutionPort, StructuredAIResponse
from aria_backend_application.usage_ledger import UsageLedger, UsageRecord

SCOPE_CONTENT_SCHEMA_VERSION = "scope_content_schema_v1"
ScopeRequirementStatus = Literal["draft", "confirmed"]


class ScopeGenerationError(RuntimeError):
    """Safe, provider-neutral Scope Generation failure."""

    retryable = False

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class ScopeGenerationInsufficientContextError(ScopeGenerationError):
    """The exact Context Version is not ready or has no usable input."""


class ScopeGenerationBlockedError(ScopeGenerationError):
    """K02 readiness prevents Scope Generation."""

    def __init__(self) -> None:
        super().__init__("critical_gap_open")


class ScopeDraftAlreadyExistsError(ScopeGenerationError):
    """K03 never overwrites an existing Working Draft."""

    def __init__(self) -> None:
        super().__init__("SCOPE_DRAFT_ALREADY_EXISTS")


class ScopeGenerationValidationError(ScopeGenerationError):
    """The provider candidate failed the canonical K01 content contract."""


class ScopeGenerationExecutionError(ScopeGenerationError):
    """The provider returned a non-success execution status."""


class ScopeGenerationRepositoryError(ScopeGenerationError):
    """The Draft persistence boundary rejected the operation."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeRepairPolicy:
    policy_version: str
    max_repairs: int

    def __post_init__(self) -> None:
        if not self.policy_version:
            raise ValueError("Scope repair policy version is required")
        if isinstance(self.max_repairs, bool) or self.max_repairs not in (0, 1):
            raise ValueError("Sprint 1 Scope repair permits max_repairs 0 or 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGenerationRequirement:
    id: UUID
    context_version: int
    status: ScopeRequirementStatus
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("Requirement context_version must be at least one")
        if self.status not in {"draft", "confirmed"}:
            raise ValueError("Scope input accepts only draft or confirmed Requirements")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGenerationSnapshot:
    account_id: UUID
    project_id: UUID
    context_version: int
    project_type: str
    context_items: tuple[Mapping[str, object], ...]
    requirements: tuple[ScopeGenerationRequirement, ...]
    resolved_gaps: tuple[Mapping[str, object], ...]
    remaining_non_blocking_gaps: tuple[Mapping[str, object], ...]
    ready_for_share: bool

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("Scope context_version must be at least one")
        if not self.project_type:
            raise ValueError("Scope project_type is required")
        if not isinstance(self.ready_for_share, bool):
            raise TypeError("ready_for_share must be boolean")
        if any(
            requirement.context_version != self.context_version
            for requirement in self.requirements
        ):
            raise ValueError("Scope Requirements must use the target Context Version")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGenerationCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    context_version: int
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_prompt_version: str
    output_schema_version: str
    repair_policy: ScopeRepairPolicy
    pricing_version: str
    output_schema: Mapping[str, object]
    routing_policy: Mapping[str, object]
    cost_budget: Mapping[str, object]
    timeout_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("Scope context_version must be at least one")
        if self.output_schema_version != SCOPE_CONTENT_SCHEMA_VERSION:
            raise ValueError(
                "Scope output schema version must be scope_content_schema_v1"
            )
        for field_name in (
            "task_type",
            "workflow_version",
            "prompt_version",
            "repair_prompt_version",
            "pricing_version",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} is required")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeGenerationResult:
    draft_id: UUID
    context_version: int
    repair_no: int


class ScopeGenerationSnapshotReader(Protocol):
    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> ScopeGenerationSnapshot | None: ...


class ScopeContentValidator(Protocol):
    def validate(self, content: object) -> Mapping[str, object]: ...


class ScopeDraftWriter(Protocol):
    async def exists(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> bool: ...

    async def create_ai_draft(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        content: Mapping[str, object],
    ) -> UUID: ...


class ScopeGenerationEventLogger(Protocol):
    def emit(
        self, event_name: str, *, level: str = "INFO", **fields: object
    ) -> None: ...


class ScopeGenerationUseCaseProtocol(Protocol):
    async def execute(
        self, command: ScopeGenerationCommand
    ) -> ScopeGenerationResult: ...


class ScopeGenerationUseCase:
    def __init__(
        self,
        *,
        snapshot_reader: ScopeGenerationSnapshotReader,
        ai_execution: AIExecutionPort,
        usage_ledger: UsageLedger,
        content_validator: ScopeContentValidator,
        draft_writer: ScopeDraftWriter,
        event_logger: ScopeGenerationEventLogger,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._ai_execution = ai_execution
        self._usage_ledger = usage_ledger
        self._content_validator = content_validator
        self._draft_writer = draft_writer
        self._event_logger = event_logger
        self._clock = clock

    async def execute(self, command: ScopeGenerationCommand) -> ScopeGenerationResult:
        started_at = self._clock()
        self._event_logger.emit(
            "scope.generation_started",
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            correlation_id=str(command.correlation_id),
            context_version=command.context_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
        )
        try:
            snapshot = await self._snapshot_reader.resolve_exact(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            if snapshot is None or snapshot.context_version != command.context_version:
                raise ScopeGenerationInsufficientContextError(
                    "scope_context_unavailable"
                )
            if (
                snapshot.account_id != command.account_id
                or snapshot.project_id != command.project_id
            ):
                raise ScopeGenerationInsufficientContextError(
                    "scope_snapshot_tenant_mismatch"
                )
            if not snapshot.ready_for_share:
                raise ScopeGenerationBlockedError
            if await self._draft_writer.exists(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            ):
                raise ScopeDraftAlreadyExistsError

            response, repair_no = await self._execute_with_repair(
                command=command, snapshot=snapshot
            )
            try:
                draft_id = await self._draft_writer.create_ai_draft(
                    account_id=command.account_id,
                    project_id=command.project_id,
                    context_version=command.context_version,
                    content=response,
                )
            except ScopeDraftAlreadyExistsError:
                raise
            except Exception as error:
                raise ScopeGenerationRepositoryError(
                    "scope_draft_persistence_failed"
                ) from error

            result = ScopeGenerationResult(
                draft_id=draft_id,
                context_version=command.context_version,
                repair_no=repair_no,
            )
            self._event_logger.emit(
                "scope.generation_completed",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                correlation_id=str(command.correlation_id),
                context_version=command.context_version,
                repair_no=repair_no,
                duration_ms=(self._clock() - started_at) * 1000,
                status="success",
            )
            return result
        except Exception as error:
            reason_code = (
                error.reason_code
                if isinstance(error, ScopeGenerationError)
                else "scope_generation_failed"
            )
            self._event_logger.emit(
                "scope.generation_failed",
                level="ERROR",
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                correlation_id=str(command.correlation_id),
                context_version=command.context_version,
                duration_ms=(self._clock() - started_at) * 1000,
                reason_code=reason_code,
                status="failed",
            )
            raise

    async def _execute_with_repair(
        self,
        *,
        command: ScopeGenerationCommand,
        snapshot: ScopeGenerationSnapshot,
    ) -> tuple[Mapping[str, object], int]:
        input_context = _build_input_context(snapshot)
        response = await self._execute_and_meter(
            command=command,
            prompt_version=command.prompt_version,
            input_context=input_context,
            repair_no=0,
        )
        for repair_no in range(command.repair_policy.max_repairs + 1):
            if repair_no > 0:
                response = await self._execute_and_meter(
                    command=command,
                    prompt_version=command.repair_prompt_version,
                    input_context={
                        **input_context,
                        "repair": {
                            "repair_no": repair_no,
                            "rejected_output": response.data,
                        },
                    },
                    repair_no=repair_no,
                )
            try:
                return self._validate_response(response), repair_no
            except Exception as error:
                if repair_no >= command.repair_policy.max_repairs:
                    if isinstance(error, ScopeGenerationValidationError):
                        raise
                    raise ScopeGenerationValidationError(
                        "scope_content_validation_failed"
                    ) from error
        raise ScopeGenerationValidationError("scope_content_validation_failed")

    async def _execute_and_meter(
        self,
        *,
        command: ScopeGenerationCommand,
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
                "output_schema_version": command.output_schema_version,
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
            raise ScopeGenerationExecutionError("provider_execution_failed")
        return response

    def _validate_response(
        self, response: StructuredAIResponse
    ) -> Mapping[str, object]:
        try:
            validated = self._content_validator.validate(response.data)
        except Exception as error:
            raise ScopeGenerationValidationError(
                "scope_content_validation_failed"
            ) from error
        if not isinstance(validated, Mapping):
            raise ScopeGenerationValidationError("scope_content_validation_failed")
        return validated


def _build_input_context(snapshot: ScopeGenerationSnapshot) -> Mapping[str, object]:
    return {
        "project_type": snapshot.project_type,
        "context_version": snapshot.context_version,
        "context_items": list(snapshot.context_items),
        "requirements": [
            {
                "id": str(requirement.id),
                "status": requirement.status,
                **dict(requirement.payload),
            }
            for requirement in snapshot.requirements
        ],
        "resolved_gaps": list(snapshot.resolved_gaps),
        "remaining_non_blocking_gaps": list(snapshot.remaining_non_blocking_gaps),
    }
