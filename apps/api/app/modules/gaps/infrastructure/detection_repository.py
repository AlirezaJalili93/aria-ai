from __future__ import annotations

from datetime import datetime
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
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.infrastructure.models import (
    ContextItemModel,
    ContextSourceVersionModel,
)
from app.modules.gaps.infrastructure.models import GapModel, GapRequirementLinkModel
from app.modules.jobs.infrastructure.models import JobModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.requirements.infrastructure.models import RequirementModel


class SqlAlchemyGapDetectionSnapshotReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_exact(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        completion_checklist_version: str,
    ) -> GapDetectionSnapshot | None:
        try:
            async with self._session_factory() as session:
                project_type = await session.scalar(
                    select(ProjectModel.project_type).where(
                        ProjectModel.id == project_id,
                        ProjectModel.account_id == account_id,
                        ProjectModel.current_context_version >= context_version,
                        ProjectModel.deleted_at.is_(None),
                    )
                )
                if project_type is None:
                    return None
                context_models = (
                    await session.scalars(
                        select(ContextItemModel)
                        .where(
                            ContextItemModel.account_id == account_id,
                            ContextItemModel.project_id == project_id,
                            ContextItemModel.context_version == context_version,
                            ContextItemModel.status.in_(("proposed", "confirmed")),
                        )
                        .order_by(ContextItemModel.id)
                    )
                ).all()
                requirement_models = (
                    await session.scalars(
                        select(RequirementModel)
                        .where(
                            RequirementModel.account_id == account_id,
                            RequirementModel.project_id == project_id,
                            RequirementModel.context_version == context_version,
                            RequirementModel.status.in_(("draft", "confirmed")),
                        )
                        .order_by(RequirementModel.id)
                    )
                ).all()
                context_items = tuple(_context_item_from_model(model) for model in context_models)
                requirements = tuple(_requirement_from_model(model) for model in requirement_models)
                await _validate_snapshot_provenance(
                    session,
                    account_id=account_id,
                    project_id=project_id,
                    references=tuple(
                        reference for item in context_items for reference in item.source_refs
                    )
                    + tuple(reference for item in requirements for reference in item.source_refs),
                )
        except SQLAlchemyError as error:
            raise GapDetectionRepositoryError("gap_snapshot_failed") from error
        return GapDetectionSnapshot(
            project_type=project_type,
            context_version=context_version,
            completion_checklist_version=completion_checklist_version,
            context_items=context_items,
            requirements=requirements,
        )


class SqlAlchemyGapDetectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> GapDetectionReplay | None:
        job = await self._session.scalar(
            select(JobModel)
            .where(
                JobModel.id == generation_job_id,
                JobModel.account_id == account_id,
                JobModel.project_id == project_id,
            )
            .with_for_update()
        )
        if job is None:
            return None
        if job.status not in {"succeeded", "failed"}:
            return None
        if job.status == "failed":
            return GapDetectionReplay(
                status="failed",
                gap_ids=(),
                gap_count=None,
                critical_candidate_count=None,
                error_code=job.error_code,
            )
        metadata = job.payload_ref
        gap_count = metadata.get("gap_count") if isinstance(metadata, dict) else None
        if isinstance(gap_count, bool) or not isinstance(gap_count, int) or gap_count < 0:
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        gap_rows = tuple(
            (
                await self._session.execute(
                    select(GapModel.id, GapModel.severity)
                    .where(
                        GapModel.account_id == account_id,
                        GapModel.project_id == project_id,
                        GapModel.generation_job_id == generation_job_id,
                    )
                    .order_by(GapModel.created_at, GapModel.id)
                )
            ).all()
        )
        gap_ids = tuple(row.id for row in gap_rows)
        if len(gap_ids) != gap_count:
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        return GapDetectionReplay(
            status="succeeded",
            gap_ids=gap_ids,
            gap_count=gap_count,
            critical_candidate_count=sum(row.severity == "critical" for row in gap_rows),
            error_code=None,
        )

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> GapSnapshotRevisions | None:
        project = await self._session.scalar(
            select(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.current_context_version >= context_version,
                ProjectModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if project is None:
            return None
        await self._session.execute(text("LOCK TABLE context_items IN SHARE MODE"))
        await self._session.execute(text("LOCK TABLE requirements IN SHARE MODE"))
        context_rows = (
            await self._session.execute(
                select(ContextItemModel.id, ContextItemModel.updated_at)
                .where(
                    ContextItemModel.account_id == account_id,
                    ContextItemModel.project_id == project_id,
                    ContextItemModel.context_version == context_version,
                    ContextItemModel.status.in_(("proposed", "confirmed")),
                )
                .order_by(ContextItemModel.id)
            )
        ).all()
        requirement_rows = (
            await self._session.execute(
                select(RequirementModel.id, RequirementModel.updated_at)
                .where(
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    RequirementModel.context_version == context_version,
                    RequirementModel.status.in_(("draft", "confirmed")),
                )
                .order_by(RequirementModel.id)
            )
        ).all()
        return GapSnapshotRevisions(
            project_type=project.project_type,
            context_item_revisions=tuple(
                ContextItemRevision(row.id, row.updated_at) for row in context_rows
            ),
            requirement_revisions=tuple(
                RequirementRevision(row.id, row.updated_at) for row in requirement_rows
            ),
        )

    async def add_batch(self, gaps: tuple[GapWrite, ...]) -> None:
        for gap in gaps:
            self._session.add(
                GapModel(
                    id=gap.id,
                    account_id=gap.account_id,
                    project_id=gap.project_id,
                    context_version=gap.context_version,
                    gap_type=gap.gap_type,
                    severity=gap.severity,
                    status="open",
                    source_refs=[_reference_to_dict(ref) for ref in gap.source_refs],
                    explanation=gap.explanation,
                    suggested_resolution_type=gap.suggested_resolution_type,
                    generation_job_id=gap.generation_job_id,
                )
            )
            self._session.add_all(
                [
                    GapRequirementLinkModel(
                        account_id=gap.account_id,
                        project_id=gap.project_id,
                        gap_id=gap.id,
                        requirement_id=requirement_id,
                    )
                    for requirement_id in gap.affected_requirement_ids
                ]
            )
        await self._session.flush()

    async def mark_job_succeeded(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        gap_count: int,
        finished_at: datetime,
    ) -> None:
        job = await self._session.scalar(
            select(JobModel)
            .where(
                JobModel.id == job_id,
                JobModel.account_id == account_id,
                JobModel.project_id == project_id,
                JobModel.status.in_(("queued", "running")),
            )
            .with_for_update()
        )
        if job is None:
            raise GapDetectionRepositoryError("gap_generation_job_unavailable")
        job.payload_ref = {**(job.payload_ref or {}), "gap_count": gap_count}
        job.status = "succeeded"
        job.finished_at = finished_at
        job.error_code = None
        job.error_detail = None
        await self._session.flush()


class SqlAlchemyGapDetectionUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyGapDetectionRepository | None = None
        self._committed = False

    @property
    def repository(self) -> GapDetectionRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyGapDetectionUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyGapDetectionRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        if self._session is None:
            return
        if not self._committed:
            await self._session.rollback()
        await self._session.close()
        if isinstance(exc, SQLAlchemyError):
            raise GapDetectionRepositoryError("gap_detection_persistence_failed") from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except SQLAlchemyError:
            raise GapDetectionRepositoryError("gap_detection_persistence_failed") from None
        self._committed = True


class SqlAlchemyGapDetectionUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> GapDetectionUnitOfWork:
        return SqlAlchemyGapDetectionUnitOfWork(self._session_factory)


def _context_item_from_model(model: ContextItemModel) -> GapContextItem:
    return GapContextItem(
        id=model.id,
        updated_at=model.updated_at,
        item_type=model.item_type,
        status=cast(Literal["proposed", "confirmed"], model.status),
        content=model.content,
        source_refs=tuple(_reference_from_dict(value) for value in model.source_refs),
    )


def _requirement_from_model(model: RequirementModel) -> GapRequirement:
    return GapRequirement(
        id=model.id,
        updated_at=model.updated_at,
        category=model.category,
        title=model.title,
        description=model.description,
        priority=model.priority,
        status=cast(Literal["draft", "confirmed"], model.status),
        source_refs=tuple(_reference_from_dict(value) for value in model.source_refs),
    )


def _reference_from_dict(value: dict[str, object]) -> GapSourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if set(value) - allowed or "source_id" not in value or "source_version_id" not in value:
        raise GapDetectionRepositoryError("invalid_persisted_source_reference")
    try:
        return GapSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError) as error:
        raise GapDetectionRepositoryError("invalid_persisted_source_reference") from error


def _reference_to_dict(reference: GapSourceReference) -> dict[str, object]:
    value: dict[str, object] = {
        "source_id": str(reference.source_id),
        "source_version_id": str(reference.source_version_id),
    }
    if reference.start_offset is not None:
        value["start_offset"] = reference.start_offset
        value["end_offset"] = reference.end_offset
    return value


async def _validate_snapshot_provenance(
    session: AsyncSession,
    *,
    account_id: UUID,
    project_id: UUID,
    references: tuple[GapSourceReference, ...],
) -> None:
    unique = {reference.identity(): reference for reference in references}
    if not unique:
        return
    version_ids = {reference.source_version_id for reference in unique.values()}
    rows = (
        await session.execute(
            select(
                ContextSourceVersionModel.id,
                ContextSourceVersionModel.source_id,
                ContextSourceVersionModel.canonical_text,
            ).where(
                ContextSourceVersionModel.id.in_(version_ids),
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.parse_status == "ready",
            )
        )
    ).all()
    targets = {(row.id, row.source_id): row.canonical_text for row in rows}
    for reference in unique.values():
        target = (reference.source_version_id, reference.source_id)
        if target not in targets:
            raise GapDetectionRepositoryError("invalid_gap_snapshot_provenance")
        canonical_text = targets[target]
        if reference.end_offset is not None and (
            canonical_text is None or reference.end_offset > len(canonical_text)
        ):
            raise GapDetectionRepositoryError("invalid_gap_snapshot_provenance")
