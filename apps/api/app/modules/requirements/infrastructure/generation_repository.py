from __future__ import annotations

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
from sqlalchemy import case, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.infrastructure.models import ContextItemModel
from app.modules.jobs.infrastructure.models import JobModel, OutboxEventModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.requirements.infrastructure.models import RequirementModel


class SqlAlchemyRequirementContextSnapshotReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> RequirementContextSnapshot | None:
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
                models = (
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
        except SQLAlchemyError as error:
            raise RequirementGenerationRepositoryError("context_snapshot_failed") from error
        return RequirementContextSnapshot(
            project_type=project_type,
            context_version=context_version,
            items=tuple(_context_item_from_model(model) for model in models),
        )


class SqlAlchemyRequirementGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_generation_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> RequirementGenerationReplay | None:
        job = await self._session.scalar(
            select(JobModel).where(
                JobModel.id == generation_job_id,
                JobModel.account_id == account_id,
                JobModel.project_id == project_id,
                JobModel.status.in_(("succeeded", "failed")),
            )
        )
        if job is None:
            return None
        if job.status == "failed":
            return RequirementGenerationReplay(
                status="failed", requirements=(), error_code=job.error_code
            )
        models = (
            await self._session.scalars(
                select(RequirementModel)
                .where(
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    RequirementModel.generation_job_id == generation_job_id,
                )
                .order_by(RequirementModel.created_at, RequirementModel.id)
            )
        ).all()
        return RequirementGenerationReplay(
            status="succeeded",
            requirements=tuple(_existing_from_model(model) for model in models),
            error_code=None,
        )

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ContextItemRevision, ...] | None:
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
        # The lock is acquired only for the short final transaction. It prevents a
        # phantom insert or state/update race after exact-set comparison.
        await self._session.execute(text("LOCK TABLE context_items IN SHARE MODE"))
        rows = (
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
        return tuple(ContextItemRevision(row.id, row.updated_at) for row in rows)

    async def list_existing_for_merge(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> tuple[ExistingRequirement, ...]:
        models = (
            await self._session.scalars(
                select(RequirementModel)
                .where(
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    RequirementModel.context_version == context_version,
                )
                .order_by(
                    case((RequirementModel.status == "removed", 1), else_=0),
                    RequirementModel.created_at,
                    RequirementModel.id,
                )
                .with_for_update()
            )
        ).all()
        return tuple(_existing_from_model(model) for model in models)

    async def replace_source_refs(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        source_refs: tuple[RequirementSourceReference, ...],
    ) -> None:
        updated_id = await self._session.scalar(
            update(RequirementModel)
            .where(
                RequirementModel.id == requirement_id,
                RequirementModel.account_id == account_id,
                RequirementModel.project_id == project_id,
            )
            .values(source_refs=[_reference_to_dict(reference) for reference in source_refs])
            .returning(RequirementModel.id)
        )
        if updated_id is None:
            raise RequirementGenerationRepositoryError("requirement_merge_target_missing")

    async def add_batch(self, requirements: tuple[RequirementWrite, ...]) -> None:
        self._session.add_all(
            [
                RequirementModel(
                    id=requirement.id,
                    account_id=requirement.account_id,
                    project_id=requirement.project_id,
                    context_version=requirement.context_version,
                    category=requirement.category,
                    title=requirement.title,
                    description=requirement.description,
                    priority=requirement.priority,
                    status=requirement.status,
                    source_refs=[
                        _reference_to_dict(reference)
                        for reference in requirement.source_refs
                    ],
                    confidence=requirement.confidence,
                    is_unsupported=requirement.is_unsupported,
                    duplicate_group_key=requirement.duplicate_group_key,
                    generation_job_id=requirement.generation_job_id,
                    created_by_type=requirement.created_by_type,
                    created_by=requirement.created_by,
                )
                for requirement in requirements
            ]
        )
        await self._session.flush()

    async def add_conflict_events(
        self, events: tuple[RequirementConflictEvent, ...]
    ) -> None:
        self._session.add_all(
            [
                OutboxEventModel(
                    id=event.id,
                    account_id=event.account_id,
                    aggregate_type="project",
                    aggregate_id=event.project_id,
                    event_type="requirement.conflict_detected",
                    payload={
                        "project_id": str(event.project_id),
                        "context_version": event.context_version,
                        "requirement_ids": [
                            str(requirement_id)
                            for requirement_id in event.requirement_ids
                        ],
                    },
                    status="pending",
                    attempt_count=0,
                    available_at=event.occurred_at,
                )
                for event in events
            ]
        )
        await self._session.flush()


class SqlAlchemyRequirementGenerationUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyRequirementGenerationRepository | None = None
        self._committed = False

    @property
    def repository(self) -> RequirementGenerationRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyRequirementGenerationUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyRequirementGenerationRepository(self._session)
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
            raise RequirementGenerationRepositoryError(
                "requirement_generation_persistence_failed"
            ) from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except SQLAlchemyError:
            raise RequirementGenerationRepositoryError(
                "requirement_generation_persistence_failed"
            ) from None
        self._committed = True


class SqlAlchemyRequirementGenerationUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> RequirementGenerationUnitOfWork:
        return SqlAlchemyRequirementGenerationUnitOfWork(self._session_factory)


def _context_item_from_model(model: ContextItemModel) -> RequirementContextItem:
    if model.status not in {"proposed", "confirmed"}:
        raise RequirementGenerationRepositoryError("ineligible_context_item_loaded")
    return RequirementContextItem(
        id=model.id,
        updated_at=model.updated_at,
        item_type=model.item_type,
        status=cast(Literal["proposed", "confirmed"], model.status),
        content=model.content,
        source_refs=tuple(_reference_from_dict(value) for value in model.source_refs),
    )


def _existing_from_model(model: RequirementModel) -> ExistingRequirement:
    return ExistingRequirement(
        id=model.id,
        category=cast(
            Literal[
                "functional",
                "content",
                "visual",
                "technical",
                "constraint",
                "business",
            ],
            model.category,
        ),
        title=model.title,
        description=model.description,
        priority=cast(Literal["must", "should", "could"], model.priority),
        status=cast(
            Literal["draft", "confirmed", "superseded", "removed"], model.status
        ),
        source_refs=tuple(_reference_from_dict(value) for value in model.source_refs),
        confidence=model.confidence,
        is_unsupported=model.is_unsupported,
        duplicate_group_key=model.duplicate_group_key,
        generation_job_id=model.generation_job_id,
    )


def _reference_from_dict(value: dict[str, object]) -> RequirementSourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if set(value) - allowed or "source_id" not in value or "source_version_id" not in value:
        raise RequirementGenerationRepositoryError("invalid_persisted_source_reference")
    try:
        return RequirementSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError) as error:
        raise RequirementGenerationRepositoryError(
            "invalid_persisted_source_reference"
        ) from error


def _reference_to_dict(reference: RequirementSourceReference) -> dict[str, object]:
    value: dict[str, object] = {
        "source_id": str(reference.source_id),
        "source_version_id": str(reference.source_version_id),
    }
    if reference.start_offset is not None:
        value["start_offset"] = reference.start_offset
        value["end_offset"] = reference.end_offset
    return value
