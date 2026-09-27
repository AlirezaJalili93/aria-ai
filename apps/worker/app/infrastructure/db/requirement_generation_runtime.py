from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Literal, cast
from uuid import UUID

from aria_backend_application.requirements_generation import (
    ContextItemRevision,
    ExistingRequirement,
    RequirementConflictEvent,
    RequirementContextItem,
    RequirementContextSnapshot,
    RequirementGenerationReplay,
    RequirementGenerationRepository,
    RequirementGenerationRepositoryError,
    RequirementGenerationUnitOfWork,
    RequirementSourceReference,
    RequirementWrite,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from app.application.requirement_generation_consumer import (
    REQUIREMENT_GENERATION_EVENT_TYPE,
    REQUIREMENT_GENERATION_JOB_TYPE,
    REQUIREMENT_GENERATION_MESSAGE_VERSION,
    RequirementGenerationJobInput,
    RequirementGenerationJobMessage,
    RequirementGenerationMessageValidationError,
    RequirementGenerationRuntimePersistenceError,
)


class PostgresRequirementContextSnapshotReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> RequirementContextSnapshot | None:
        try:
            async with self._engine.connect() as connection:
                project_type = await connection.scalar(
                    text(
                        "SELECT project_type FROM public.projects WHERE id=:project_id "
                        "AND account_id=:account_id AND current_context_version>=:context_version "
                        "AND deleted_at IS NULL"
                    ),
                    {
                        "account_id": account_id,
                        "project_id": project_id,
                        "context_version": context_version,
                    },
                )
                if project_type is None:
                    return None
                rows = (
                    await connection.execute(
                        text(
                            "SELECT id, updated_at, item_type, status, content, source_refs "
                            "FROM public.context_items WHERE account_id=:account_id "
                            "AND project_id=:project_id AND context_version=:context_version "
                            "AND status IN ('proposed','confirmed') ORDER BY id"
                        ),
                        {
                            "account_id": account_id,
                            "project_id": project_id,
                            "context_version": context_version,
                        },
                    )
                ).mappings().all()
        except SQLAlchemyError:
            raise RequirementGenerationRepositoryError("context_snapshot_failed") from None
        return RequirementContextSnapshot(
            project_type=str(project_type),
            context_version=context_version,
            items=tuple(_context_item(row) for row in rows),
        )


class SqlRequirementGenerationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def resolve_generation_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> RequirementGenerationReplay | None:
        job = (
            await self._connection.execute(
                text(
                    "SELECT status, error_code FROM public.jobs WHERE id=:job_id "
                    "AND account_id=:account_id AND project_id=:project_id "
                    "AND job_type='requirement_generation'"
                ),
                {
                    "job_id": generation_job_id,
                    "account_id": account_id,
                    "project_id": project_id,
                },
            )
        ).mappings().one_or_none()
        if job is None or job["status"] not in {"succeeded", "failed"}:
            return None
        if job["status"] == "failed":
            return RequirementGenerationReplay("failed", (), job["error_code"])
        rows = (
            await self._connection.execute(
                text(
                    "SELECT id, category, title, description, priority, status, source_refs, "
                    "confidence, is_unsupported, duplicate_group_key, generation_job_id "
                    "FROM public.requirements WHERE account_id=:account_id "
                    "AND project_id=:project_id AND generation_job_id=:job_id "
                    "ORDER BY created_at, id"
                ),
                {
                    "account_id": account_id,
                    "project_id": project_id,
                    "job_id": generation_job_id,
                },
            )
        ).mappings().all()
        return RequirementGenerationReplay(
            "succeeded", tuple(_existing_requirement(row) for row in rows), None
        )

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ContextItemRevision, ...] | None:
        project = await self._connection.scalar(
            text(
                "SELECT id FROM public.projects WHERE id=:project_id AND account_id=:account_id "
                "AND current_context_version>=:context_version AND deleted_at IS NULL FOR UPDATE"
            ),
            {
                "account_id": account_id,
                "project_id": project_id,
                "context_version": context_version,
            },
        )
        if project is None:
            return None
        await self._connection.execute(text("LOCK TABLE public.context_items IN SHARE MODE"))
        rows = (
            await self._connection.execute(
                text(
                    "SELECT id, updated_at FROM public.context_items "
                    "WHERE account_id=:account_id AND project_id=:project_id "
                    "AND context_version=:context_version "
                    "AND status IN ('proposed','confirmed') ORDER BY id"
                ),
                {
                    "account_id": account_id,
                    "project_id": project_id,
                    "context_version": context_version,
                },
            )
        ).mappings().all()
        return tuple(ContextItemRevision(row["id"], row["updated_at"]) for row in rows)

    async def list_existing_for_merge(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ExistingRequirement, ...]:
        rows = (
            await self._connection.execute(
                text(
                    "SELECT id, category, title, description, priority, status, source_refs, "
                    "confidence, is_unsupported, duplicate_group_key, generation_job_id "
                    "FROM public.requirements WHERE account_id=:account_id "
                    "AND project_id=:project_id AND context_version=:context_version "
                    "ORDER BY CASE WHEN status='removed' THEN 1 ELSE 0 END, created_at, id "
                    "FOR UPDATE"
                ),
                {
                    "account_id": account_id,
                    "project_id": project_id,
                    "context_version": context_version,
                },
            )
        ).mappings().all()
        return tuple(_existing_requirement(row) for row in rows)

    async def replace_source_refs(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        source_refs: tuple[RequirementSourceReference, ...],
    ) -> None:
        result = await self._connection.execute(
            text(
                "UPDATE public.requirements SET source_refs=CAST(:source_refs AS jsonb) "
                "WHERE id=:id AND account_id=:account_id AND project_id=:project_id"
            ),
            {
                "id": requirement_id,
                "account_id": account_id,
                "project_id": project_id,
                "source_refs": json.dumps([_reference_dict(value) for value in source_refs]),
            },
        )
        _require_one(result.rowcount, "requirement_merge_target_missing")

    async def add_batch(self, requirements: tuple[RequirementWrite, ...]) -> None:
        for item in requirements:
            await self._connection.execute(
                text(
                    "INSERT INTO public.requirements "
                    "(id, account_id, project_id, context_version, category, title, description, "
                    "priority, status, source_refs, confidence, is_unsupported, "
                    "duplicate_group_key, generation_job_id, created_by_type, created_by) VALUES "
                    "(:id, :account_id, :project_id, :context_version, :category, :title, "
                    ":description, :priority, :status, CAST(:source_refs AS jsonb), :confidence, "
                    ":is_unsupported, :duplicate_group_key, :generation_job_id, 'ai', NULL)"
                ),
                {
                    "id": item.id,
                    "account_id": item.account_id,
                    "project_id": item.project_id,
                    "context_version": item.context_version,
                    "category": item.category,
                    "title": item.title,
                    "description": item.description,
                    "priority": item.priority,
                    "status": item.status,
                    "source_refs": json.dumps(
                        [_reference_dict(value) for value in item.source_refs]
                    ),
                    "confidence": item.confidence,
                    "is_unsupported": item.is_unsupported,
                    "duplicate_group_key": item.duplicate_group_key,
                    "generation_job_id": item.generation_job_id,
                },
            )

    async def add_conflict_events(
        self, events: tuple[RequirementConflictEvent, ...]
    ) -> None:
        for event in events:
            await self._connection.execute(
                text(
                    "INSERT INTO public.outbox_events "
                    "(id, account_id, aggregate_type, aggregate_id, event_type, "
                    "delivery_channel, payload, status, attempt_count, available_at) VALUES "
                    "(:id, :account_id, 'project', :project_id, "
                    "'requirement.conflict_detected', 'domain_event', "
                    "CAST(:payload AS jsonb), 'pending', 0, :available_at)"
                ),
                {
                    "id": event.id,
                    "account_id": event.account_id,
                    "project_id": event.project_id,
                    "payload": json.dumps(
                        {
                            "project_id": str(event.project_id),
                            "context_version": event.context_version,
                            "requirement_ids": [str(value) for value in event.requirement_ids],
                        }
                    ),
                    "available_at": event.occurred_at,
                },
            )

    async def complete_job_success(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> None:
        result = await self._connection.execute(
            text(
                "UPDATE public.jobs SET status='succeeded', finished_at=CURRENT_TIMESTAMP, "
                "error_code=NULL, error_detail=NULL WHERE id=:job_id "
                "AND account_id=:account_id AND project_id=:project_id "
                "AND job_type='requirement_generation' AND status='running'"
            ),
            {
                "job_id": generation_job_id,
                "account_id": account_id,
                "project_id": project_id,
            },
        )
        _require_one(result.rowcount, "generation_job_not_running")


class PostgresRequirementGenerationUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._repository: SqlRequirementGenerationRepository | None = None
        self._committed = False

    @property
    def repository(self) -> RequirementGenerationRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> PostgresRequirementGenerationUnitOfWork:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self._repository = SqlRequirementGenerationRepository(self._connection)
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
            raise RequirementGenerationRepositoryError(
                "requirement_generation_persistence_failed"
            ) from None

    async def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._transaction.commit()
        except SQLAlchemyError:
            raise RequirementGenerationRepositoryError(
                "requirement_generation_persistence_failed"
            ) from None
        self._committed = True


class PostgresRequirementGenerationUnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def __call__(self) -> RequirementGenerationUnitOfWork:
        return PostgresRequirementGenerationUnitOfWork(self._engine)


class SqlAlchemyRequirementGenerationJobStore:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def prepare(
        self, message: RequirementGenerationJobMessage
    ) -> RequirementGenerationJobInput:
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
                    or job["job_type"] != REQUIREMENT_GENERATION_JOB_TYPE
                    or job["account_id"] is None
                    or job["project_id"] is None
                    or job["status"] not in {"queued", "running"}
                ):
                    raise RequirementGenerationMessageValidationError(
                        "Requirement Generation Job is invalid"
                    )
                context_version, revisions = _job_payload(job["payload_ref"])
                event = (
                    await connection.execute(
                        text(
                            "SELECT account_id, aggregate_type, aggregate_id, event_type, "
                            "delivery_channel, payload FROM public.outbox_events WHERE id=:event_id"
                        ),
                        {"event_id": message.outbox_event_id},
                    )
                ).mappings().one_or_none()
                expected_payload = {
                    "jobId": str(message.job_id),
                    "taskType": REQUIREMENT_GENERATION_JOB_TYPE,
                    "payloadVersion": REQUIREMENT_GENERATION_MESSAGE_VERSION,
                }
                if (
                    event is None
                    or event["account_id"] != job["account_id"]
                    or event["aggregate_type"] != "project"
                    or event["aggregate_id"] != job["project_id"]
                    or event["event_type"] != REQUIREMENT_GENERATION_EVENT_TYPE
                    or event["delivery_channel"] != "job_queue"
                    or event["payload"] != expected_payload
                ):
                    raise RequirementGenerationMessageValidationError(
                        "Requirement Generation Outbox reference is invalid"
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
                        raise RequirementGenerationRuntimePersistenceError
                return RequirementGenerationJobInput(
                    job_id=message.job_id,
                    account_id=job["account_id"],
                    project_id=job["project_id"],
                    correlation_id=job["correlation_id"],
                    context_version=context_version,
                    context_item_revisions=revisions,
                    first_attempt=first_attempt,
                )
        except (
            RequirementGenerationMessageValidationError,
            RequirementGenerationRuntimePersistenceError,
        ):
            raise
        except SQLAlchemyError:
            raise RequirementGenerationRuntimePersistenceError from None

    async def finalize_failure(
        self, job: RequirementGenerationJobInput, *, error_code: str
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='failed', finished_at=:finished_at, "
                        "error_code=:error_code, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id "
                        "AND job_type='requirement_generation' AND status='running'"
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
                    raise RequirementGenerationRuntimePersistenceError
        except RequirementGenerationRuntimePersistenceError:
            raise
        except SQLAlchemyError:
            raise RequirementGenerationRuntimePersistenceError from None


def _job_payload(value: object) -> tuple[int, tuple[ContextItemRevision, ...]]:
    if not isinstance(value, dict) or set(value) != {
        "context_version",
        "context_item_revisions",
    }:
        raise RequirementGenerationMessageValidationError("AI-02 Job payload is invalid")
    context_version = value["context_version"]
    revisions_value = value["context_item_revisions"]
    if (
        isinstance(context_version, bool)
        or not isinstance(context_version, int)
        or context_version < 1
    ):
        raise RequirementGenerationMessageValidationError("AI-02 Context version is invalid")
    if not isinstance(revisions_value, list) or not revisions_value:
        raise RequirementGenerationMessageValidationError("AI-02 revision vector is invalid")
    try:
        revisions = tuple(
            ContextItemRevision(
                context_item_id=UUID(str(item["context_item_id"])),
                updated_at=datetime.fromisoformat(str(item["updated_at"])),
            )
            for item in revisions_value
            if isinstance(item, dict)
            and set(item) == {"context_item_id", "updated_at"}
        )
    except (KeyError, TypeError, ValueError):
        raise RequirementGenerationMessageValidationError(
            "AI-02 revision vector is invalid"
        ) from None
    canonical = tuple(sorted(revisions, key=lambda item: item.context_item_id.int))
    if len(revisions) != len(revisions_value) or canonical != revisions or len(
        {item.context_item_id for item in revisions}
    ) != len(revisions):
        raise RequirementGenerationMessageValidationError("AI-02 revision vector is invalid")
    return context_version, revisions


def _context_item(row: object) -> RequirementContextItem:
    value = cast(dict[str, object], row)
    status = str(value["status"])
    if status not in {"proposed", "confirmed"}:
        raise RequirementGenerationRepositoryError("ineligible_context_item_loaded")
    return RequirementContextItem(
        id=cast(UUID, value["id"]),
        updated_at=cast(datetime, value["updated_at"]),
        item_type=str(value["item_type"]),
        status=cast(Literal["proposed", "confirmed"], status),
        content=str(value["content"]),
        source_refs=tuple(
            _reference_from_dict(item)
            for item in cast(list[object], value["source_refs"])
        ),
    )


def _existing_requirement(row: object) -> ExistingRequirement:
    value = cast(dict[str, object], row)
    return ExistingRequirement(
        id=cast(UUID, value["id"]),
        category=cast(
            Literal[
                "functional", "content", "visual", "technical", "constraint", "business"
            ],
            value["category"],
        ),
        title=str(value["title"]),
        description=str(value["description"]),
        priority=cast(Literal["must", "should", "could"], value["priority"]),
        status=cast(Literal["draft", "confirmed", "superseded", "removed"], value["status"]),
        source_refs=tuple(
            _reference_from_dict(item)
            for item in cast(list[object], value["source_refs"])
        ),
        confidence=cast(Decimal | None, value["confidence"]),
        is_unsupported=bool(value["is_unsupported"]),
        duplicate_group_key=cast(str | None, value["duplicate_group_key"]),
        generation_job_id=cast(UUID | None, value["generation_job_id"]),
    )


def _reference_from_dict(value: object) -> RequirementSourceReference:
    if not isinstance(value, dict) or set(value) - {
        "source_id", "source_version_id", "start_offset", "end_offset"
    }:
        raise RequirementGenerationRepositoryError("invalid_persisted_source_reference")
    try:
        return RequirementSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (KeyError, TypeError, ValueError):
        raise RequirementGenerationRepositoryError(
            "invalid_persisted_source_reference"
        ) from None


def _reference_dict(value: RequirementSourceReference) -> dict[str, object]:
    result: dict[str, object] = {
        "source_id": str(value.source_id),
        "source_version_id": str(value.source_version_id),
    }
    if value.start_offset is not None:
        result["start_offset"] = value.start_offset
        result["end_offset"] = value.end_offset
    return result


def _require_one(rowcount: int, reason_code: str) -> None:
    if rowcount != 1:
        raise RequirementGenerationRepositoryError(reason_code)
