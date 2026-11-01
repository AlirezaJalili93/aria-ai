from __future__ import annotations

import asyncio
import re
from contextlib import suppress
from uuid import UUID

from aria_backend_application.preview_delivery import PreviewBinding, PreviewError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.application.preview_publication_runtime import (
    PERMANENT_PREVIEW_FAILURES,
    PreviewPublicationJob,
    PreviewPublicationMessage,
    preview_prefix,
)


class PostgresPreviewPublicationStore:
    """Only reviewed fixed helpers, with an owned physical session across preparation."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._held: dict[
            UUID, tuple[AsyncConnection, PreviewPublicationMessage, PreviewPublicationJob]
        ] = {}

    async def prepare(self, message: PreviewPublicationMessage) -> PreviewPublicationJob:
        if message.job_id in self._held:
            raise PreviewError("PREVIEW_PUBLICATION_IN_PROGRESS")
        connection: AsyncConnection | None = None
        try:
            connection = await self._engine.connect()
            transaction = await connection.begin()
            value = await connection.scalar(
                text("SELECT aria_internal.claim_preview(:job_id, :event_id)"),
                {"job_id": message.job_id, "event_id": message.outbox_event_id},
            )
            job = _binding(value, message)
            await transaction.commit()
            if job.already_completed:
                await _discard(connection)
            else:
                self._held[message.job_id] = (connection, message, job)
            return job
        except BaseException as exc:
            # A session advisory lock can survive transaction rollback, including an ambiguous
            # commit. Never return this connection to a pool with unknown lock ownership.
            if connection is not None:
                await asyncio.shield(_discard(connection))
            if isinstance(exc, SQLAlchemyError):
                raise _database_error(exc) from None
            raise

    async def finalize(
        self, job: PreviewPublicationJob, *, manifest_ref: str, manifest_hash: str
    ) -> None:
        held = self._held.get(job.job_id)
        if held is None or held[2] != job:
            raise PreviewError("RESOURCE_NOT_FOUND")
        connection, message, _ = held
        if manifest_ref != preview_prefix(
            job.binding
        ) + "/delivery-manifest.json" or not re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_hash):
            raise PreviewError("PREVIEW_DELIVERY_CONFLICT")
        try:
            transaction = await connection.begin()
            await connection.execute(
                text("SELECT aria_internal.finalize_preview(:job_id, :event_id, :ref, :hash)"),
                {
                    "job_id": job.job_id,
                    "event_id": message.outbox_event_id,
                    "ref": manifest_ref,
                    "hash": manifest_hash,
                },
            )
            await transaction.commit()
        except BaseException as exc:
            self._held.pop(job.job_id, None)
            await asyncio.shield(_discard(connection))
            if isinstance(exc, SQLAlchemyError):
                raise _database_error(exc) from None
            raise

    async def release(self, message: PreviewPublicationMessage) -> None:
        held = self._held.get(message.job_id)
        if held is None:
            return
        connection, owned_message, _ = held
        if owned_message != message:
            raise PreviewError("RESOURCE_NOT_FOUND")
        self._held.pop(message.job_id)
        try:
            transaction = await connection.begin()
            await connection.execute(
                text("SELECT aria_internal.release_preview(:job_id, :event_id)"),
                {"job_id": message.job_id, "event_id": message.outbox_event_id},
            )
            await transaction.commit()
        except SQLAlchemyError:
            # Session termination releases advisory ownership even if the helper/commit failed.
            pass
        finally:
            await asyncio.shield(_discard(connection))

    async def finalize_failure(self, job: PreviewPublicationJob, *, error_code: str) -> None:
        if error_code not in PERMANENT_PREVIEW_FAILURES:
            raise PreviewError("VALIDATION_FAILED")
        held = self._held.get(job.job_id)
        if held is None or held[2] != job:
            raise PreviewError("RESOURCE_NOT_FOUND")
        connection, message, _ = held
        try:
            transaction = await connection.begin()
            await connection.execute(
                text("SELECT aria_internal.fail_preview(:job_id, :event_id, :error_code)"),
                {
                    "job_id": job.job_id,
                    "event_id": message.outbox_event_id,
                    "error_code": error_code,
                },
            )
            await transaction.commit()
        except BaseException as exc:
            self._held.pop(job.job_id, None)
            await asyncio.shield(_discard(connection))
            if isinstance(exc, SQLAlchemyError):
                raise _database_error(exc) from None
            raise


async def _discard(connection: AsyncConnection) -> None:
    try:
        await connection.invalidate()
    except SQLAlchemyError:
        raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None
    finally:
        with suppress(SQLAlchemyError):
            await connection.close()


def _binding(value: object, message: PreviewPublicationMessage) -> PreviewPublicationJob:
    try:
        if not isinstance(value, dict) or set(value) != {
            "job_id",
            "publication_id",
            "account_id",
            "project_id",
            "artifact_id",
            "artifact_version_id",
            "representation_id",
            "version_no",
            "source_hash",
            "source_ref",
            "manifest_ref",
            "manifest_hash",
            "already_completed",
        }:
            raise ValueError
        version = value["version_no"]
        if type(version) is not int or version < 1 or type(value["already_completed"]) is not bool:
            raise ValueError
        source_hash, source_ref = value["source_hash"], value["source_ref"]
        if not isinstance(source_hash, str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", source_hash
        ):
            raise ValueError
        if not isinstance(source_ref, str) or not source_ref:
            raise ValueError
        job_id = UUID(str(value["job_id"]))
        if job_id != message.job_id:
            raise ValueError
        return PreviewPublicationJob(
            job_id=job_id,
            publication_id=UUID(str(value["publication_id"])),
            binding=PreviewBinding(
                account_id=UUID(str(value["account_id"])),
                project_id=UUID(str(value["project_id"])),
                artifact_id=UUID(str(value["artifact_id"])),
                artifact_version_id=UUID(str(value["artifact_version_id"])),
                representation_id=UUID(str(value["representation_id"])),
                version_no=version,
                source_hash=source_hash,
                source_ref=source_ref,
            ),
            already_completed=value["already_completed"],
        )
    except (ValueError, TypeError, KeyError):
        raise PreviewError("RESOURCE_NOT_FOUND") from None


def _database_error(exc: SQLAlchemyError) -> PreviewError:
    sqlstate = getattr(exc.orig, "sqlstate", None) if isinstance(exc, DBAPIError) else None
    if sqlstate == "55P03":
        return PreviewError("PREVIEW_PUBLICATION_IN_PROGRESS")
    if sqlstate == "42501":
        return PreviewError("RESOURCE_NOT_FOUND")
    if sqlstate == "23514":
        return PreviewError("PREVIEW_DELIVERY_CONFLICT")
    return PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True)
