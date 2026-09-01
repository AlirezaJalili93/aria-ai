from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.projects.application.ports import (
    ProjectCreateReservation,
    ProjectRepository,
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
from app.modules.projects.infrastructure.models import ProjectCreateRequestModel, ProjectModel


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve_create(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        idempotency_key: str,
        payload_hash: str,
        project_id: UUID,
    ) -> ProjectCreateReservation:
        reserved_project_id = await self._session.scalar(
            insert(ProjectCreateRequestModel)
            .values(
                account_id=account_id,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
                payload_hash=payload_hash,
                project_id=project_id,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "idempotency_key"]
            )
            .returning(ProjectCreateRequestModel.project_id)
        )
        if reserved_project_id is not None:
            return ProjectCreateReservation(True, payload_hash, reserved_project_id, None)

        existing = await self._session.scalar(
            select(ProjectCreateRequestModel).where(
                ProjectCreateRequestModel.account_id == account_id,
                ProjectCreateRequestModel.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise ProjectRepositoryError
        snapshot = (
            _project_from_snapshot(existing.response_snapshot)
            if existing.response_snapshot is not None
            else None
        )
        return ProjectCreateReservation(
            False, existing.payload_hash, existing.project_id, snapshot
        )

    async def complete_create_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        idempotency_key: str,
        project: Project,
    ) -> None:
        completed_id = await self._session.scalar(
            update(ProjectCreateRequestModel)
            .where(
                ProjectCreateRequestModel.account_id == account_id,
                ProjectCreateRequestModel.idempotency_key == idempotency_key,
                ProjectCreateRequestModel.project_id == project.id,
            )
            .values(response_snapshot=_project_snapshot(project))
            .returning(ProjectCreateRequestModel.project_id)
        )
        if completed_id is None:
            raise ProjectRepositoryError

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
        model = await self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        return _project_from_model(model) if model is not None else None

    async def get_including_deleted(
        self, *, account_id: UUID, project_id: UUID
    ) -> Project | None:
        model = await self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
            )
        )
        return _project_from_model(model) if model is not None else None

    async def list_by_account(
        self,
        *,
        account_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Project, ...]:
        filters = [
            ProjectModel.account_id == account_id,
            ProjectModel.deleted_at.is_(None),
        ]
        if cursor_created_at is not None and cursor_id is not None:
            filters.append(
                or_(
                    ProjectModel.created_at < cursor_created_at,
                    and_(
                        ProjectModel.created_at == cursor_created_at,
                        ProjectModel.id < cursor_id,
                    ),
                )
            )
        models = (
            await self._session.scalars(
                select(ProjectModel)
                .where(*filters)
                .order_by(ProjectModel.created_at.desc(), ProjectModel.id.desc())
                .limit(limit)
            )
        ).all()
        return tuple(_project_from_model(model) for model in models)

    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        title: str | None = None,
        status: ProjectStatus | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Project | None:
        values: dict[str, object] = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        filters = [
            ProjectModel.id == project_id,
            ProjectModel.account_id == account_id,
            ProjectModel.deleted_at.is_(None),
        ]
        if expected_updated_at is not None:
            filters.append(ProjectModel.updated_at == expected_updated_at)
        model = await self._session.scalar(
            update(ProjectModel).where(*filters).values(**values).returning(ProjectModel)
        )
        return _project_from_model(model) if model is not None else None

    async def soft_delete(self, *, account_id: UUID, project_id: UUID) -> Project | None:
        model = await self._session.scalar(
            update(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(ProjectModel)
        )
        return _project_from_model(model) if model is not None else None


class SqlAlchemyProjectUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyProjectRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ProjectRepository:
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


def _project_snapshot(project: Project) -> dict[str, object]:
    return {
        "id": str(project.id),
        "account_id": str(project.account_id),
        "owner_id": str(project.owner_id),
        "title": project.title,
        "project_type": project.project_type,
        "status": project.status,
        "current_context_version": project.current_context_version,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _project_from_snapshot(snapshot: dict[str, object]) -> Project:
    try:
        return Project(
            id=UUID(str(snapshot["id"])),
            account_id=UUID(str(snapshot["account_id"])),
            owner_id=UUID(str(snapshot["owner_id"])),
            title=str(snapshot["title"]),
            project_type=cast(ProjectType, snapshot["project_type"]),
            status=cast(ProjectStatus, snapshot["status"]),
            current_context_version=int(str(snapshot["current_context_version"])),
            created_at=datetime.fromisoformat(str(snapshot["created_at"])),
            updated_at=datetime.fromisoformat(str(snapshot["updated_at"])),
            deleted_at=None,
        )
    except (KeyError, TypeError, ValueError, ProjectValidationError):
        raise ProjectRepositoryError from None
