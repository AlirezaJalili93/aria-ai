from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.ports import ExecutionAcquisition
from app.application.txt_parser_consumer import (
    PARSER_JOB_TYPE,
    ParserJobInput,
    ParserJobMessage,
    ParserMessageValidationError,
    ParserRuntimePersistenceError,
)

_LOCK_PREFIX = "aria:txt-parser:"


class PostgresJobExecutionGuard:
    """Hold a session advisory lock while one controlled consumer owns a Job."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._held: dict[UUID, AsyncConnection] = {}

    async def acquire(self, job_id: UUID) -> ExecutionAcquisition:
        if job_id in self._held:
            return "already_in_progress"
        connection = await self._engine.connect()
        try:
            acquired = await connection.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:lock_key, 0))"),
                {"lock_key": _lock_key(job_id)},
            )
            if acquired is not True:
                await connection.close()
                return "already_in_progress"
            status = await connection.scalar(
                text("SELECT status FROM public.jobs WHERE id=:job_id"),
                {"job_id": job_id},
            )
            if status is None:
                await self._unlock(connection, job_id)
                raise ParserMessageValidationError("Parser Job is not available")
            if status in {"succeeded", "failed", "cancelled"}:
                await self._unlock(connection, job_id)
                return "already_completed"
            if status not in {"queued", "running"}:
                await self._unlock(connection, job_id)
                raise ParserMessageValidationError("Parser Job state is invalid")
            self._held[job_id] = connection
            return "acquired"
        except ParserMessageValidationError:
            if not connection.closed:
                with suppress(SQLAlchemyError):
                    await connection.close()
            raise
        except SQLAlchemyError:
            if not connection.closed:
                with suppress(SQLAlchemyError):
                    await connection.close()
            raise ParserRuntimePersistenceError from None

    async def complete(self, job_id: UUID) -> None:
        await self._release(job_id)

    async def release(self, job_id: UUID) -> None:
        await self._release(job_id)

    async def _release(self, job_id: UUID) -> None:
        connection = self._held.pop(job_id, None)
        if connection is not None:
            await self._unlock(connection, job_id)

    @staticmethod
    async def _unlock(connection: AsyncConnection, job_id: UUID) -> None:
        with suppress(SQLAlchemyError):
            await connection.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:lock_key, 0))"),
                {"lock_key": _lock_key(job_id)},
            )
        await connection.close()


class SqlAlchemyTxtParserJobStore:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def prepare(self, message: ParserJobMessage) -> ParserJobInput:
        try:
            async with self._engine.begin() as connection:
                job = (
                    await connection.execute(
                        text(
                            "SELECT id, account_id, project_id, job_type, status, payload_ref, "
                            "attempt_count, correlation_id, available_at "
                            "FROM public.jobs WHERE id=:job_id FOR UPDATE"
                        ),
                        {"job_id": message.job_id},
                    )
                ).mappings().one_or_none()
                if job is None or job["job_type"] != PARSER_JOB_TYPE:
                    raise ParserMessageValidationError("Parser Job type is invalid")
                if job["account_id"] is None or job["project_id"] is None:
                    raise ParserMessageValidationError("Parser Job Tenant state is invalid")
                payload = job["payload_ref"]
                if not isinstance(payload, dict) or set(payload) != {
                    "source_id",
                    "source_version_id",
                }:
                    raise ParserMessageValidationError("Parser Job payload is invalid")
                try:
                    source_id = UUID(str(payload["source_id"]))
                    source_version_id = UUID(str(payload["source_version_id"]))
                except (TypeError, ValueError):
                    raise ParserMessageValidationError(
                        "Parser Job references are invalid"
                    ) from None

                event = (
                    await connection.execute(
                        text(
                            "SELECT account_id, aggregate_id, event_type, payload "
                            "FROM public.outbox_events WHERE id=:event_id"
                        ),
                        {"event_id": message.outbox_event_id},
                    )
                ).mappings().one_or_none()
                if (
                    event is None
                    or event["account_id"] != job["account_id"]
                    or event["aggregate_id"] != source_id
                    or event["event_type"] != "context_added.v1"
                    or not isinstance(event["payload"], dict)
                    or event["payload"].get("jobId") != str(message.job_id)
                ):
                    raise ParserMessageValidationError("Parser Outbox reference is invalid")

                source = (
                    await connection.execute(
                        text(
                            "SELECT id, source_type, status, raw_text, storage_ref, mime_type "
                            "FROM public.context_sources "
                            "WHERE id=:source_id AND account_id=:account_id "
                            "AND project_id=:project_id FOR UPDATE"
                        ),
                        {
                            "source_id": source_id,
                            "account_id": job["account_id"],
                            "project_id": job["project_id"],
                        },
                    )
                ).mappings().one_or_none()
                version = (
                    await connection.execute(
                        text(
                            "SELECT id, source_id, parse_status, storage_ref "
                            "FROM public.context_source_versions "
                            "WHERE id=:version_id AND source_id=:source_id "
                            "AND account_id=:account_id AND project_id=:project_id FOR UPDATE"
                        ),
                        {
                            "version_id": source_version_id,
                            "source_id": source_id,
                            "account_id": job["account_id"],
                            "project_id": job["project_id"],
                        },
                    )
                ).mappings().one_or_none()
                if source is None or version is None:
                    raise ParserMessageValidationError("Parser Source Version is not available")
                if source["source_type"] not in {"text", "file"}:
                    raise ParserMessageValidationError("Parser Source type is unsupported")
                if source["status"] not in {"uploaded", "parsing"}:
                    raise ParserMessageValidationError("Parser Source state is invalid")
                if version["parse_status"] not in {"pending", "parsing"}:
                    raise ParserMessageValidationError("Parser Source Version state is invalid")
                if job["status"] not in {"queued", "running"}:
                    raise ParserMessageValidationError("Parser Job state is invalid")

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
                    _require_one(result.rowcount)
                source_update = await connection.execute(
                    text(
                        "UPDATE public.context_sources SET status='parsing' "
                        "WHERE id=:source_id AND status IN ('uploaded','parsing')"
                    ),
                    {"source_id": source_id},
                )
                version_update = await connection.execute(
                    text(
                        "UPDATE public.context_source_versions SET parse_status='parsing' "
                        "WHERE id=:version_id AND parse_status IN ('pending','parsing')"
                    ),
                    {"version_id": source_version_id},
                )
                _require_one(source_update.rowcount)
                _require_one(version_update.rowcount)
                return ParserJobInput(
                    job_id=message.job_id,
                    account_id=job["account_id"],
                    project_id=job["project_id"],
                    correlation_id=job["correlation_id"],
                    source_id=source_id,
                    source_version_id=source_version_id,
                    source_type=source["source_type"],
                    raw_text=source["raw_text"],
                    storage_ref=version["storage_ref"] or source["storage_ref"],
                    mime_type=source["mime_type"],
                    available_at=job["available_at"],
                    first_attempt=first_attempt,
                )
        except ParserMessageValidationError:
            raise
        except SQLAlchemyError:
            raise ParserRuntimePersistenceError from None

    async def finalize_success(
        self,
        job: ParserJobInput,
        *,
        canonical_value: str,
        canonical_hash: str,
        metadata: dict[str, object],
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                version = await connection.execute(
                    text(
                        "UPDATE public.context_source_versions SET canonical_text=:value, "
                        "content_hash=:hash, metadata=CAST(:metadata AS jsonb), "
                        "parse_status='ready' "
                        "WHERE id=:version_id AND source_id=:source_id AND account_id=:account_id "
                        "AND project_id=:project_id AND parse_status='parsing'"
                    ),
                    {
                        "value": canonical_value,
                        "hash": canonical_hash,
                        "metadata": json.dumps(metadata, separators=(",", ":"), sort_keys=True),
                        **_identity(job),
                    },
                )
                source = await connection.execute(
                    text(
                        "UPDATE public.context_sources SET status='ready' "
                        "WHERE id=:source_id AND account_id=:account_id "
                        "AND project_id=:project_id AND status='parsing'"
                    ),
                    _identity(job),
                )
                completed = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='succeeded', finished_at=:finished_at, "
                        "error_code=NULL, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id AND status='running'"
                    ),
                    {"finished_at": self._clock(), **_identity(job)},
                )
                for result in (version, source, completed):
                    _require_one(result.rowcount)
        except SQLAlchemyError:
            raise ParserRuntimePersistenceError from None

    async def finalize_failure(self, job: ParserJobInput, *, error_code: str) -> None:
        try:
            async with self._engine.begin() as connection:
                version = await connection.execute(
                    text(
                        "UPDATE public.context_source_versions SET parse_status='failed' "
                        "WHERE id=:version_id AND source_id=:source_id AND account_id=:account_id "
                        "AND project_id=:project_id AND parse_status='parsing'"
                    ),
                    _identity(job),
                )
                source = await connection.execute(
                    text(
                        "UPDATE public.context_sources SET status='failed' "
                        "WHERE id=:source_id AND account_id=:account_id "
                        "AND project_id=:project_id AND status='parsing'"
                    ),
                    _identity(job),
                )
                failed = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='failed', finished_at=:finished_at, "
                        "error_code=:error_code, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id AND status='running'"
                    ),
                    {"finished_at": self._clock(), "error_code": error_code, **_identity(job)},
                )
                for result in (version, source, failed):
                    _require_one(result.rowcount)
        except SQLAlchemyError:
            raise ParserRuntimePersistenceError from None


def _lock_key(job_id: UUID) -> str:
    return f"{_LOCK_PREFIX}{job_id}"


def _identity(job: ParserJobInput) -> dict[str, UUID]:
    return {
        "job_id": job.job_id,
        "account_id": job.account_id,
        "project_id": job.project_id,
        "source_id": job.source_id,
        "version_id": job.source_version_id,
    }


def _require_one(rowcount: int) -> None:
    if rowcount != 1:
        raise ParserRuntimePersistenceError
