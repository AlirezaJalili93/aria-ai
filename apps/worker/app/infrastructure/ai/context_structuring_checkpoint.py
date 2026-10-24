from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.ai_invocation_recovery import (
    AI_INVOCATION_OUTCOME_UNKNOWN,
    AIInvocationAttempt,
    AIInvocationCheckpoint,
    AIInvocationIdentityError,
    AIInvocationRecoveryError,
    DurableAIInvocationRecovery,
)
from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    ContextStructuringCheckpointResolution,
    ContextStructuringCommand,
    ContextStructuringError,
    SourceSnapshot,
)
from aria_backend_application.context_structuring_checkpoint import (
    AI_INVOCATION_CHECKPOINT_INVALID,
    ContextStructuringCheckpointCodecError,
    context_structuring_input_fingerprint,
    decode_context_structuring_checkpoint,
    encode_context_structuring_checkpoint,
    require_matching_context_snapshot,
)

from app.infrastructure.db.ai_invocation_recovery import (
    PostgresAIInvocationCheckpointStore,
    complete_usage_record,
    unavailable_usage_record,
)


class RetrySleeper(Protocol):
    async def sleep(self, delay_seconds: float) -> None: ...


class _AsyncioRetrySleeper:
    async def sleep(self, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)


class SyntheticAI01CheckpointRuntime:
    """Compose the frozen 0084 checkpoint and opt-in 0085 timeout retry."""

    def __init__(
        self,
        store: PostgresAIInvocationCheckpointStore,
        *,
        provider: str = "synthetic",
        model: str = "context-structuring-fake-v1",
        id_factory: Callable[[], UUID] = uuid4,
        timeout_retry_enabled: bool = False,
        utc_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        random_source: Callable[[], float] = random.random,
        sleeper: RetrySleeper | None = None,
    ) -> None:
        self._store = store
        self._recovery = DurableAIInvocationRecovery(store)
        self._provider = provider
        self._model = model
        self._id_factory = id_factory
        self._timeout_retry_enabled = timeout_retry_enabled
        self._utc_clock = utc_clock
        self._random_source = random_source
        self._sleeper = sleeper or _AsyncioRetrySleeper()

    async def recover(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
    ) -> ContextStructuringCheckpointResolution | None:
        try:
            checkpoint = await self._store.find_for_job(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                task_type=command.task_type,
                retry_no=0,
                repair_no=0,
            )
            if checkpoint is None:
                return None
            _require_attempt(
                command,
                snapshot,
                checkpoint.attempt,
                self._provider,
                self._model,
                retry_no=0,
            )
            decision = await self._recovery.recover(checkpoint.attempt)
            if decision.disposition == "action_required":
                raise ContextStructuringError(AI_INVOCATION_OUTCOME_UNKNOWN)
            if decision.disposition == "retry_known":
                if not self._timeout_retry_enabled:
                    raise ContextStructuringCheckpointCodecError(
                        "checkpoint_retry_not_enabled"
                    )
                _require_retryable_timeout(checkpoint, requires_schedule=True)
                retry_checkpoint = await self._store.find_for_job(
                    account_id=command.account_id,
                    project_id=command.project_id,
                    job_id=command.job_id,
                    task_type=command.task_type,
                    retry_no=1,
                    repair_no=0,
                )
                if retry_checkpoint is None:
                    retry_attempt = await self._begin_retry(
                        command=command,
                        snapshot=snapshot,
                        retry_not_before=checkpoint.retry_not_before,
                    )
                    return ContextStructuringCheckpointResolution(
                        provider_attempt_id=retry_attempt.provider_attempt_id,
                        batch=None,
                        retry_no=1,
                    )
                _require_attempt(
                    command,
                    snapshot,
                    retry_checkpoint.attempt,
                    self._provider,
                    self._model,
                    retry_no=1,
                )
                retry_decision = await self._recovery.recover(
                    retry_checkpoint.attempt
                )
                if retry_decision.disposition == "action_required":
                    raise ContextStructuringError(AI_INVOCATION_OUTCOME_UNKNOWN)
                if retry_decision.disposition == "retry_known":
                    _require_retryable_timeout(
                        retry_checkpoint,
                        requires_schedule=False,
                    )
                    raise ContextStructuringError("timeout")
                decision = retry_decision
                checkpoint = retry_checkpoint
            if decision.disposition != "reuse_result" or decision.normalized_result is None:
                raise ContextStructuringCheckpointCodecError("checkpoint_result_unavailable")
            decoded = decode_context_structuring_checkpoint(decision.normalized_result)
            require_matching_context_snapshot(decoded, snapshot)
            return ContextStructuringCheckpointResolution(
                provider_attempt_id=checkpoint.attempt.provider_attempt_id,
                batch=decoded.batch,
                retry_no=checkpoint.attempt.retry_no,
            )
        except ContextStructuringError:
            raise
        except (AIInvocationRecoveryError, ContextStructuringCheckpointCodecError):
            raise ContextStructuringError(AI_INVOCATION_CHECKPOINT_INVALID) from None

    async def begin(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
    ) -> UUID:
        if command.repair_policy.max_repairs != 0:
            raise ContextStructuringError(AI_INVOCATION_CHECKPOINT_INVALID)
        attempt = self._attempt(command=command, snapshot=snapshot, retry_no=0)
        try:
            checkpoint = await self._recovery.begin(attempt)
        except AIInvocationRecoveryError:
            raise ContextStructuringError(AI_INVOCATION_CHECKPOINT_INVALID) from None
        return checkpoint.attempt.provider_attempt_id

    async def checkpoint_success(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
        provider_attempt_id: UUID,
        response: StructuredAIResponse,
        batch: CandidateContextBatch,
    ) -> None:
        attempt = await self._resolve_attempt(
            command=command,
            snapshot=snapshot,
            provider_attempt_id=provider_attempt_id,
        )
        try:
            _require_response(attempt, response)
            await self._recovery.checkpoint_success(
                attempt=attempt,
                normalized_result=encode_context_structuring_checkpoint(
                    snapshot=snapshot,
                    batch=batch,
                ),
                usage_record=complete_usage_record(
                    attempt=attempt,
                    provider_request_id=response.provider_request_id,
                    input_tokens=response.input_tokens,
                    cached_input_tokens=response.cached_input_tokens,
                    output_tokens=response.output_tokens,
                    latency_ms=Decimal(str(response.latency_ms)),
                    estimated_cost=Decimal(str(response.estimated_cost)),
                ),
            )
        except (AIInvocationRecoveryError, AIInvocationIdentityError):
            raise ContextStructuringError(AI_INVOCATION_CHECKPOINT_INVALID) from None

    async def checkpoint_failure(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
        provider_attempt_id: UUID,
        error_class: str,
        retryable: bool,
        latency_ms: Decimal,
    ) -> UUID | None:
        if error_class != "timeout" or not retryable:
            raise ContextStructuringError(error_class)
        try:
            attempt = await self._resolve_attempt(
                command=command,
                snapshot=snapshot,
                provider_attempt_id=provider_attempt_id,
            )
            retry_not_before: datetime | None = None
            if attempt.retry_no == 0:
                if not self._timeout_retry_enabled:
                    raise ContextStructuringError("timeout")
                retry_not_before = self._utc_clock() + timedelta(
                    seconds=_full_jitter_delay(self._random_source())
                )
            await self._recovery.checkpoint_known_failure(
                attempt=attempt,
                failure_class="timeout",
                retryable=True,
                retry_not_before=retry_not_before,
                usage_record=unavailable_usage_record(
                    attempt=attempt,
                    failure_class="timeout",
                    latency_ms=latency_ms,
                ),
            )
            if attempt.retry_no == 1:
                return None
            retry_attempt = await self._begin_retry(
                command=command,
                snapshot=snapshot,
                retry_not_before=retry_not_before,
            )
            return retry_attempt.provider_attempt_id
        except ContextStructuringError:
            raise
        except (AIInvocationRecoveryError, AIInvocationIdentityError):
            raise ContextStructuringError(AI_INVOCATION_CHECKPOINT_INVALID) from None

    async def _resolve_attempt(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
        provider_attempt_id: UUID,
    ) -> AIInvocationAttempt:
        for retry_no in (0, 1):
            checkpoint = await self._store.find_for_job(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                task_type=command.task_type,
                retry_no=retry_no,
                repair_no=0,
            )
            if checkpoint is None or checkpoint.attempt.provider_attempt_id != provider_attempt_id:
                continue
            _require_attempt(
                command,
                snapshot,
                checkpoint.attempt,
                self._provider,
                self._model,
                retry_no=retry_no,
            )
            return checkpoint.attempt
        raise AIInvocationIdentityError("provider_attempt_identity_mismatch")

    async def _begin_retry(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
        retry_not_before: datetime | None,
    ) -> AIInvocationAttempt:
        if retry_not_before is None:
            raise ContextStructuringCheckpointCodecError("retry_schedule_missing")
        delay_seconds = (retry_not_before - self._utc_clock()).total_seconds()
        if delay_seconds > 0:
            await self._sleeper.sleep(delay_seconds)
        checkpoint = await self._recovery.begin(
            self._attempt(command=command, snapshot=snapshot, retry_no=1)
        )
        _require_attempt(
            command,
            snapshot,
            checkpoint.attempt,
            self._provider,
            self._model,
            retry_no=1,
        )
        return checkpoint.attempt

    def _attempt(
        self,
        *,
        command: ContextStructuringCommand,
        snapshot: tuple[SourceSnapshot, ...],
        retry_no: int,
    ) -> AIInvocationAttempt:
        return AIInvocationAttempt(
            provider_attempt_id=self._id_factory(),
            account_id=command.account_id,
            project_id=command.project_id,
            job_id=command.job_id,
            task_type=command.task_type,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            output_schema_version=command.output_schema_version,
            provider=self._provider,
            model=self._model,
            pricing_version=command.pricing_version,
            input_fingerprint=context_structuring_input_fingerprint(command, snapshot),
            retry_no=retry_no,
            repair_no=0,
            correlation_id=command.correlation_id,
        )


def _require_attempt(
    command: ContextStructuringCommand,
    snapshot: tuple[SourceSnapshot, ...],
    attempt: AIInvocationAttempt,
    provider: str,
    model: str,
    *,
    retry_no: int,
) -> None:
    expected = (
        command.account_id,
        command.project_id,
        command.job_id,
        command.task_type,
        command.workflow_version,
        command.prompt_version,
        command.output_schema_version,
        provider,
        model,
        command.pricing_version,
        context_structuring_input_fingerprint(command, snapshot),
        retry_no,
        0,
        command.correlation_id,
    )
    actual = (
        attempt.account_id,
        attempt.project_id,
        attempt.job_id,
        attempt.task_type,
        attempt.workflow_version,
        attempt.prompt_version,
        attempt.output_schema_version,
        attempt.provider,
        attempt.model,
        attempt.pricing_version,
        attempt.input_fingerprint,
        attempt.retry_no,
        attempt.repair_no,
        attempt.correlation_id,
    )
    if actual != expected:
        raise ContextStructuringCheckpointCodecError("checkpoint_identity_mismatch")


def _require_response(
    attempt: AIInvocationAttempt,
    response: StructuredAIResponse,
) -> None:
    if (
        response.provider_attempt_id != attempt.provider_attempt_id
        or response.provider != attempt.provider
        or response.model != attempt.model
        or response.workflow_version != attempt.workflow_version
        or response.prompt_version != attempt.prompt_version
        or response.retry_no != attempt.retry_no
        or response.status != "success"
    ):
        raise AIInvocationIdentityError("provider_attempt_identity_mismatch")


def _require_retryable_timeout(
    checkpoint: AIInvocationCheckpoint,
    *,
    requires_schedule: bool,
) -> None:
    if (
        checkpoint.failure_class != "timeout"
        or checkpoint.retryable is not True
        or (requires_schedule and checkpoint.retry_not_before is None)
        or (not requires_schedule and checkpoint.retry_not_before is not None)
    ):
        raise ContextStructuringCheckpointCodecError(
            "checkpoint_known_failure_invalid"
        )


def _full_jitter_delay(fraction: float) -> float:
    if fraction < 0 or fraction > 1:
        raise ContextStructuringCheckpointCodecError(
            "retry_random_fraction_out_of_range"
        )
    return 2.0 * fraction
