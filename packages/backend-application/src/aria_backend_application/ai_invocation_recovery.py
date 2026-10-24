from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from aria_backend_application.usage_ledger import UsageRecord

AI_INVOCATION_OUTCOME_UNKNOWN = "AI_INVOCATION_OUTCOME_UNKNOWN"

InvocationCheckpointStatus = Literal[
    "started",
    "failed_known",
    "result_ready",
    "finalized",
    "outcome_unknown",
]
RecoveryDisposition = Literal[
    "retry_known",
    "reuse_result",
    "already_finalized",
    "action_required",
]


class AIInvocationRecoveryError(RuntimeError):
    """A durable invocation checkpoint could not be validated or persisted."""


class AIInvocationIdentityError(AIInvocationRecoveryError):
    """The caller attempted to reuse a checkpoint under a different identity."""


@dataclass(frozen=True, slots=True)
class AIInvocationAttempt:
    provider_attempt_id: UUID
    account_id: UUID
    project_id: UUID
    job_id: UUID
    task_type: str
    workflow_version: str
    prompt_version: str
    output_schema_version: str
    provider: str
    model: str
    pricing_version: str
    input_fingerprint: str
    retry_no: int
    repair_no: int
    correlation_id: UUID

    def __post_init__(self) -> None:
        for field_name in (
            "task_type",
            "workflow_version",
            "prompt_version",
            "output_schema_version",
            "provider",
            "model",
            "pricing_version",
        ):
            if not getattr(self, field_name).strip():
                raise AIInvocationIdentityError(f"{field_name}_required")
        if len(self.input_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.input_fingerprint
        ):
            raise AIInvocationIdentityError("input_fingerprint_invalid")
        if self.retry_no < 0 or self.repair_no < 0:
            raise AIInvocationIdentityError("attempt_number_invalid")


@dataclass(frozen=True, slots=True)
class AIInvocationCheckpoint:
    attempt: AIInvocationAttempt
    status: InvocationCheckpointStatus
    normalized_result: Mapping[str, object] | None
    normalized_result_hash: str | None
    failure_class: str | None = None
    retryable: bool | None = None
    retry_not_before: datetime | None = None


@dataclass(frozen=True, slots=True)
class AIInvocationRecoveryDecision:
    disposition: RecoveryDisposition
    normalized_result: Mapping[str, object] | None = None


class AIInvocationCheckpointStore(Protocol):
    async def begin(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint: ...

    async def checkpoint_known_failure(
        self,
        *,
        attempt: AIInvocationAttempt,
        failure_class: str,
        retryable: bool,
        retry_not_before: datetime | None,
        usage_record: UsageRecord,
    ) -> None: ...

    async def checkpoint_success(
        self,
        *,
        attempt: AIInvocationAttempt,
        normalized_result: Mapping[str, object],
        normalized_result_hash: str,
        usage_record: UsageRecord,
    ) -> None: ...

    async def load(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint: ...

    async def mark_outcome_unknown(self, attempt: AIInvocationAttempt) -> None: ...

    async def finalize_cleanup(self, attempt: AIInvocationAttempt) -> None: ...


class DurableAIInvocationRecovery:
    """Provider-neutral orchestration for the frozen 0083 recovery boundary."""

    def __init__(self, store: AIInvocationCheckpointStore) -> None:
        self._store = store

    async def begin(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint:
        return await self._store.begin(attempt)

    async def checkpoint_known_failure(
        self,
        *,
        attempt: AIInvocationAttempt,
        failure_class: str,
        retryable: bool,
        retry_not_before: datetime | None,
        usage_record: UsageRecord,
    ) -> None:
        _require_usage_identity(attempt, usage_record)
        if (
            usage_record.status != "failed"
            or usage_record.accounting_status != "unavailable"
            or usage_record.error_code != failure_class
        ):
            raise AIInvocationIdentityError("known_failure_usage_required")
        await self._store.checkpoint_known_failure(
            attempt=attempt,
            failure_class=failure_class,
            retryable=retryable,
            retry_not_before=retry_not_before,
            usage_record=usage_record,
        )

    async def checkpoint_success(
        self,
        *,
        attempt: AIInvocationAttempt,
        normalized_result: Mapping[str, object],
        usage_record: UsageRecord,
    ) -> str:
        _require_usage_identity(attempt, usage_record)
        if usage_record.status != "success" or usage_record.accounting_status != "complete":
            raise AIInvocationIdentityError("successful_complete_usage_required")
        result_hash = normalized_result_hash(normalized_result)
        await self._store.checkpoint_success(
            attempt=attempt,
            normalized_result=normalized_result,
            normalized_result_hash=result_hash,
            usage_record=usage_record,
        )
        return result_hash

    async def recover(self, attempt: AIInvocationAttempt) -> AIInvocationRecoveryDecision:
        checkpoint = await self._store.load(attempt)
        if checkpoint.status == "failed_known":
            return AIInvocationRecoveryDecision(disposition="retry_known")
        if checkpoint.status == "result_ready":
            if checkpoint.normalized_result is None:
                raise AIInvocationRecoveryError("checkpoint_payload_missing")
            expected_hash = normalized_result_hash(checkpoint.normalized_result)
            if expected_hash != checkpoint.normalized_result_hash:
                raise AIInvocationRecoveryError("checkpoint_hash_mismatch")
            return AIInvocationRecoveryDecision(
                disposition="reuse_result",
                normalized_result=checkpoint.normalized_result,
            )
        if checkpoint.status == "finalized":
            return AIInvocationRecoveryDecision(disposition="already_finalized")
        if checkpoint.status == "outcome_unknown":
            return AIInvocationRecoveryDecision(disposition="action_required")

        await self._store.mark_outcome_unknown(attempt)
        return AIInvocationRecoveryDecision(disposition="action_required")

    async def finalize_cleanup(self, attempt: AIInvocationAttempt) -> None:
        await self._store.finalize_cleanup(attempt)


def normalized_result_hash(normalized_result: Mapping[str, object]) -> str:
    try:
        encoded = json.dumps(
            normalized_result,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise AIInvocationRecoveryError("normalized_result_not_json") from None
    return hashlib.sha256(encoded).hexdigest()


def _require_usage_identity(
    attempt: AIInvocationAttempt,
    usage_record: UsageRecord,
) -> None:
    if (
        usage_record.provider_attempt_id != attempt.provider_attempt_id
        or usage_record.account_id != attempt.account_id
        or usage_record.project_id != attempt.project_id
        or usage_record.job_id != attempt.job_id
        or usage_record.task_type != attempt.task_type
        or usage_record.workflow_version != attempt.workflow_version
        or usage_record.prompt_version != attempt.prompt_version
        or usage_record.provider != attempt.provider
        or usage_record.model != attempt.model
        or usage_record.pricing_version != attempt.pricing_version
        or usage_record.retry_no != attempt.retry_no
        or usage_record.repair_no != attempt.repair_no
        or usage_record.correlation_id != attempt.correlation_id
    ):
        raise AIInvocationIdentityError("usage_identity_mismatch")
