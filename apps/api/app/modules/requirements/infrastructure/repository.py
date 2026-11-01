from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.context.infrastructure.models import (
    ContextSourceModel,
    ContextSourceVersionModel,
)
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.requirements.application.ports import (
    RequirementProvenanceTarget,
    RequirementRepository,
    RequirementRepositoryError,
    RequirementUnitOfWork,
)
from app.modules.requirements.application.requirement_crud_ports import (
    RequirementCrudRepository,
    RequirementCrudRepositoryError,
    RequirementCrudUnitOfWork,
)
from app.modules.requirements.domain.requirement import (
    REQUIREMENT_CATEGORIES,
    REQUIREMENT_CREATOR_TYPES,
    REQUIREMENT_PRIORITIES,
    REQUIREMENT_STATUSES,
    NewRequirement,
    Requirement,
    RequirementCategory,
    RequirementCreatorType,
    RequirementPriority,
    RequirementSourceReference,
    RequirementStatus,
    RequirementValidationError,
)
from app.modules.requirements.infrastructure.models import RequirementModel
from app.shared.idempotency import IdempotencyRepository, IdempotencyRepositoryError


class SqlAlchemyRequirementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project_current_context_version(
        self, *, account_id: UUID, project_id: UUID
    ) -> int | None:
        return (
            await self._session.execute(
                select(ProjectModel.current_context_version).where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                ).with_for_update()
            )
        ).scalar_one_or_none()

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> RequirementProvenanceTarget | None:
        row = (
            await self._session.execute(
                select(ContextSourceVersionModel.canonical_text)
                .join(
                    ContextSourceModel,
                    (ContextSourceModel.id == ContextSourceVersionModel.source_id)
                    & (ContextSourceModel.account_id == ContextSourceVersionModel.account_id)
                    & (ContextSourceModel.project_id == ContextSourceVersionModel.project_id),
                )
                .where(
                    ContextSourceVersionModel.id == source_version_id,
                    ContextSourceVersionModel.source_id == source_id,
                    ContextSourceVersionModel.account_id == account_id,
                    ContextSourceVersionModel.project_id == project_id,
                    ContextSourceVersionModel.parse_status == "ready",
                    ContextSourceModel.id == source_id,
                    ContextSourceModel.account_id == account_id,
                    ContextSourceModel.project_id == project_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        canonical_text = cast(str | None, row[0])
        return RequirementProvenanceTarget(
            account_id=account_id,
            project_id=project_id,
            source_id=source_id,
            source_version_id=source_version_id,
            canonical_text_length=len(canonical_text) if canonical_text is not None else None,
        )

    async def add(self, requirement: NewRequirement) -> Requirement:
        model = RequirementModel(
            id=requirement.id,
            account_id=requirement.account_id,
            project_id=requirement.project_id,
            context_version=requirement.context_version,
            category=requirement.category,
            title=requirement.title,
            description=requirement.description,
            priority=requirement.priority,
            status=requirement.status,
            source_refs=[reference.to_dict() for reference in requirement.source_refs],
            confidence=requirement.confidence,
            is_unsupported=requirement.is_unsupported,
            duplicate_group_key=requirement.duplicate_group_key,
            generation_job_id=requirement.generation_job_id,
            acceptance_note=requirement.acceptance_note,
            created_by_type=requirement.created_by_type,
            created_by=requirement.created_by,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _requirement_from_model(model)

    async def get_by_id(
        self, *, account_id: UUID, project_id: UUID, requirement_id: UUID
    ) -> Requirement | None:
        model = (
            await self._session.scalars(
                select(RequirementModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == RequirementModel.project_id)
                    & (ProjectModel.account_id == RequirementModel.account_id),
                )
                .where(
                    RequirementModel.id == requirement_id,
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        return _requirement_from_model(model) if model is not None else None

    async def list_by_project(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        category: RequirementCategory | None,
        status: RequirementStatus | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Requirement, ...] | None:
        project_exists = (
            await self._session.scalar(
                select(ProjectModel.id).where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        )
        if project_exists is None:
            return None

        statement = select(RequirementModel).where(
            RequirementModel.account_id == account_id,
            RequirementModel.project_id == project_id,
        )
        if category is not None:
            statement = statement.where(RequirementModel.category == category)
        if status is None:
            statement = statement.where(
                RequirementModel.status.not_in(("removed", "superseded"))
            )
        else:
            statement = statement.where(RequirementModel.status == status)
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    RequirementModel.created_at < cursor_created_at,
                    (RequirementModel.created_at == cursor_created_at)
                    & (RequirementModel.id < cursor_id),
                )
            )
        models = (
            await self._session.scalars(
                statement.order_by(
                    RequirementModel.created_at.desc(), RequirementModel.id.desc()
                ).limit(limit)
            )
        ).all()
        return tuple(_requirement_from_model(model) for model in models)

    async def get_for_update(
        self, *, account_id: UUID, project_id: UUID, requirement_id: UUID
    ) -> Requirement | None:
        model = (
            await self._session.scalars(
                select(RequirementModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == RequirementModel.project_id)
                    & (ProjectModel.account_id == RequirementModel.account_id),
                )
                .where(
                    RequirementModel.id == requirement_id,
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update(of=RequirementModel)
            )
        ).one_or_none()
        return _requirement_from_model(model) if model is not None else None

    async def update_mutable(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        requirement_id: UUID,
        expected_updated_at: datetime,
        title: str,
        description: str,
        priority: RequirementPriority,
        acceptance_note: str | None,
        status: RequirementStatus,
    ) -> Requirement | None:
        model = (
            await self._session.scalars(
                update(RequirementModel)
                .where(
                    RequirementModel.id == requirement_id,
                    RequirementModel.account_id == account_id,
                    RequirementModel.project_id == project_id,
                    RequirementModel.updated_at == expected_updated_at,
                    RequirementModel.status.not_in(("removed", "superseded")),
                )
                .values(
                    title=title,
                    description=description,
                    priority=priority,
                    acceptance_note=acceptance_note,
                    status=status,
                )
                .returning(RequirementModel)
            )
        ).one_or_none()
        return _requirement_from_model(model) if model is not None else None


class SqlAlchemyRequirementUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyRequirementRepository | None = None
        self._committed = False

    @property
    def repository(self) -> RequirementRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyRequirementUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyRequirementRepository(self._session)
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
            raise RequirementRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyRequirementUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> RequirementUnitOfWork:
        return SqlAlchemyRequirementUnitOfWork(self._session_factory)


class SqlAlchemyRequirementCrudUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyRequirementRepository | None = None
        self._idempotency: SqlAlchemyIdempotencyRepository | None = None
        self._committed = False

    @property
    def repository(self) -> RequirementCrudRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    @property
    def idempotency(self) -> IdempotencyRepository:
        if self._idempotency is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._idempotency

    async def __aenter__(self) -> SqlAlchemyRequirementCrudUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyRequirementRepository(self._session)
        self._idempotency = SqlAlchemyIdempotencyRepository(self._session)
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
        if isinstance(exc, (SQLAlchemyError, IdempotencyRepositoryError)):
            raise RequirementCrudRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyRequirementCrudUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> RequirementCrudUnitOfWork:
        return SqlAlchemyRequirementCrudUnitOfWork(self._session_factory)


def _requirement_from_model(model: RequirementModel) -> Requirement:
    if (
        model.category not in REQUIREMENT_CATEGORIES
        or model.priority not in REQUIREMENT_PRIORITIES
        or model.status not in REQUIREMENT_STATUSES
        or model.created_by_type not in REQUIREMENT_CREATOR_TYPES
    ):
        raise RequirementValidationError("Persisted Requirement vocabulary is invalid")
    return Requirement(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        category=cast(RequirementCategory, model.category),
        title=model.title,
        description=model.description,
        priority=cast(RequirementPriority, model.priority),
        status=cast(RequirementStatus, model.status),
        source_refs=tuple(_source_reference_from_dict(value) for value in model.source_refs),
        confidence=model.confidence,
        is_unsupported=model.is_unsupported,
        duplicate_group_key=model.duplicate_group_key,
        generation_job_id=model.generation_job_id,
        acceptance_note=model.acceptance_note,
        created_by_type=cast(RequirementCreatorType, model.created_by_type),
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _source_reference_from_dict(value: dict[str, object]) -> RequirementSourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if set(value) - allowed or "source_id" not in value or "source_version_id" not in value:
        raise RequirementValidationError("Persisted Source Reference shape is invalid")
    try:
        return RequirementSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError) as error:
        raise RequirementValidationError("Persisted Source Reference shape is invalid") from error
