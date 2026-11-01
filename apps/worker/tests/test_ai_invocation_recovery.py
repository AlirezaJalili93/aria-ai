from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from aria_backend_application.ai_invocation_recovery import (
    AIInvocationAttempt,
    AIInvocationCheckpoint,
    AIInvocationIdentityError,
    DurableAIInvocationRecovery,
    normalized_result_hash,
)

from app.application.usage_ledger import UsageRecord


class MemoryStore:
    def __init__(self) -> None:
        self.checkpoint: AIInvocationCheckpoint | None = None
        self.usage_records: dict[object, UsageRecord] = {}

    async def begin(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint:
        if self.checkpoint is None:
            self.checkpoint = AIInvocationCheckpoint(attempt, "started", None, None)
        return self.checkpoint

    async def checkpoint_known_failure(
        self,
        *,
        attempt: AIInvocationAttempt,
        failure_class: str,
        retryable: bool,
        retry_not_before: datetime | None,
        usage_record: UsageRecord,
    ) -> None:
        self.usage_records.setdefault(usage_record.provider_attempt_id, usage_record)
        self.checkpoint = AIInvocationCheckpoint(
            attempt,
            "failed_known",
            None,
            None,
            failure_class,
            retryable,
            retry_not_before,
        )

    async def checkpoint_success(
        self,
        *,
        attempt: AIInvocationAttempt,
        normalized_result: dict[str, object],
        normalized_result_hash: str,
        usage_record: UsageRecord,
    ) -> None:
        self.usage_records.setdefault(usage_record.provider_attempt_id, usage_record)
        self.checkpoint = AIInvocationCheckpoint(
            attempt, "result_ready", normalized_result, normalized_result_hash
        )

    async def load(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint:
        assert self.checkpoint is not None
        assert self.checkpoint.attempt == attempt
        return self.checkpoint

    async def mark_outcome_unknown(self, attempt: AIInvocationAttempt) -> None:
        self.checkpoint = AIInvocationCheckpoint(attempt, "outcome_unknown", None, None)

    async def finalize_cleanup(self, attempt: AIInvocationAttempt) -> None:
        assert self.checkpoint is not None
        self.checkpoint = AIInvocationCheckpoint(
            attempt,
            "finalized",
            None,
            self.checkpoint.normalized_result_hash,
        )


def _attempt() -> AIInvocationAttempt:
    return AIInvocationAttempt(
        provider_attempt_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        job_id=uuid4(),
        task_type="context_structuring",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        output_schema_version="schema-v1",
        provider="synthetic",
        model="synthetic-model-v1",
        pricing_version="synthetic-zero-v1",
        input_fingerprint="a" * 64,
        retry_no=0,
        repair_no=0,
        correlation_id=uuid4(),
    )


def _usage(attempt: AIInvocationAttempt) -> UsageRecord:
    return UsageRecord(
        account_id=attempt.account_id,
        provider_attempt_id=attempt.provider_attempt_id,
        project_id=attempt.project_id,
        job_id=attempt.job_id,
        task_type=attempt.task_type,
        workflow_version=attempt.workflow_version,
        prompt_version=attempt.prompt_version,
        provider=attempt.provider,
        model=attempt.model,
        provider_request_id="synthetic-request",
        input_tokens=10,
        cached_input_tokens=0,
        output_tokens=5,
        latency_ms=Decimal("12.5"),
        status="success",
        error_code=None,
        retry_no=attempt.retry_no,
        repair_no=attempt.repair_no,
        estimated_cost=Decimal("0"),
        pricing_version=attempt.pricing_version,
        correlation_id=attempt.correlation_id,
    )


def test_ready_checkpoint_reuses_result_without_new_usage() -> None:
    async def exercise() -> None:
        attempt = _attempt()
        store = MemoryStore()
        recovery = DurableAIInvocationRecovery(store)
        result = {"items": [{"kind": "synthetic"}]}

        await recovery.begin(attempt)
        await recovery.checkpoint_success(
            attempt=attempt,
            normalized_result=result,
            usage_record=_usage(attempt),
        )
        decision = await recovery.recover(attempt)

        assert decision.disposition == "reuse_result"
        assert decision.normalized_result == result
        assert len(store.usage_records) == 1

    asyncio.run(exercise())


def test_started_attempt_without_checkpoint_fails_closed() -> None:
    async def exercise() -> None:
        attempt = _attempt()
        store = MemoryStore()
        recovery = DurableAIInvocationRecovery(store)

        await recovery.begin(attempt)
        decision = await recovery.recover(attempt)

        assert decision.disposition == "action_required"
        assert store.checkpoint is not None
        assert store.checkpoint.status == "outcome_unknown"
        assert store.usage_records == {}

    asyncio.run(exercise())


def test_known_failure_persists_usage_and_recovers_as_retryable() -> None:
    async def exercise() -> None:
        attempt = _attempt()
        store = MemoryStore()
        recovery = DurableAIInvocationRecovery(store)
        retry_at = datetime(2026, 9, 30, tzinfo=UTC)
        await recovery.begin(attempt)
        failed_usage = replace(
            _usage(attempt),
            provider_request_id=None,
            input_tokens=None,
            cached_input_tokens=None,
            output_tokens=None,
            status="failed",
            error_code="timeout",
            estimated_cost=None,
            accounting_status="unavailable",
        )

        await recovery.checkpoint_known_failure(
            attempt=attempt,
            failure_class="timeout",
            retryable=True,
            retry_not_before=retry_at,
            usage_record=failed_usage,
        )

        assert (await recovery.recover(attempt)).disposition == "retry_known"
        assert store.checkpoint is not None
        assert store.checkpoint.retry_not_before == retry_at
        assert len(store.usage_records) == 1

    asyncio.run(exercise())


def test_usage_identity_mismatch_is_rejected_before_persistence() -> None:
    async def exercise() -> None:
        attempt = _attempt()
        store = MemoryStore()
        recovery = DurableAIInvocationRecovery(store)
        await recovery.begin(attempt)

        with pytest.raises(AIInvocationIdentityError, match="usage_identity_mismatch"):
            await recovery.checkpoint_success(
                attempt=attempt,
                normalized_result={"items": []},
                usage_record=replace(_usage(attempt), provider_attempt_id=uuid4()),
            )
        assert store.usage_records == {}

    asyncio.run(exercise())


def test_normalized_hash_is_canonical_and_utf8_safe() -> None:
    first = {"items": [{"content": "متن فارسی", "score": 1}], "version": 1}
    second = {"version": 1, "items": [{"score": 1, "content": "متن فارسی"}]}
    assert normalized_result_hash(first) == normalized_result_hash(second)
