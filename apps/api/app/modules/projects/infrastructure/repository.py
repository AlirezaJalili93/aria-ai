from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.projects.application.ports import (
    ProjectRepositoryError,
    ProjectUnitOfWork,
)
from app.modules.projects.domain.project import (
    PROJECT_STATUSES,
    PROJECT_TYPES,
    NewProject,
    Project,
    ProjectStatus,
    ProjectType,
    ProjectValidationError,
)
from app.modules.projects.infrastructure.models import ProjectModel


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: NewProject) -> Project:
        model = ProjectModel(
            id=project.id,
            account_id=project.account_id,
            owner_id=project.owner_id,
            title=project.title,
            project_type=project.project_type,
            status=project.status,
            current_context_version=project.current_context_version,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _project_from_model(model)

    async def get(self, *, account_id: UUID, project_id: UUID) -> Project | None:
        statement = select(ProjectModel).where(
            ProjectModel.id == project_id,
            ProjectModel.account_id == account_id,
            ProjectModel.deleted_at.is_(None),
        )
        model = await self._session.scalar(statement)
        return _project_from_model(model) if model is not None else None

    async def get_including_deleted(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None:
        statement = select(ProjectModel).where(
            ProjectModel.id == project_id,
            ProjectModel.account_id == account_id,
        )
        model = await self._session.scalar(statement)
        return _project_from_model(model) if model is not None else None

    async def list_by_account(
        self,
        *,
        account_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[Project, ...]:
        statement = (
            select(ProjectModel)
            .where(
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .order_by(ProjectModel.created_at.desc(), ProjectModel.id)
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.scalars(statement)).all()
        return tuple(_project_from_model(model) for model in models)

    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        title: str | None = None,
        status: ProjectStatus | None = None,
    ) -> Project | None:
        values: dict[str, object] = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        statement = (
            update(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .values(**values)
            .returning(ProjectModel)
        )
        model = await self._session.scalar(statement)
        return _project_from_model(model) if model is not None else None

    async def soft_delete(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None:
        statement = (
            update(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(ProjectModel)
        )
        model = await self._session.scalar(statement)
        return _project_from_model(model) if model is not None else None


class SqlAlchemyProjectUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyProjectRepository | None = None
        self._committed = False

    @property
    def repository(self) -> SqlAlchemyProjectRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyProjectUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyProjectRepository(self._session)
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
            raise ProjectRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyProjectUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ProjectUnitOfWork:
        return SqlAlchemyProjectUnitOfWork(self._session_factory)


def _project_from_model(model: ProjectModel) -> Project:
    if model.project_type not in PROJECT_TYPES or model.status not in PROJECT_STATUSES:
        raise ProjectValidationError("Persisted Project vocabulary is invalid")
    return Project(
        id=model.id,
        account_id=model.account_id,
        owner_id=model.owner_id,
        title=model.title,
        project_type=cast(ProjectType, model.project_type),
        status=cast(ProjectStatus, model.status),
        current_context_version=model.current_context_version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        deleted_at=model.deleted_at,
    )
