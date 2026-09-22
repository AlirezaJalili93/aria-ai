from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.application.context_source_management import (
    ContextSourceJobSummary,
    ContextSourceManagementRepository,
    ContextSourceManagementRepositoryError,
    ContextSourceManagementUnitOfWork,
    ContextSourceVersionSummary,
    ContextSourceView,
    parser_job_retryable,
)
from app.modules.context.infrastructure.models import ContextSourceModel, ContextSourceVersionModel
from app.modules.jobs.domain.job import JOB_STATUSES, JobStatus
from app.modules.jobs.infrastructure.models import JobModel
from app.modules.projects.infrastructure.models import ProjectModel


class SqlAlchemyContextSourceManagementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def project_exists(self, *, account_id: UUID, project_id: UUID) -> bool:
        value = await self._session.scalar(
            select(
                exists().where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        )
        return bool(value)

    async def list_sources(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[ContextSourceView, ...]:
        filters = [
            ContextSourceModel.account_id == account_id,
            ContextSourceModel.project_id == project_id,
            ContextSourceModel.status != "deleted",
        ]
        if cursor_created_at is not None and cursor_id is not None:
            filters.append(
                or_(
                    ContextSourceModel.created_at < cursor_created_at,
                    and_(
                        ContextSourceModel.created_at == cursor_created_at,
                        ContextSourceModel.id < cursor_id,
                    ),
                )
            )
        sources = (
            await self._session.scalars(
                select(ContextSourceModel)
                .where(*filters)
                .order_by(ContextSourceModel.created_at.desc(), ContextSourceModel.id.desc())
                .limit(limit)
            )
        ).all()
        return await self._views(sources)

    async def get_source(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        include_deleted: bool = False,
    ) -> ContextSourceView | None:
        filters = [
            ContextSourceModel.id == source_id,
            ContextSourceModel.account_id == account_id,
            ContextSourceModel.project_id == project_id,
        ]
        if not include_deleted:
            filters.append(ContextSourceModel.status != "deleted")
        source = await self._session.scalar(select(ContextSourceModel).where(*filters))
        if source is None:
            return None
        return (await self._views((source,)))[0]

    async def has_active_parser_job(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> bool:
        value = await self._session.scalar(
            select(
                exists().where(
                    JobModel.account_id == account_id,
                    JobModel.project_id == project_id,
                    JobModel.job_type == "context_source_parse",
                    JobModel.status.in_(("queued", "running")),
                    JobModel.payload_ref["source_id"].astext == str(source_id),
                )
            )
        )
        return bool(value)

    async def archive_source(self, *, account_id: UUID, project_id: UUID, source_id: UUID) -> bool:
        value = await self._session.scalar(
            update(ContextSourceModel)
            .where(
                ContextSourceModel.id == source_id,
                ContextSourceModel.account_id == account_id,
                ContextSourceModel.project_id == project_id,
                ContextSourceModel.status != "deleted",
            )
            .values(status="deleted", updated_at=func.now())
            .returning(ContextSourceModel.id)
        )
        return value is not None

    async def _views(self, sources: Iterable[ContextSourceModel]) -> tuple[ContextSourceView, ...]:
        source_rows = tuple(sources)
        if not source_rows:
            return ()
        source_ids = [source.id for source in source_rows]
        versions = (
            await self._session.scalars(
                select(ContextSourceVersionModel)
                .where(ContextSourceVersionModel.source_id.in_(source_ids))
                .order_by(
                    ContextSourceVersionModel.source_id,
                    ContextSourceVersionModel.version_no.desc(),
                )
            )
        ).all()
        latest: dict[UUID, ContextSourceVersionModel] = {}
        ready: dict[UUID, ContextSourceVersionModel] = {}
        for version in versions:
            latest.setdefault(version.source_id, version)
            if version.parse_status == "ready":
                ready.setdefault(version.source_id, version)
        version_ids = [version.id for version in latest.values()]
        jobs = (
            await self._session.scalars(
                select(JobModel)
                .where(
                    JobModel.account_id == source_rows[0].account_id,
                    JobModel.project_id == source_rows[0].project_id,
                    JobModel.job_type == "context_source_parse",
                    JobModel.payload_ref["source_version_id"].astext.in_(
                        [str(value) for value in version_ids]
                    ),
                )
                .order_by(JobModel.created_at.desc(), JobModel.id.desc())
            )
        ).all()
        jobs_by_version: dict[str, JobModel] = {}
        for job in jobs:
            payload = job.payload_ref or {}
            source_version_id = payload.get("source_version_id")
            if isinstance(source_version_id, str):
                jobs_by_version.setdefault(source_version_id, job)
        return tuple(
            _view(
                source,
                latest.get(source.id),
                ready.get(source.id),
                jobs_by_version,
            )
            for source in source_rows
        )


class SqlAlchemyContextSourceManagementUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyContextSourceManagementRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ContextSourceManagementRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyContextSourceManagementUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyContextSourceManagementRepository(self._session)
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
            raise ContextSourceManagementRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyContextSourceManagementUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ContextSourceManagementUnitOfWork:
        return SqlAlchemyContextSourceManagementUnitOfWork(self._session_factory)


def _version_summary(
    version: ContextSourceVersionModel | None,
) -> ContextSourceVersionSummary | None:
    if version is None:
        return None
    return ContextSourceVersionSummary(
        id=version.id,
        version_no=version.version_no,
        parse_status=version.parse_status,
        created_at=version.created_at,
    )


def _view(
    source: ContextSourceModel,
    latest: ContextSourceVersionModel | None,
    ready: ContextSourceVersionModel | None,
    jobs_by_version: dict[str, JobModel],
) -> ContextSourceView:
    job = jobs_by_version.get(str(latest.id)) if latest is not None else None
    job_summary = None
    if job is not None:
        if job.status not in JOB_STATUSES:
            raise ContextSourceManagementRepositoryError
        job_summary = ContextSourceJobSummary(
            id=job.id,
            status=cast(JobStatus, job.status),
            retryable=parser_job_retryable(status=job.status, error_code=job.error_code),
            error_code=job.error_code,
            created_at=job.created_at,
        )
    return ContextSourceView(
        id=source.id,
        source_type=source.source_type,
        status=source.status,
        original_name=source.original_name,
        mime_type=source.mime_type,
        created_at=source.created_at,
        updated_at=source.updated_at,
        created_by=source.created_by,
        latest_version=_version_summary(latest),
        current_ready_version=_version_summary(ready),
        latest_job=job_summary,
    )
