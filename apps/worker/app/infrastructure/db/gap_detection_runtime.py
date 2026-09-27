from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from types import TracebackType
from typing import Literal, cast
from uuid import UUID

from aria_backend_application.gap_detection import (
    ContextItemRevision,
    GapContextItem,
    GapDetectionReplay,
    GapDetectionRepository,
    GapDetectionRepositoryError,
    GapDetectionSnapshot,
    GapDetectionUnitOfWork,
    GapRequirement,
    GapSnapshotRevisions,
    GapSourceReference,
    GapWrite,
    RequirementRevision,
)
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from app.application.gap_detection_consumer import (
    GAP_DETECTION_EVENT_TYPE,
    GAP_DETECTION_JOB_TYPE,
    GAP_DETECTION_MESSAGE_VERSION,
    GapDetectionJobInput,
    GapDetectionJobMessage,
    GapDetectionMessageValidationError,
    GapDetectionRuntimePersistenceError,
)


class PostgresGapDetectionSnapshotReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve_exact(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        completion_checklist_version: str,
    ) -> GapDetectionSnapshot | None:
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
                context_rows = (
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
                requirement_rows = (
                    await connection.execute(
                        text(
                            "SELECT id, updated_at, category, title, description, priority, "
                            "status, source_refs FROM public.requirements "
                            "WHERE account_id=:account_id AND project_id=:project_id "
                            "AND context_version=:context_version "
                            "AND status IN ('draft','confirmed') ORDER BY id"
                        ),
                        {
                            "account_id": account_id,
                            "project_id": project_id,
                            "context_version": context_version,
                        },
                    )
                ).mappings().all()
                context_items = tuple(_context_item(row) for row in context_rows)
                requirements = tuple(_requirement(row) for row in requirement_rows)
                await _validate_snapshot_provenance(
                    connection,
                    account_id=account_id,
                    project_id=project_id,
                    references=tuple(
                        reference for item in context_items for reference in item.source_refs
                    )
                    + tuple(
                        reference for item in requirements for reference in item.source_refs
                    ),
                )
        except GapDetectionRepositoryError:
            raise
        except SQLAlchemyError:
            raise GapDetectionRepositoryError("gap_snapshot_failed") from None
        return GapDetectionSnapshot(
            project_type=str(project_type),
            context_version=context_version,
            completion_checklist_version=completion_checklist_version,
            context_items=context_items,
            requirements=requirements,
        )


class SqlGapDetectionRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def resolve_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> GapDetectionReplay | None:
        job = (
            await self._connection.execute(
                text(
                    "SELECT status, error_code, payload_ref FROM public.jobs "
                    "WHERE id=:job_id AND account_id=:account_id AND project_id=:project_id "
                    "AND job_type='gap_detection' FOR UPDATE"
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
            return GapDetectionReplay(
                status="failed",
                gap_ids=(),
                gap_count=None,
                critical_candidate_count=None,
                error_code=job["error_code"],
            )
        metadata = job["payload_ref"]
        if not isinstance(metadata, dict):
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        gap_count = _nonnegative_int(metadata, "gap_count")
        rows = (
            await self._connection.execute(
                text(
                    "SELECT id, severity FROM public.gaps WHERE account_id=:account_id "
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
        gap_ids = tuple(row["id"] for row in rows)
        if len(gap_ids) != gap_count:
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        actual_critical = sum(row["severity"] == "critical" for row in rows)
        critical_gap_count = _nonnegative_int(metadata, "critical_gap_count")
        if critical_gap_count != actual_critical:
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        rule_generated_gap_count = _nonnegative_int(
            metadata, "rule_generated_gap_count"
        )
        if rule_generated_gap_count > gap_count:
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        return GapDetectionReplay(
            status="succeeded",
            gap_ids=gap_ids,
            gap_count=gap_count,
            critical_candidate_count=_nonnegative_int(
                metadata, "critical_candidate_count"
            ),
            error_code=None,
            rule_generated_gap_count=rule_generated_gap_count,
            critical_gap_count=critical_gap_count,
            completion_checklist_version=_nonempty_string(
                metadata, "completion_checklist_version"
            ),
            critical_rule_pack_version=_nonempty_string(
                metadata, "critical_rule_pack_version"
            ),
        )

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> GapSnapshotRevisions | None:
        project_type = await self._connection.scalar(
            text(
                "SELECT project_type FROM public.projects WHERE id=:project_id "
                "AND account_id=:account_id AND current_context_version>=:context_version "
                "AND deleted_at IS NULL FOR UPDATE"
            ),
            {
                "account_id": account_id,
                "project_id": project_id,
                "context_version": context_version,
            },
        )
        if project_type is None:
            return None
        await self._connection.execute(text("LOCK TABLE public.context_items IN SHARE MODE"))
        await self._connection.execute(text("LOCK TABLE public.requirements IN SHARE MODE"))
        context_rows = (
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
        requirement_rows = (
            await self._connection.execute(
                text(
                    "SELECT id, updated_at FROM public.requirements "
                    "WHERE account_id=:account_id AND project_id=:project_id "
                    "AND context_version=:context_version "
                    "AND status IN ('draft','confirmed') ORDER BY id"
                ),
                {
                    "account_id": account_id,
                    "project_id": project_id,
                    "context_version": context_version,
                },
            )
        ).mappings().all()
        return GapSnapshotRevisions(
            project_type=str(project_type),
            context_item_revisions=tuple(
                ContextItemRevision(row["id"], row["updated_at"])
                for row in context_rows
            ),
            requirement_revisions=tuple(
                RequirementRevision(row["id"], row["updated_at"])
                for row in requirement_rows
            ),
        )

    async def add_batch(self, gaps: tuple[GapWrite, ...]) -> None:
        for gap in gaps:
            await self._connection.execute(
                text(
                    "INSERT INTO public.gaps "
                    "(id, account_id, project_id, context_version, gap_type, severity, "
                    "status, source_refs, explanation, suggested_resolution_type, "
                    "generation_job_id) VALUES "
                    "(:id, :account_id, :project_id, :context_version, :gap_type, "
                    ":severity, 'open', CAST(:source_refs AS jsonb), :explanation, "
                    ":resolution, :generation_job_id)"
                ),
                {
                    "id": gap.id,
                    "account_id": gap.account_id,
                    "project_id": gap.project_id,
                    "context_version": gap.context_version,
                    "gap_type": gap.gap_type,
                    "severity": gap.severity,
                    "source_refs": json.dumps(
                        [_reference_dict(value) for value in gap.source_refs]
                    ),
                    "explanation": gap.explanation,
                    "resolution": gap.suggested_resolution_type,
                    "generation_job_id": gap.generation_job_id,
                },
            )
            for requirement_id in gap.affected_requirement_ids:
                await self._connection.execute(
                    text(
                        "INSERT INTO public.gap_requirement_links "
                        "(account_id, project_id, gap_id, requirement_id) VALUES "
                        "(:account_id, :project_id, :gap_id, :requirement_id)"
                    ),
                    {
                        "account_id": gap.account_id,
                        "project_id": gap.project_id,
                        "gap_id": gap.id,
                        "requirement_id": requirement_id,
                    },
                )

    async def mark_job_succeeded(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        gap_count: int,
        critical_candidate_count: int,
        rule_generated_gap_count: int,
        critical_gap_count: int,
        completion_checklist_version: str,
        critical_rule_pack_version: str,
        finished_at: datetime,
    ) -> None:
        row = (
            await self._connection.execute(
                text(
                    "SELECT payload_ref FROM public.jobs WHERE id=:job_id "
                    "AND account_id=:account_id AND project_id=:project_id "
                    "AND job_type='gap_detection' AND status='running' FOR UPDATE"
                ),
                {
                    "job_id": job_id,
                    "account_id": account_id,
                    "project_id": project_id,
                },
            )
        ).mappings().one_or_none()
        if row is None or not isinstance(row["payload_ref"], dict):
            raise GapDetectionRepositoryError("gap_generation_job_unavailable")
        payload_ref = {
            **row["payload_ref"],
            "gap_count": gap_count,
            "critical_candidate_count": critical_candidate_count,
            "rule_generated_gap_count": rule_generated_gap_count,
            "critical_gap_count": critical_gap_count,
            "completion_checklist_version": completion_checklist_version,
            "critical_rule_pack_version": critical_rule_pack_version,
        }
        result = await self._connection.execute(
            text(
                "UPDATE public.jobs SET payload_ref=CAST(:payload_ref AS jsonb), "
                "status='succeeded', finished_at=:finished_at, error_code=NULL, "
                "error_detail=NULL WHERE id=:job_id AND account_id=:account_id "
                "AND project_id=:project_id AND job_type='gap_detection' "
                "AND status='running'"
            ),
            {
                "payload_ref": json.dumps(payload_ref),
                "finished_at": finished_at,
                "job_id": job_id,
                "account_id": account_id,
                "project_id": project_id,
            },
        )
        _require_one(result.rowcount, "gap_generation_job_unavailable")


class PostgresGapDetectionUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._connection: AsyncConnection | None = None
        self._transaction: AsyncTransaction | None = None
        self._repository: SqlGapDetectionRepository | None = None
        self._committed = False

    @property
    def repository(self) -> GapDetectionRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> PostgresGapDetectionUnitOfWork:
        self._connection = await self._engine.connect()
        self._transaction = await self._connection.begin()
        self._repository = SqlGapDetectionRepository(self._connection)
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
            raise GapDetectionRepositoryError("gap_detection_persistence_failed") from None

    async def commit(self) -> None:
        if self._transaction is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._transaction.commit()
        except SQLAlchemyError:
            raise GapDetectionRepositoryError("gap_detection_persistence_failed") from None
        self._committed = True


class PostgresGapDetectionUnitOfWorkFactory:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def __call__(self) -> GapDetectionUnitOfWork:
        return PostgresGapDetectionUnitOfWork(self._engine)


class SqlAlchemyGapDetectionJobStore:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def prepare(self, message: GapDetectionJobMessage) -> GapDetectionJobInput:
        try:
            async with self._engine.begin() as connection:
                job = (
                    await connection.execute(
                        text(
                            "SELECT id, account_id, project_id, job_type, status, payload_ref, "
                            "correlation_id FROM public.jobs WHERE id=:job_id FOR UPDATE"
                        ),
                        {"job_id": message.job_id},
                    )
                ).mappings().one_or_none()
                if (
                    job is None
                    or job["job_type"] != GAP_DETECTION_JOB_TYPE
                    or job["account_id"] is None
                    or job["project_id"] is None
                    or job["status"] not in {"queued", "running"}
                ):
                    raise GapDetectionMessageValidationError(
                        "Gap Detection Job is invalid"
                    )
                (
                    context_version,
                    context_revisions,
                    requirement_revisions,
                    checklist_version,
                    rule_pack_version,
                ) = _job_payload(job["payload_ref"])
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
                    "taskType": GAP_DETECTION_JOB_TYPE,
                    "payloadVersion": GAP_DETECTION_MESSAGE_VERSION,
                }
                if (
                    event is None
                    or event["account_id"] != job["account_id"]
                    or event["aggregate_type"] != "project"
                    or event["aggregate_id"] != job["project_id"]
                    or event["event_type"] != GAP_DETECTION_EVENT_TYPE
                    or event["delivery_channel"] != "job_queue"
                    or event["payload"] != expected_payload
                ):
                    raise GapDetectionMessageValidationError(
                        "Gap Detection Outbox reference is invalid"
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
                        raise GapDetectionRuntimePersistenceError
                return GapDetectionJobInput(
                    job_id=message.job_id,
                    account_id=job["account_id"],
                    project_id=job["project_id"],
                    correlation_id=job["correlation_id"],
                    context_version=context_version,
                    context_item_revisions=context_revisions,
                    requirement_revisions=requirement_revisions,
                    completion_checklist_version=checklist_version,
                    critical_rule_pack_version=rule_pack_version,
                    first_attempt=first_attempt,
                )
        except (GapDetectionMessageValidationError, GapDetectionRuntimePersistenceError):
            raise
        except SQLAlchemyError:
            raise GapDetectionRuntimePersistenceError from None

    async def finalize_failure(
        self, job: GapDetectionJobInput, *, error_code: str
    ) -> None:
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='failed', finished_at=:finished_at, "
                        "error_code=:error_code, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id "
                        "AND job_type='gap_detection' AND status='running'"
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
                    raise GapDetectionRuntimePersistenceError
        except GapDetectionRuntimePersistenceError:
            raise
        except SQLAlchemyError:
            raise GapDetectionRuntimePersistenceError from None


def _job_payload(
    value: object,
) -> tuple[
    int,
    tuple[ContextItemRevision, ...],
    tuple[RequirementRevision, ...],
    str,
    str,
]:
    expected = {
        "context_version",
        "context_item_revisions",
        "requirement_revisions",
        "completion_checklist_version",
        "critical_rule_pack_version",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise GapDetectionMessageValidationError("AI-03 Job payload is invalid")
    context_version = value["context_version"]
    if (
        isinstance(context_version, bool)
        or not isinstance(context_version, int)
        or context_version < 1
    ):
        raise GapDetectionMessageValidationError("AI-03 Context version is invalid")
    context_revisions = _context_revisions(value["context_item_revisions"])
    requirement_revisions = _requirement_revisions(value["requirement_revisions"])
    checklist = value["completion_checklist_version"]
    rule_pack = value["critical_rule_pack_version"]
    if not isinstance(checklist, str) or not checklist:
        raise GapDetectionMessageValidationError("AI-03 Checklist version is invalid")
    if not isinstance(rule_pack, str) or not rule_pack:
        raise GapDetectionMessageValidationError("AI-03 Rule Pack version is invalid")
    return context_version, context_revisions, requirement_revisions, checklist, rule_pack


def _context_revisions(value: object) -> tuple[ContextItemRevision, ...]:
    if not isinstance(value, list) or not value:
        raise GapDetectionMessageValidationError("AI-03 Context revision vector is invalid")
    try:
        revisions = tuple(
            ContextItemRevision(
                context_item_id=UUID(str(item["context_item_id"])),
                updated_at=datetime.fromisoformat(str(item["updated_at"])),
            )
            for item in value
            if isinstance(item, dict)
            and set(item) == {"context_item_id", "updated_at"}
        )
    except (KeyError, TypeError, ValueError):
        raise GapDetectionMessageValidationError(
            "AI-03 Context revision vector is invalid"
        ) from None
    canonical = tuple(sorted(revisions, key=lambda item: item.context_item_id.int))
    if len(revisions) != len(value) or canonical != revisions or len(
        {item.context_item_id for item in revisions}
    ) != len(revisions):
        raise GapDetectionMessageValidationError(
            "AI-03 Context revision vector is invalid"
        )
    return revisions


def _requirement_revisions(value: object) -> tuple[RequirementRevision, ...]:
    if not isinstance(value, list):
        raise GapDetectionMessageValidationError(
            "AI-03 Requirement revision vector is invalid"
        )
    try:
        revisions = tuple(
            RequirementRevision(
                requirement_id=UUID(str(item["requirement_id"])),
                updated_at=datetime.fromisoformat(str(item["updated_at"])),
            )
            for item in value
            if isinstance(item, dict)
            and set(item) == {"requirement_id", "updated_at"}
        )
    except (KeyError, TypeError, ValueError):
        raise GapDetectionMessageValidationError(
            "AI-03 Requirement revision vector is invalid"
        ) from None
    canonical = tuple(sorted(revisions, key=lambda item: item.requirement_id.int))
    if len(revisions) != len(value) or canonical != revisions or len(
        {item.requirement_id for item in revisions}
    ) != len(revisions):
        raise GapDetectionMessageValidationError(
            "AI-03 Requirement revision vector is invalid"
        )
    return revisions


def _context_item(row: object) -> GapContextItem:
    value = cast(dict[str, object], row)
    status = str(value["status"])
    if status not in {"proposed", "confirmed"}:
        raise GapDetectionRepositoryError("ineligible_context_item_loaded")
    return GapContextItem(
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


def _requirement(row: object) -> GapRequirement:
    value = cast(dict[str, object], row)
    status = str(value["status"])
    if status not in {"draft", "confirmed"}:
        raise GapDetectionRepositoryError("ineligible_requirement_loaded")
    return GapRequirement(
        id=cast(UUID, value["id"]),
        updated_at=cast(datetime, value["updated_at"]),
        category=str(value["category"]),
        title=str(value["title"]),
        description=str(value["description"]),
        priority=str(value["priority"]),
        status=cast(Literal["draft", "confirmed"], status),
        source_refs=tuple(
            _reference_from_dict(item)
            for item in cast(list[object], value["source_refs"])
        ),
    )


def _reference_from_dict(value: object) -> GapSourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if (
        not isinstance(value, dict)
        or set(value) - allowed
        or "source_id" not in value
        or "source_version_id" not in value
    ):
        raise GapDetectionRepositoryError("invalid_persisted_source_reference")
    try:
        return GapSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError):
        raise GapDetectionRepositoryError(
            "invalid_persisted_source_reference"
        ) from None


def _reference_dict(value: GapSourceReference) -> dict[str, object]:
    result: dict[str, object] = {
        "source_id": str(value.source_id),
        "source_version_id": str(value.source_version_id),
    }
    if value.start_offset is not None:
        result["start_offset"] = value.start_offset
        result["end_offset"] = value.end_offset
    return result


async def _validate_snapshot_provenance(
    connection: AsyncConnection,
    *,
    account_id: UUID,
    project_id: UUID,
    references: tuple[GapSourceReference, ...],
) -> None:
    unique = {reference.identity(): reference for reference in references}
    if not unique:
        return
    rows = (
        await connection.execute(
            text(
                "SELECT id, source_id, canonical_text FROM public.context_source_versions "
                "WHERE account_id=:account_id AND project_id=:project_id "
                "AND parse_status='ready'"
            ),
            {"account_id": account_id, "project_id": project_id},
        )
    ).mappings().all()
    targets = {
        (row["id"], row["source_id"]): row["canonical_text"] for row in rows
    }
    for reference in unique.values():
        target = (reference.source_version_id, reference.source_id)
        if target not in targets:
            raise GapDetectionRepositoryError("invalid_gap_snapshot_provenance")
        canonical_text = targets[target]
        if reference.end_offset is not None and (
            canonical_text is None or reference.end_offset > len(canonical_text)
        ):
            raise GapDetectionRepositoryError("invalid_gap_snapshot_provenance")


def _nonnegative_int(metadata: dict[str, object], key: str) -> int:
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
    return value


def _nonempty_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
    return value


def _require_one(rowcount: int, reason_code: str) -> None:
    if rowcount != 1:
        raise GapDetectionRepositoryError(reason_code)
