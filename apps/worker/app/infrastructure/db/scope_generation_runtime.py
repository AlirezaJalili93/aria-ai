from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from aria_backend_application.scope_content import (
    ScopeDraftValidationError,
    validate_scope_content,
)
from aria_backend_application.scope_generation import (
    ScopeDraftAlreadyExistsError,
    ScopeGenerationBlockedError,
    ScopeGenerationCommand,
    ScopeGenerationInputChangedError,
    ScopeGenerationRepositoryError,
    ScopeGenerationRequirement,
    ScopeGenerationSnapshot,
    ScopeGenerationValidationError,
    ScopeInputRevision,
    ScopeRequirementStatus,
)
from aria_backend_application.scope_readiness import (
    ScopeReadinessGap,
    ScopeReadinessGapSeverity,
    ScopeReadinessGapStatus,
    ScopeReadinessPolicy,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncTransaction

from app.application.scope_generation_consumer import (
    SCOPE_GENERATION_EVENT_TYPE,
    SCOPE_GENERATION_JOB_TYPE,
    SCOPE_GENERATION_MESSAGE_VERSION,
    ScopeGenerationJobInput,
    ScopeGenerationJobMessage,
    ScopeGenerationMessageValidationError,
    ScopeGenerationRuntimePersistenceError,
)


@dataclass(frozen=True, slots=True)
class _SnapshotRows:
    project_type: str
    context_items: tuple[dict[str, object], ...]
    requirements: tuple[dict[str, object], ...]
    gaps: tuple[dict[str, object], ...]

    @property
    def context_revisions(self) -> tuple[ScopeInputRevision, ...]:
        return _row_revisions(self.context_items)

    @property
    def requirement_revisions(self) -> tuple[ScopeInputRevision, ...]:
        return _row_revisions(self.requirements)

    @property
    def gap_revisions(self) -> tuple[ScopeInputRevision, ...]:
        return _row_revisions(self.gaps)


def _row_revisions(rows: tuple[dict[str, object], ...]) -> tuple[ScopeInputRevision, ...]:
    return tuple(
        ScopeInputRevision(cast(UUID, row["id"]), cast(datetime, row["updated_at"])) for row in rows
    )


def _pins_match(
    rows: _SnapshotRows,
    *,
    context_item_revisions: tuple[ScopeInputRevision, ...],
    requirement_revisions: tuple[ScopeInputRevision, ...],
    gap_revisions: tuple[ScopeInputRevision, ...],
) -> bool:
    return (
        rows.context_revisions == context_item_revisions
        and rows.requirement_revisions == requirement_revisions
        and rows.gap_revisions == gap_revisions
    )


async def _snapshot_rows(
    connection: AsyncConnection,
    *,
    account_id: UUID,
    project_id: UUID,
    context_version: int,
    lock_project: bool = False,
) -> _SnapshotRows | None:
    project_sql = (
        "SELECT project_type, current_context_version FROM public.projects "
        "WHERE id=:project_id AND account_id=:account_id AND deleted_at IS NULL"
        + (" FOR UPDATE" if lock_project else "")
    )
    params = {
        "account_id": account_id,
        "project_id": project_id,
        "context_version": context_version,
    }
    project = (await connection.execute(text(project_sql), params)).mappings().one_or_none()
    if project is None or project["current_context_version"] != context_version:
        return None
    context_rows = (
        (
            await connection.execute(
                text(
                    "SELECT id, updated_at, item_type, status, content, source_refs "
                    "FROM public.context_items WHERE account_id=:account_id "
                    "AND project_id=:project_id AND context_version=:context_version "
                    "AND status IN ('proposed','confirmed') ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    requirement_rows = (
        (
            await connection.execute(
                text(
                    "SELECT id, updated_at, category, title, description, priority, status, "
                    "source_refs FROM public.requirements WHERE account_id=:account_id "
                    "AND project_id=:project_id AND context_version=:context_version "
                    "AND status IN ('draft','confirmed') ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    gap_rows = (
        (
            await connection.execute(
                text(
                    "SELECT id, updated_at, gap_type, severity, status, explanation "
                    "FROM public.gaps WHERE account_id=:account_id AND project_id=:project_id "
                    "AND context_version=:context_version ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return _SnapshotRows(
        project_type=str(project["project_type"]),
        context_items=tuple(dict(row) for row in context_rows),
        requirements=tuple(dict(row) for row in requirement_rows),
        gaps=tuple(dict(row) for row in gap_rows),
    )


def _readiness(
    rows: _SnapshotRows,
    *,
    account_id: UUID,
    project_id: UUID,
    context_version: int,
) -> bool:
    return (
        ScopeReadinessPolicy()
        .evaluate(
            account_id=account_id,
            project_id=project_id,
            context_version=context_version,
            gaps=(
                ScopeReadinessGap(
                    id=cast(UUID, row["id"]),
                    account_id=account_id,
                    project_id=project_id,
                    context_version=context_version,
                    status=cast(ScopeReadinessGapStatus, row["status"]),
                    severity=cast(ScopeReadinessGapSeverity, row["severity"]),
                )
                for row in rows.gaps
            ),
        )
        .ready_for_share
    )


class PostgresScopeGenerationSnapshotReader:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve_exact(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        job_id: UUID,
        context_item_revisions: tuple[ScopeInputRevision, ...],
        requirement_revisions: tuple[ScopeInputRevision, ...],
        gap_revisions: tuple[ScopeInputRevision, ...],
    ) -> ScopeGenerationSnapshot | None:
        del job_id
        try:
            async with self._engine.connect() as connection:
                rows = await _snapshot_rows(
                    connection,
                    account_id=account_id,
                    project_id=project_id,
                    context_version=context_version,
                )
            if rows is None:
                raise ScopeGenerationInputChangedError
            if not _pins_match(
                rows,
                context_item_revisions=context_item_revisions,
                requirement_revisions=requirement_revisions,
                gap_revisions=gap_revisions,
            ):
                raise ScopeGenerationInputChangedError
            return ScopeGenerationSnapshot(
                account_id=account_id,
                project_id=project_id,
                context_version=context_version,
                project_type=rows.project_type,
                context_items=tuple(
                    {
                        "id": str(row["id"]),
                        "item_type": row["item_type"],
                        "status": row["status"],
                        "content": row["content"],
                        "source_refs": row["source_refs"],
                    }
                    for row in rows.context_items
                ),
                requirements=tuple(
                    ScopeGenerationRequirement(
                        id=cast(UUID, row["id"]),
                        context_version=context_version,
                        status=cast(ScopeRequirementStatus, row["status"]),
                        payload={
                            "category": row["category"],
                            "title": row["title"],
                            "description": row["description"],
                            "priority": row["priority"],
                            "source_refs": row["source_refs"],
                        },
                    )
                    for row in rows.requirements
                ),
                resolved_gaps=tuple(
                    {
                        "id": str(row["id"]),
                        "gap_type": row["gap_type"],
                        "severity": row["severity"],
                        "status": row["status"],
                        "explanation": row["explanation"],
                    }
                    for row in rows.gaps
                    if row["status"] == "resolved"
                ),
                remaining_non_blocking_gaps=tuple(
                    {
                        "id": str(row["id"]),
                        "gap_type": row["gap_type"],
                        "severity": row["severity"],
                        "status": row["status"],
                        "explanation": row["explanation"],
                    }
                    for row in rows.gaps
                    if row["status"] == "open" and row["severity"] != "critical"
                ),
                ready_for_share=_readiness(
                    rows,
                    account_id=account_id,
                    project_id=project_id,
                    context_version=context_version,
                ),
            )
        except (ScopeGenerationInputChangedError, ScopeGenerationBlockedError):
            raise
        except SQLAlchemyError:
            raise ScopeGenerationRepositoryError("scope_snapshot_unavailable") from None


class PostgresScopeGenerationFinalizer:
    def __init__(self, engine: AsyncEngine, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._engine = engine
        self._id_factory = id_factory

    async def exists(self, *, account_id: UUID, project_id: UUID, context_version: int) -> bool:
        try:
            async with self._engine.connect() as connection:
                value = await connection.scalar(
                    text(
                        "SELECT id FROM public.scope_drafts WHERE account_id=:account_id "
                        "AND project_id=:project_id AND context_version=:context_version"
                    ),
                    {
                        "account_id": account_id,
                        "project_id": project_id,
                        "context_version": context_version,
                    },
                )
            return value is not None
        except SQLAlchemyError:
            raise ScopeGenerationRepositoryError("scope_draft_lookup_failed") from None

    async def finalize(
        self, *, command: ScopeGenerationCommand, content: Mapping[str, object]
    ) -> UUID:
        draft_id = self._id_factory()
        connection = await self._engine.connect()
        transaction = await connection.begin()
        try:
            job = (
                (
                    await connection.execute(
                        text(
                            "SELECT payload_ref FROM public.jobs WHERE id=:job_id "
                            "AND account_id=:account_id AND project_id=:project_id "
                            "AND job_type='scope_generation' AND status='running' FOR UPDATE"
                        ),
                        {
                            "job_id": command.job_id,
                            "account_id": command.account_id,
                            "project_id": command.project_id,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
            if job is None or _job_payload(job["payload_ref"]) != (
                command.context_version,
                command.context_item_revisions,
                command.requirement_revisions,
                command.gap_revisions,
            ):
                raise ScopeGenerationInputChangedError
            # Keep the recheck and Draft/Job writes in one short transaction.
            await connection.execute(text("SELECT public.lock_scope_generation_inputs()"))
            rows = await _snapshot_rows(
                connection,
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
                lock_project=True,
            )
            if rows is None or not _pins_match(
                rows,
                context_item_revisions=command.context_item_revisions,
                requirement_revisions=command.requirement_revisions,
                gap_revisions=command.gap_revisions,
            ):
                raise ScopeGenerationInputChangedError
            if not _readiness(
                rows,
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            ):
                raise ScopeGenerationBlockedError
            existing = await connection.scalar(
                text(
                    "SELECT id FROM public.scope_drafts WHERE account_id=:account_id "
                    "AND project_id=:project_id AND context_version=:context_version"
                ),
                {
                    "account_id": command.account_id,
                    "project_id": command.project_id,
                    "context_version": command.context_version,
                },
            )
            if existing is not None:
                raise ScopeDraftAlreadyExistsError
            try:
                validated = validate_scope_content(dict(content))
            except ScopeDraftValidationError:
                raise ScopeGenerationValidationError("scope_content_validation_failed") from None
            _validate_trace(validated, rows)
            await connection.execute(
                text(
                    "INSERT INTO public.scope_drafts "
                    "(id, account_id, project_id, context_version, content, "
                    "updated_by_type, updated_by) VALUES "
                    "(:id, :account_id, :project_id, :context_version, "
                    "CAST(:content AS jsonb), 'ai', NULL)"
                ),
                {
                    "id": draft_id,
                    "account_id": command.account_id,
                    "project_id": command.project_id,
                    "context_version": command.context_version,
                    "content": json.dumps(validated, ensure_ascii=False),
                },
            )
            updated = await connection.execute(
                text(
                    "UPDATE public.jobs SET status='succeeded', finished_at=CURRENT_TIMESTAMP, "
                    "error_code=NULL, error_detail=NULL WHERE id=:job_id "
                    "AND account_id=:account_id AND project_id=:project_id "
                    "AND job_type='scope_generation' AND status='running'"
                ),
                {
                    "job_id": command.job_id,
                    "account_id": command.account_id,
                    "project_id": command.project_id,
                },
            )
            if updated.rowcount != 1:
                raise ScopeGenerationRepositoryError("scope_job_not_running")
            await self._commit(transaction)
            return draft_id
        except IntegrityError as error:
            if "uq_scope_drafts_project_context_version" in str(error.orig):
                raise ScopeDraftAlreadyExistsError from None
            raise ScopeGenerationRepositoryError("scope_finalization_failed") from None
        except SQLAlchemyError:
            raise ScopeGenerationRepositoryError("scope_finalization_failed") from None
        finally:
            if transaction.is_active:
                await transaction.rollback()
            await connection.close()

    async def _commit(self, transaction: AsyncTransaction) -> None:
        """An override point for deterministic rollback tests, not a retry hook."""
        await transaction.commit()


def _validate_trace(content: dict[str, object], rows: _SnapshotRows) -> None:
    sections = cast(list[dict[str, object]], content["sections"])
    trace_ids: dict[str, set[UUID]] = {
        "context_item_ids": set(),
        "requirement_ids": set(),
        "gap_ids": set(),
    }
    for section in sections:
        trace = cast(dict[str, list[str]], section["trace"])
        for key in trace_ids:
            trace_ids[key].update(UUID(value) for value in trace[key])
    targets = {
        "context_item_ids": {cast(UUID, row["id"]) for row in rows.context_items},
        "requirement_ids": {cast(UUID, row["id"]) for row in rows.requirements},
        "gap_ids": {cast(UUID, row["id"]) for row in rows.gaps},
    }
    if any(not ids.issubset(targets[key]) for key, ids in trace_ids.items()):
        raise ScopeGenerationValidationError("scope_trace_invalid")
    resolved = {cast(UUID, row["id"]) for row in rows.gaps if row["status"] == "resolved"}
    resolved_section = next(item for item in sections if item["section_id"] == "resolved_gaps")
    resolved_trace = cast(dict[str, list[str]], resolved_section["trace"])
    if not {UUID(value) for value in resolved_trace["gap_ids"]}.issubset(resolved):
        raise ScopeGenerationValidationError("scope_trace_invalid")


class SqlAlchemyScopeGenerationJobStore:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def prepare(self, message: ScopeGenerationJobMessage) -> ScopeGenerationJobInput:
        try:
            async with self._engine.begin() as connection:
                job = (
                    (
                        await connection.execute(
                            text(
                                "SELECT id, account_id, project_id, job_type, status, payload_ref, "
                                "correlation_id FROM public.jobs WHERE id=:job_id FOR UPDATE"
                            ),
                            {"job_id": message.job_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if (
                    job is None
                    or job["job_type"] != SCOPE_GENERATION_JOB_TYPE
                    or job["account_id"] is None
                    or job["project_id"] is None
                    or job["status"] not in {"queued", "running"}
                ):
                    raise ScopeGenerationMessageValidationError("AI-05 Job is invalid")
                context_version, context_revisions, requirement_revisions, gap_revisions = (
                    _job_payload(job["payload_ref"])
                )
                event = (
                    (
                        await connection.execute(
                            text(
                                "SELECT account_id, aggregate_type, aggregate_id, event_type, "
                                "delivery_channel, payload FROM public.outbox_events "
                                "WHERE id=:event_id"
                            ),
                            {"event_id": message.outbox_event_id},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                expected_payload = {
                    "jobId": str(message.job_id),
                    "taskType": SCOPE_GENERATION_JOB_TYPE,
                    "payloadVersion": SCOPE_GENERATION_MESSAGE_VERSION,
                }
                if (
                    event is None
                    or event["account_id"] != job["account_id"]
                    or event["aggregate_type"] != "project"
                    or event["aggregate_id"] != job["project_id"]
                    or event["event_type"] != SCOPE_GENERATION_EVENT_TYPE
                    or event["delivery_channel"] != "job_queue"
                    or event["payload"] != expected_payload
                ):
                    raise ScopeGenerationMessageValidationError("AI-05 Outbox reference is invalid")
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
                        raise ScopeGenerationRuntimePersistenceError
                return ScopeGenerationJobInput(
                    job_id=message.job_id,
                    account_id=job["account_id"],
                    project_id=job["project_id"],
                    correlation_id=job["correlation_id"],
                    context_version=context_version,
                    context_item_revisions=context_revisions,
                    requirement_revisions=requirement_revisions,
                    gap_revisions=gap_revisions,
                    first_attempt=first_attempt,
                )
        except (ScopeGenerationMessageValidationError, ScopeGenerationRuntimePersistenceError):
            raise
        except SQLAlchemyError:
            raise ScopeGenerationRuntimePersistenceError from None

    async def finalize_failure(self, job: ScopeGenerationJobInput, *, error_code: str) -> None:
        try:
            async with self._engine.begin() as connection:
                result = await connection.execute(
                    text(
                        "UPDATE public.jobs SET status='failed', finished_at=:finished_at, "
                        "error_code=:error_code, error_detail=NULL WHERE id=:job_id "
                        "AND account_id=:account_id AND project_id=:project_id "
                        "AND job_type='scope_generation' AND status='running'"
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
                    raise ScopeGenerationRuntimePersistenceError
        except ScopeGenerationRuntimePersistenceError:
            raise
        except SQLAlchemyError:
            raise ScopeGenerationRuntimePersistenceError from None


def _job_payload(
    value: object,
) -> tuple[
    int,
    tuple[ScopeInputRevision, ...],
    tuple[ScopeInputRevision, ...],
    tuple[ScopeInputRevision, ...],
]:
    expected = {
        "context_version",
        "context_item_revisions",
        "requirement_revisions",
        "gap_revisions",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ScopeGenerationMessageValidationError("AI-05 Job payload is invalid")
    context_version = value["context_version"]
    if (
        isinstance(context_version, bool)
        or not isinstance(context_version, int)
        or context_version < 1
    ):
        raise ScopeGenerationMessageValidationError("AI-05 Context version is invalid")
    return (
        context_version,
        _parse_revisions(value["context_item_revisions"], required=True),
        _parse_revisions(value["requirement_revisions"], required=True),
        _parse_revisions(value["gap_revisions"], required=False),
    )


def _parse_revisions(value: object, *, required: bool) -> tuple[ScopeInputRevision, ...]:
    if not isinstance(value, list) or (required and not value):
        raise ScopeGenerationMessageValidationError("AI-05 revision vector is invalid")
    try:
        revisions = tuple(
            ScopeInputRevision(
                id=UUID(str(item["id"])),
                updated_at=datetime.fromisoformat(str(item["updated_at"])),
            )
            for item in value
            if isinstance(item, dict) and set(item) == {"id", "updated_at"}
        )
    except (KeyError, TypeError, ValueError):
        raise ScopeGenerationMessageValidationError("AI-05 revision vector is invalid") from None
    if (
        len(revisions) != len(value)
        or tuple(sorted(revisions, key=lambda item: item.id.int)) != revisions
        or len({item.id for item in revisions}) != len(revisions)
    ):
        raise ScopeGenerationMessageValidationError("AI-05 revision vector is invalid")
    return revisions
