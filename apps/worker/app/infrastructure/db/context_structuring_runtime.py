from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from aria_backend_application.context_structuring import (
    ContextStructuringRepository,
    ContextStructuringRepositoryError,
    ContextStructuringUnitOfWork,
    ContextVersionWrite,
    SourceSnapshot,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from app.application.context_structuring_consumer import (
    CONTEXT_STRUCTURING_EVENT_TYPE,
    CONTEXT_STRUCTURING_JOB_TYPE,
    CONTEXT_STRUCTURING_MESSAGE_VERSION,
    ContextStructuringJobInput,
    ContextStructuringJobMessage,
    ContextStructuringMessageValidationError,
    ContextStructuringRuntimePersistenceError,
)


class PostgresContextStructuringSnapshotReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve_latest_ready(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> tuple[SourceSnapshot, ...]:
        try:
            async with self._engine.connect() as connection:
                rows = (
                    await connection.execute(
                        text(
                            """
                            WITH ranked AS (
                                SELECT v.source_id,
                                       v.id AS source_version_id,
                                       v.version_no,
                                       v.canonical_text,
                                       v.storage_ref,
                                       row_number() OVER (
                                           PARTITION BY v.source_id
                                           ORDER BY v.version_no DESC
                                       ) AS ready_rank
                                FROM public.context_source_versions AS v
                                JOIN public.context_sources AS s
                                  ON s.id=v.source_id
                                 AND s.account_id=v.account_id
                                 AND s.project_id=v.project_id
                                WHERE v.account_id=:account_id
                                  AND v.project_id=:project_id
                                  AND v.parse_status='ready'
                                  AND s.status<>'deleted'
                            )
                            SELECT source_id, source_version_id, version_no,
                                   canonical_text, storage_ref
                            FROM ranked
                            WHERE ready_rank=1
                            ORDER BY source_id
                            """
                        ),
                        {"account_id": account_id, "project_id": project_id},
                    )
                ).mappings().all()
        except SQLAlchemyError:
            raise ContextStructuringRepositoryError("source_snapshot_failed") from None
        return tuple(
            SourceSnapshot(
                source_id=row["source_id"],
                source_version_id=row["source_version_id"],
                version_no=row["version_no"],
                canonical_text=row["canonical_text"],
                storage_ref=row["storage_ref"],
            )
            for row in rows
        )


class SqlContextStructuringRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def allocate_next_version(self, *, account_id: UUID, project_id: UUID) -> int:
        current_version = await self._connection.scalar(
            text(
                "SELECT current_context_version FROM public.projects "
                "WHERE id=:project_id AND account_id=:account_id AND deleted_at IS NULL "
                "FOR UPDATE"
            ),
            {"account_id": account_id, "project_id": project_id},
        )
        if current_version is None:
            raise ContextStructuringRepositoryError("project_not_available")
        return int(current_version) + 1

    async def add_batch(self, items: tuple[ContextVersionWrite, ...]) -> None:
        for item in items:
            source_refs = [
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
            ]
            await self._connection.execute(
                text(
                    """
                    INSERT INTO public.context_items
                    (id, account_id, project_id, context_version, item_type, content,
                     source_refs, confidence, status, created_by_type, created_by)
                    VALUES
                    (:id, :account_id, :project_id, :context_version, :item_type, :content,
                     CAST(:source_refs AS jsonb), :confidence, :status, :created_by_type, NULL)
                    """
                ),
                {
                    "id": item.id,
                    "account_id": item.account_id,
                    "project_id": item.project_id,
                    "context_version": item.context_version,
                    "item_type": item.item_type,
                    "content": item.content,
                    "source_refs": json.dumps(source_refs, separators=(",", ":")),
                    "confidence": item.confidence,
                    "status": item.status,
                    "created_by_type": item.created_by_type,
                },
            )

    async def advance_project_version(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
    ) -> None:
        result = await self._connection.execute(
            text(
                "UPDATE public.projects SET current_context_version=:context_version "
                "WHERE id=:project_id AND account_id=:account_id "
                "AND current_context_version=:previous_version AND deleted_at IS NULL"
            ),
            {
                "account_id": account_id,
                "project_id": project_id,
                "context_version": context_version,
                "previous_version": context_version - 1,
            },
        )
        _require_one(result.rowcount, "context_version_conflict")

    async def complete_job_success(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
    ) -> None:
        result = await self._connection.execute(
            text(
                "UPDATE public.jobs SET status='succeeded', finished_at=CURRENT_TIMESTAMP, "
                "error_code=NULL, error_detail=NULL WHERE id=:job_id "
                "AND account_id=:account_id AND project_id=:project_id "
                "AND job_type='context_structuring' AND status='running'"
            ),
            {"account_id": account_id, "project_id": project_id, "job_id": job_id},
        )
        _require_one(result.rowcount, "job_not_running")


class PostgresContextStructuringUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._repository: SqlContextStructuringRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ContextStructuringRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> PostgresContextStructuringUnitOfWork:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self._repository = SqlContextStructuringRepository(self._connection)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        if self._connection is None or self._transaction is None:
            return
        try:
            if not self._committed and self._transaction.is_active:
                await self._transaction.rollback()
        finally:
            await self._connection.close()
        if isinstance(exc, SQLAlchemyError):
            raise ContextStructuringRepositoryError("context_persistence_failed") from None

    async def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._transaction.commit()
        except SQLAlchemyError:
            raise ContextStructuringRepositoryError("context_persistence_failed") from None
        self._committed = True


class PostgresContextStructuringUnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def __call__(self) -> ContextStructuringUnitOfWork:
        return PostgresContextStructuringUnitOfWork(self._engine)


class SqlAlchemyContextStructuringJobStore:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def prepare(
        self, message: ContextStructuringJobMessage
    ) -> ContextStructuringJobInput:
        try:
            async with self._engine.begin() as connection:
                job = (
                    await connection.execute(
                        text(
                            "SELECT id, account_id, project_id, job_type, status, payload_ref, "
                            "attempt_count, correlation_id FROM public.jobs "
                            "WHERE id=:job_id FOR UPDATE"
                        ),
                        {"job_id": message.job_id},
                    )
                ).mappings().one_or_none()
                if (
                    job is None
                    or job["job_type"] != CONTEXT_STRUCTURING_JOB_TYPE
                    or job["account_id"] is None
                    or job["project_id"] is None
                    or job["payload_ref"] is not None
                    or job["status"] not in {"queued", "running"}
                ):
                    raise ContextStructuringMessageValidationError(
                        "Context Structuring Job is invalid"
                    )

                event = (
                    await connection.execute(
                        text(
                            "SELECT account_id, aggregate_type, aggregate_id, event_type, "
                            "delivery_channel, payload FROM public.outbox_events "
                            "WHERE id=:event_id"
                        ),
                        {"event_id": message.outbox_event_id},
                    )
                ).mappings().one_or_none()
                expected_payload = {
                    "jobId": str(message.job_id),
                    "taskType": CONTEXT_STRUCTURING_JOB_TYPE,
                    "payloadVersion": CONTEXT_STRUCTURING_MESSAGE_VERSION,
                }
                if (
                    event is None
                    or event["account_id"] != job["account_id"]
                    or event["aggregate_type"] != "project"
                    or event["aggregate_id"] != job["project_id"]
                    or event["event_type"] != CONTEXT_STRUCTURING_EVENT_TYPE
                    or event["delivery_channel"] != "job_queue"
                    or event["payload"] != expected_payload
                ):
                    raise ContextStructuringMessageValidationError(
                        "Context Structuring Outbox reference is invalid"
                    )

                first_attempt = job["status"] == "queued"
                if first_attempt:
                    result = await connection.execute(
                        text(
                            "UPDATE public.jobs SET status='running', attempt_count=1, "
                            "started_at=:started_at, finished_at=NULL, error_code=NULL, "
                            "error_detail=NULL WHERE id=:job_id AND status='queued'"
                        ),
                        {"started_at": self._clock(), "job_id": message.job_id},
                    )
                    if result.rowcount != 1:
                        raise ContextStructuringRuntimePersistenceError
                return ContextStructuringJobInput(
                    job_id=message.job_id,
                    account_id=job["account_id"],
                    project_id=job["project_id"],
                    correlation_id=job["correlation_id"],
                    first_attempt=first_attempt,
                )
        except ContextStructuringMessageValidationError:
            raise
        except ContextStructuringRuntimePersistenceError:
            raise
        except SQLAlchemyError:
            raise ContextStructuringRuntimePersistenceError from None

    async def finalize_failure(
        self,
        job: ContextStructuringJobInput,
        *,
        error_code: str,
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='failed', finished_at=:finished_at, "
                        "error_code=:error_code, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id "
                        "AND job_type='context_structuring' AND status='running'"
                    ),
                    {
                        "finished_at": self._clock(),
                        "error_code": error_code,
                        "job_id": job.job_id,
                        "account_id": job.account_id,
                        "project_id": job.project_id,
                    },
                )
                if result.rowcount != 1:
                    raise ContextStructuringRuntimePersistenceError
        except ContextStructuringRuntimePersistenceError:
            raise
        except SQLAlchemyError:
            raise ContextStructuringRuntimePersistenceError from None


def _require_one(rowcount: int, reason_code: str) -> None:
    if rowcount != 1:
        raise ContextStructuringRepositoryError(reason_code)
