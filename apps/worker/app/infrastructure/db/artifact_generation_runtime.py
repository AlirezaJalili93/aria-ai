from __future__ import annotations

from contextlib import suppress
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.artifact_generation_runtime import (
    ArtifactGenerationError,
    ArtifactGenerationJob,
    ArtifactGenerationMessage,
)


class PostgresArtifactGenerationJobStore:
    """Use only the operation-specific 0100 helpers through one owned DB session."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._held: dict[UUID, AsyncConnection] = {}
        self._events: dict[UUID, UUID] = {}

    async def prepare(self, message: ArtifactGenerationMessage) -> ArtifactGenerationJob:
        if message.job_id in self._held:
            raise ArtifactGenerationError(
                "ARTIFACT_GENERATION_IN_PROGRESS", retryable=True
            )
        connection = await self._engine.connect()
        transaction = await connection.begin()
        try:
            value = await connection.scalar(
                text(
                    "SELECT aria_internal.claim_artifact_generation("
                    ":job_id, :outbox_event_id)"
                ),
                {
                    "job_id": message.job_id,
                    "outbox_event_id": message.outbox_event_id,
                },
            )
            await transaction.commit()
            if not isinstance(value, dict):
                raise ArtifactGenerationError("ARTIFACT_RUNTIME_PERSISTENCE_FAILED")
            job = _job_from_binding(value)
            if job.already_completed:
                await connection.close()
            else:
                self._held[message.job_id] = connection
                self._events[message.job_id] = message.outbox_event_id
            return job
        except ArtifactGenerationError:
            if transaction.is_active:
                await transaction.rollback()
            await connection.close()
            raise
        except SQLAlchemyError as exc:
            if transaction.is_active:
                await transaction.rollback()
            await connection.close()
            raise _map_database_error(exc) from None

    async def save_checkpoint(
        self,
        job: ArtifactGenerationJob,
        *,
        checkpoint_ref: str,
        checkpoint_hash: str,
    ) -> None:
        connection = self._owned(job.job_id)
        transaction = await connection.begin()
        try:
            await connection.execute(
                text(
                    "SELECT aria_internal.save_artifact_generation_checkpoint("
                    ":job_id, :outbox_event_id, :checkpoint_ref, :checkpoint_hash)"
                ),
                {
                    "job_id": job.job_id,
                    "outbox_event_id": self._event_id(job.job_id),
                    "checkpoint_ref": checkpoint_ref,
                    "checkpoint_hash": checkpoint_hash,
                },
            )
            await transaction.commit()
        except SQLAlchemyError as exc:
            if transaction.is_active:
                await transaction.rollback()
            raise _map_database_error(exc) from None

    async def finalize(
        self,
        job: ArtifactGenerationJob,
        *,
        storage_ref: str,
        artifact_hash: str,
    ) -> Literal["finalized", "already_completed", "stale"]:
        connection = self._owned(job.job_id)
        transaction = await connection.begin()
        try:
            outcome = await connection.scalar(
                text(
                    "SELECT aria_internal.finalize_artifact_generation("
                    ":job_id, :outbox_event_id, :storage_ref, :artifact_hash)"
                ),
                {
                    "job_id": job.job_id,
                    "outbox_event_id": self._event_id(job.job_id),
                    "storage_ref": storage_ref,
                    "artifact_hash": artifact_hash,
                },
            )
            await transaction.commit()
            if outcome not in {"finalized", "already_completed", "stale"}:
                raise ArtifactGenerationError("ARTIFACT_RUNTIME_PERSISTENCE_FAILED")
            return cast(Literal["finalized", "already_completed", "stale"], outcome)
        except ArtifactGenerationError:
            if transaction.is_active:
                await transaction.rollback()
            raise
        except SQLAlchemyError as exc:
            if transaction.is_active:
                await transaction.rollback()
            raise _map_database_error(exc) from None

    async def release(self, message: ArtifactGenerationMessage) -> None:
        connection = self._held.pop(message.job_id, None)
        self._events.pop(message.job_id, None)
        if connection is None:
            return
        try:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(
                        "SELECT aria_internal.release_artifact_generation("
                        ":job_id, :outbox_event_id)"
                    ),
                    {
                        "job_id": message.job_id,
                        "outbox_event_id": message.outbox_event_id,
                    },
                )
                await transaction.commit()
            except SQLAlchemyError:
                if transaction.is_active:
                    with suppress(SQLAlchemyError):
                        await transaction.rollback()
        finally:
            await connection.close()

    def _owned(self, job_id: UUID) -> AsyncConnection:
        connection = self._held.get(job_id)
        if connection is None:
            raise ArtifactGenerationError("ARTIFACT_GENERATION_OWNERSHIP_REQUIRED")
        return connection

    def _event_id(self, job_id: UUID) -> UUID:
        value = self._events.get(job_id)
        if value is None:
            raise ArtifactGenerationError("ARTIFACT_GENERATION_OWNERSHIP_REQUIRED")
        return value


def _job_from_binding(value: dict[str, object]) -> ArtifactGenerationJob:
    try:
        job = ArtifactGenerationJob(
            job_id=UUID(str(value["job_id"])),
            account_id=UUID(str(value["account_id"])),
            project_id=UUID(str(value["project_id"])),
            correlation_id=UUID(str(value["correlation_id"])),
            artifact_id=UUID(str(value["artifact_id"])),
            artifact_version_id=UUID(str(value["artifact_version_id"])),
            version_no=int(str(value["version_no"])),
            scope_version_id=UUID(str(value["scope_version_id"])),
            scope_version_no=int(str(value["scope_version_no"])),
            scope_version_hash=str(value["scope_version_hash"]),
            project_type=str(value["project_type"]),
            checkpoint_ref=(
                str(value["checkpoint_ref"])
                if value.get("checkpoint_ref") is not None
                else None
            ),
            checkpoint_hash=(
                str(value["checkpoint_hash"])
                if value.get("checkpoint_hash") is not None
                else None
            ),
            already_completed=value.get("already_completed") is True,
        )
    except (KeyError, TypeError, ValueError):
        raise ArtifactGenerationError("ARTIFACT_GENERATION_MESSAGE_INVALID") from None
    return job


def _map_database_error(exc: SQLAlchemyError) -> ArtifactGenerationError:
    sqlstate = None
    if isinstance(exc, DBAPIError):
        sqlstate = getattr(exc.orig, "sqlstate", None)
    if sqlstate == "55P03":
        return ArtifactGenerationError("ARTIFACT_GENERATION_IN_PROGRESS", retryable=True)
    if sqlstate in {"42501", "23514"}:
        return ArtifactGenerationError("ARTIFACT_GENERATION_MESSAGE_INVALID")
    return ArtifactGenerationError("ARTIFACT_RUNTIME_PERSISTENCE_FAILED", retryable=True)
