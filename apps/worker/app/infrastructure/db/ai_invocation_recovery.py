from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from aria_backend_application.ai_invocation_recovery import (
    AI_INVOCATION_OUTCOME_UNKNOWN,
    AIInvocationAttempt,
    AIInvocationCheckpoint,
    AIInvocationIdentityError,
    AIInvocationRecoveryError,
)
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.usage_ledger import UsageRecord
from app.infrastructure.db.usage_ledger import usage_records


class PostgresAIInvocationCheckpointStore:
    """Least-privilege PostgreSQL adapter for the 0083 checkpoint contract."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def begin(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                result = await connection.execute(
                    text(
                        """
                        INSERT INTO public.ai_invocation_checkpoints
                        (provider_attempt_id, account_id, project_id, job_id, task_type,
                         workflow_version, prompt_version, output_schema_version,
                         provider, model, pricing_version, input_fingerprint,
                         retry_no, repair_no, correlation_id, status)
                        SELECT :provider_attempt_id, :account_id, :project_id, :job_id,
                               :task_type, :workflow_version, :prompt_version,
                               :output_schema_version, :provider, :model,
                               :pricing_version, :input_fingerprint,
                               :retry_no, :repair_no, :correlation_id, 'started'
                        FROM public.jobs
                        WHERE id=:job_id AND account_id=:account_id
                          AND project_id=:project_id AND job_type=:task_type
                          AND status='running'
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    _attempt_parameters(attempt),
                )
                if result.rowcount == 1:
                    return await _load_locked(connection, attempt)
                checkpoint = await _load_logical_locked(connection, attempt)
                _require_logical_attempt_identity(attempt, checkpoint.attempt)
                return checkpoint
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("checkpoint_begin_failed") from None

    async def checkpoint_known_failure(
        self,
        *,
        attempt: AIInvocationAttempt,
        failure_class: str,
        retryable: bool,
        retry_not_before: datetime | None,
        usage_record: UsageRecord,
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                checkpoint = await _load_locked(connection, attempt)
                _require_attempt_identity(attempt, checkpoint.attempt)
                if checkpoint.status == "failed_known":
                    if (
                        checkpoint.failure_class != failure_class
                        or checkpoint.retryable is not retryable
                        or checkpoint.retry_not_before != retry_not_before
                    ):
                        raise AIInvocationIdentityError("checkpoint_failure_conflict")
                    return
                if checkpoint.status != "started":
                    raise AIInvocationRecoveryError("checkpoint_not_started")

                inserted = await connection.execute(
                    _usage_insert(usage_record).on_conflict_do_nothing()
                )
                if inserted.rowcount != 1:
                    raise AIInvocationRecoveryError("usage_checkpoint_conflict")

                updated = await connection.execute(
                    text(
                        """
                        UPDATE public.ai_invocation_checkpoints
                        SET status='failed_known', failure_class=:failure_class,
                            retryable=:retryable,
                            retry_not_before=:retry_not_before,
                            failed_known_at=CURRENT_TIMESTAMP
                        WHERE provider_attempt_id=:provider_attempt_id
                          AND account_id=:account_id AND project_id=:project_id
                          AND job_id=:job_id AND status='started'
                        """
                    ),
                    {
                        **_identity_parameters(attempt),
                        "failure_class": failure_class,
                        "retryable": retryable,
                        "retry_not_before": retry_not_before,
                    },
                )
                if updated.rowcount != 1:
                    raise AIInvocationRecoveryError("checkpoint_failure_commit_failed")
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("checkpoint_failure_commit_failed") from None

    async def find_for_job(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        task_type: str,
        retry_no: int,
        repair_no: int,
    ) -> AIInvocationCheckpoint | None:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, account_id)
                rows = (
                    await connection.execute(
                        text(
                            """
                            SELECT provider_attempt_id, account_id, project_id, job_id,
                                   task_type, workflow_version, prompt_version,
                                   output_schema_version, provider, model, pricing_version,
                                   input_fingerprint, retry_no, repair_no, correlation_id,
                                   status, normalized_result, normalized_result_hash,
                                   failure_class, retryable, retry_not_before
                            FROM public.ai_invocation_checkpoints
                            WHERE account_id=:account_id AND project_id=:project_id
                              AND job_id=:job_id AND task_type=:task_type
                              AND retry_no=:retry_no AND repair_no=:repair_no
                            ORDER BY created_at
                            FOR UPDATE
                            """
                        ),
                        {
                            "account_id": account_id,
                            "project_id": project_id,
                            "job_id": job_id,
                            "task_type": task_type,
                            "retry_no": retry_no,
                            "repair_no": repair_no,
                        },
                    )
                ).mappings().all()
                if not rows:
                    return None
                if len(rows) != 1:
                    raise AIInvocationRecoveryError("checkpoint_attempt_ambiguous")
                return _checkpoint_from_row(rows[0])
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("checkpoint_load_failed") from None

    async def checkpoint_success(
        self,
        *,
        attempt: AIInvocationAttempt,
        normalized_result: Mapping[str, object],
        normalized_result_hash: str,
        usage_record: UsageRecord,
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                checkpoint = await _load_locked(connection, attempt)
                _require_attempt_identity(attempt, checkpoint.attempt)
                if checkpoint.status == "result_ready":
                    if checkpoint.normalized_result_hash != normalized_result_hash:
                        raise AIInvocationIdentityError("checkpoint_result_conflict")
                    return
                if checkpoint.status != "started":
                    raise AIInvocationRecoveryError("checkpoint_not_started")

                usage_insert = _usage_insert(usage_record).on_conflict_do_nothing()
                inserted = await connection.execute(usage_insert)
                if inserted.rowcount != 1:
                    raise AIInvocationRecoveryError("usage_checkpoint_conflict")

                updated = await connection.execute(
                    text(
                        """
                        UPDATE public.ai_invocation_checkpoints
                        SET status='result_ready',
                            normalized_result=CAST(:normalized_result AS jsonb),
                            normalized_result_hash=:normalized_result_hash,
                            result_ready_at=CURRENT_TIMESTAMP
                        WHERE provider_attempt_id=:provider_attempt_id
                          AND account_id=:account_id AND project_id=:project_id
                          AND job_id=:job_id AND status='started'
                        """
                    ),
                    {
                        "provider_attempt_id": attempt.provider_attempt_id,
                        "account_id": attempt.account_id,
                        "project_id": attempt.project_id,
                        "job_id": attempt.job_id,
                        "normalized_result": json.dumps(
                            normalized_result,
                            ensure_ascii=False,
                            allow_nan=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "normalized_result_hash": normalized_result_hash,
                    },
                )
                if updated.rowcount != 1:
                    raise AIInvocationRecoveryError("checkpoint_commit_failed")
        except AIInvocationRecoveryError:
            raise
        except (SQLAlchemyError, TypeError, ValueError):
            raise AIInvocationRecoveryError("checkpoint_commit_failed") from None

    async def load(self, attempt: AIInvocationAttempt) -> AIInvocationCheckpoint:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                checkpoint = await _load_locked(connection, attempt)
                _require_attempt_identity(attempt, checkpoint.attempt)
                return checkpoint
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("checkpoint_load_failed") from None

    async def mark_outcome_unknown(self, attempt: AIInvocationAttempt) -> None:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                checkpoint = await _load_locked(connection, attempt)
                _require_attempt_identity(attempt, checkpoint.attempt)
                if checkpoint.status == "outcome_unknown":
                    return
                if checkpoint.status != "started":
                    raise AIInvocationRecoveryError("checkpoint_not_ambiguous")
                checkpoint_update = await connection.execute(
                    text(
                        """
                        UPDATE public.ai_invocation_checkpoints
                        SET status='outcome_unknown', outcome_unknown_at=CURRENT_TIMESTAMP
                        WHERE provider_attempt_id=:provider_attempt_id
                          AND account_id=:account_id AND project_id=:project_id
                          AND job_id=:job_id AND status='started'
                        """
                    ),
                    _identity_parameters(attempt),
                )
                job_update = await connection.execute(
                    text(
                        """
                        UPDATE public.jobs
                        SET status='failed', finished_at=CURRENT_TIMESTAMP,
                            error_code=:error_code, error_detail=NULL
                        WHERE id=:job_id AND account_id=:account_id
                          AND project_id=:project_id AND job_type=:task_type
                          AND status='running'
                        """
                    ),
                    {
                        **_identity_parameters(attempt),
                        "task_type": attempt.task_type,
                        "error_code": AI_INVOCATION_OUTCOME_UNKNOWN,
                    },
                )
                if checkpoint_update.rowcount != 1 or job_update.rowcount != 1:
                    raise AIInvocationRecoveryError("outcome_unknown_commit_failed")
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("outcome_unknown_commit_failed") from None

    async def finalize_cleanup(self, attempt: AIInvocationAttempt) -> None:
        try:
            async with self._engine.begin() as connection:
                await _bind_account(connection, attempt.account_id)
                checkpoint = await _load_locked(connection, attempt)
                _require_attempt_identity(attempt, checkpoint.attempt)
                if checkpoint.status == "finalized":
                    return
                if checkpoint.status != "result_ready":
                    raise AIInvocationRecoveryError("checkpoint_not_ready")
                updated = await connection.execute(
                    text(
                        """
                        UPDATE public.ai_invocation_checkpoints AS checkpoint
                        SET status='finalized', normalized_result=NULL,
                            finalized_at=CURRENT_TIMESTAMP
                        FROM public.jobs AS job
                        WHERE checkpoint.provider_attempt_id=:provider_attempt_id
                          AND checkpoint.account_id=:account_id
                          AND checkpoint.project_id=:project_id
                          AND checkpoint.job_id=:job_id
                          AND checkpoint.status='result_ready'
                          AND job.id=checkpoint.job_id
                          AND job.account_id=checkpoint.account_id
                          AND job.project_id=checkpoint.project_id
                          AND job.status='succeeded'
                        """
                    ),
                    _identity_parameters(attempt),
                )
                if updated.rowcount != 1:
                    raise AIInvocationRecoveryError("domain_finalization_required")
        except AIInvocationRecoveryError:
            raise
        except SQLAlchemyError:
            raise AIInvocationRecoveryError("checkpoint_cleanup_failed") from None


async def _bind_account(connection: AsyncConnection, account_id: UUID) -> None:
    await connection.execute(
        text("SELECT pg_catalog.set_config('aria.checkpoint_account_id', :account_id, true)"),
        {"account_id": str(account_id)},
    )


async def _load_locked(
    connection: AsyncConnection,
    attempt: AIInvocationAttempt,
) -> AIInvocationCheckpoint:
    row = (
        await connection.execute(
            text(
                """
                SELECT provider_attempt_id, account_id, project_id, job_id, task_type,
                       workflow_version, prompt_version, output_schema_version,
                       provider, model, pricing_version, input_fingerprint,
                       retry_no, repair_no, correlation_id, status,
                       normalized_result, normalized_result_hash,
                       failure_class, retryable, retry_not_before
                FROM public.ai_invocation_checkpoints
                WHERE provider_attempt_id=:provider_attempt_id
                  AND account_id=:account_id AND project_id=:project_id
                  AND job_id=:job_id
                FOR UPDATE
                """
            ),
            _identity_parameters(attempt),
        )
    ).mappings().one_or_none()
    if row is None:
        raise AIInvocationRecoveryError("checkpoint_not_found")
    return _checkpoint_from_row(row)


async def _load_logical_locked(
    connection: AsyncConnection,
    attempt: AIInvocationAttempt,
) -> AIInvocationCheckpoint:
    rows = (
        await connection.execute(
            text(
                """
                SELECT provider_attempt_id, account_id, project_id, job_id, task_type,
                       workflow_version, prompt_version, output_schema_version,
                       provider, model, pricing_version, input_fingerprint,
                       retry_no, repair_no, correlation_id, status,
                       normalized_result, normalized_result_hash,
                       failure_class, retryable, retry_not_before
                FROM public.ai_invocation_checkpoints
                WHERE account_id=:account_id AND project_id=:project_id
                  AND job_id=:job_id AND task_type=:task_type
                  AND retry_no=:retry_no AND repair_no=:repair_no
                FOR UPDATE
                """
            ),
            _attempt_parameters(attempt),
        )
    ).mappings().all()
    if not rows:
        raise AIInvocationRecoveryError("checkpoint_not_found")
    if len(rows) != 1:
        raise AIInvocationRecoveryError("checkpoint_attempt_ambiguous")
    return _checkpoint_from_row(rows[0])


def _checkpoint_from_row(
    row: Mapping[str, object] | RowMapping,
) -> AIInvocationCheckpoint:
    return AIInvocationCheckpoint(
        attempt=AIInvocationAttempt(
            provider_attempt_id=row["provider_attempt_id"],  # type: ignore[arg-type]
            account_id=row["account_id"],  # type: ignore[arg-type]
            project_id=row["project_id"],  # type: ignore[arg-type]
            job_id=row["job_id"],  # type: ignore[arg-type]
            task_type=row["task_type"],  # type: ignore[arg-type]
            workflow_version=row["workflow_version"],  # type: ignore[arg-type]
            prompt_version=row["prompt_version"],  # type: ignore[arg-type]
            output_schema_version=row["output_schema_version"],  # type: ignore[arg-type]
            provider=row["provider"],  # type: ignore[arg-type]
            model=row["model"],  # type: ignore[arg-type]
            pricing_version=row["pricing_version"],  # type: ignore[arg-type]
            input_fingerprint=row["input_fingerprint"],  # type: ignore[arg-type]
            retry_no=row["retry_no"],  # type: ignore[arg-type]
            repair_no=row["repair_no"],  # type: ignore[arg-type]
            correlation_id=row["correlation_id"],  # type: ignore[arg-type]
        ),
        status=row["status"],  # type: ignore[arg-type]
        normalized_result=row["normalized_result"],  # type: ignore[arg-type]
        normalized_result_hash=row["normalized_result_hash"],  # type: ignore[arg-type]
        failure_class=row["failure_class"],  # type: ignore[arg-type]
        retryable=row["retryable"],  # type: ignore[arg-type]
        retry_not_before=row["retry_not_before"],  # type: ignore[arg-type]
    )


def _require_attempt_identity(
    expected: AIInvocationAttempt,
    actual: AIInvocationAttempt,
) -> None:
    if expected != actual:
        raise AIInvocationIdentityError("checkpoint_identity_mismatch")


def _require_logical_attempt_identity(
    expected: AIInvocationAttempt,
    actual: AIInvocationAttempt,
) -> None:
    expected_identity = (
        expected.account_id,
        expected.project_id,
        expected.job_id,
        expected.task_type,
        expected.workflow_version,
        expected.prompt_version,
        expected.output_schema_version,
        expected.provider,
        expected.model,
        expected.pricing_version,
        expected.input_fingerprint,
        expected.retry_no,
        expected.repair_no,
        expected.correlation_id,
    )
    actual_identity = (
        actual.account_id,
        actual.project_id,
        actual.job_id,
        actual.task_type,
        actual.workflow_version,
        actual.prompt_version,
        actual.output_schema_version,
        actual.provider,
        actual.model,
        actual.pricing_version,
        actual.input_fingerprint,
        actual.retry_no,
        actual.repair_no,
        actual.correlation_id,
    )
    if expected_identity != actual_identity:
        raise AIInvocationIdentityError("checkpoint_identity_mismatch")


def _identity_parameters(attempt: AIInvocationAttempt) -> dict[str, object]:
    return {
        "provider_attempt_id": attempt.provider_attempt_id,
        "account_id": attempt.account_id,
        "project_id": attempt.project_id,
        "job_id": attempt.job_id,
    }


def _attempt_parameters(attempt: AIInvocationAttempt) -> dict[str, object]:
    return {
        **_identity_parameters(attempt),
        "task_type": attempt.task_type,
        "workflow_version": attempt.workflow_version,
        "prompt_version": attempt.prompt_version,
        "output_schema_version": attempt.output_schema_version,
        "provider": attempt.provider,
        "model": attempt.model,
        "pricing_version": attempt.pricing_version,
        "input_fingerprint": attempt.input_fingerprint,
        "retry_no": attempt.retry_no,
        "repair_no": attempt.repair_no,
        "correlation_id": attempt.correlation_id,
    }


def _usage_insert(usage_record: UsageRecord):
    return insert(usage_records).values(
        provider_attempt_id=usage_record.provider_attempt_id,
        account_id=usage_record.account_id,
        project_id=usage_record.project_id,
        job_id=usage_record.job_id,
        task_type=usage_record.task_type,
        workflow_version=usage_record.workflow_version,
        prompt_version=usage_record.prompt_version,
        provider=usage_record.provider,
        model=usage_record.model,
        provider_request_id=usage_record.provider_request_id,
        input_tokens=usage_record.input_tokens,
        cached_input_tokens=usage_record.cached_input_tokens,
        output_tokens=usage_record.output_tokens,
        latency_ms=usage_record.latency_ms,
        status=usage_record.status,
        error_code=usage_record.error_code,
        retry_no=usage_record.retry_no,
        repair_no=usage_record.repair_no,
        estimated_cost=usage_record.estimated_cost,
        accounting_status=usage_record.accounting_status,
        currency=usage_record.currency,
        pricing_version=usage_record.pricing_version,
        correlation_id=usage_record.correlation_id,
    )


def complete_usage_record(
    *,
    attempt: AIInvocationAttempt,
    provider_request_id: str | None,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    latency_ms: Decimal,
    estimated_cost: Decimal,
    currency: str = "USD",
) -> UsageRecord:
    """Synthetic-friendly constructor; production callers still own validated pricing."""

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
        provider_request_id=provider_request_id,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        status="success",
        error_code=None,
        retry_no=attempt.retry_no,
        repair_no=attempt.repair_no,
        estimated_cost=estimated_cost,
        pricing_version=attempt.pricing_version,
        correlation_id=attempt.correlation_id,
        accounting_status="complete",
        currency=currency,
    )


def unavailable_usage_record(
    *,
    attempt: AIInvocationAttempt,
    failure_class: str,
    latency_ms: Decimal,
    currency: str = "USD",
) -> UsageRecord:
    """Record a known failed invocation without fabricating token or cost data."""

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
        provider_request_id=None,
        input_tokens=None,
        cached_input_tokens=None,
        output_tokens=None,
        latency_ms=latency_ms,
        status="failed",
        error_code=failure_class,
        retry_no=attempt.retry_no,
        repair_no=attempt.repair_no,
        estimated_cost=None,
        pricing_version=attempt.pricing_version,
        correlation_id=attempt.correlation_id,
        accounting_status="unavailable",
        currency=currency,
    )
