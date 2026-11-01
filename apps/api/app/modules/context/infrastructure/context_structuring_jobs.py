from __future__ import annotations

from types import TracebackType
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.context.application.context_structuring_job_ports import (
    ContextStructuringActiveJobConflict,
    ContextStructuringJobRepositoryError,
    ContextStructuringReadinessRepository,
)
from app.modules.context.infrastructure.models import (
    ContextSourceModel,
    ContextSourceVersionModel,
)
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.infrastructure.repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.modules.projects.application.ports import ProjectRepository
from app.modules.projects.infrastructure.repository import SqlAlchemyProjectRepository
from app.shared.idempotency import IdempotencyRepository, IdempotencyRepositoryError

_ACTIVE_JOB_CONSTRAINT = "uq_jobs_active_context_structuring_project"


class SqlAlchemyContextStructuringReadinessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_ready_source(self, *, account_id: UUID, project_id: UUID) -> bool:
        source_version_id = await self._session.scalar(
            select(ContextSourceVersionModel.id)
            .join(
                ContextSourceModel,
                (ContextSourceModel.id == ContextSourceVersionModel.source_id)
                & (ContextSourceModel.account_id == ContextSourceVersionModel.account_id)
                & (ContextSourceModel.project_id == ContextSourceVersionModel.project_id),
            )
            .where(
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.parse_status == "ready",
                ContextSourceModel.status != "deleted",
            )
            .limit(1)
        )
        return source_version_id is not None


class SqlAlchemyContextStructuringJobUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: SqlAlchemyProjectRepository | None = None
        self._readiness: SqlAlchemyContextStructuringReadinessRepository | None = None
        self._jobs: SqlAlchemyJobRepository | None = None
        self._outbox: SqlAlchemyOutboxRepository | None = None
        self._idempotency: SqlAlchemyIdempotencyRepository | None = None
        self._committed = False

    @property
    def projects(self) -> ProjectRepository:
        if self._projects is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._projects

    @property
    def readiness(self) -> ContextStructuringReadinessRepository:
        if self._readiness is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._readiness

    @property
    def jobs(self) -> JobRepository:
        if self._jobs is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._jobs

    @property
    def outbox(self) -> OutboxRepository:
        if self._outbox is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._outbox

    @property
    def idempotency(self) -> IdempotencyRepository:
        if self._idempotency is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._idempotency

    async def __aenter__(self) -> SqlAlchemyContextStructuringJobUnitOfWork:
        self._session = self._session_factory()
        self._projects = SqlAlchemyProjectRepository(self._session)
        self._readiness = SqlAlchemyContextStructuringReadinessRepository(self._session)
        self._jobs = SqlAlchemyJobRepository(self._session)
        self._outbox = SqlAlchemyOutboxRepository(self._session)
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
        if isinstance(exc, IntegrityError) and _ACTIVE_JOB_CONSTRAINT in str(exc.orig):
            raise ContextStructuringActiveJobConflict from None
        if isinstance(exc, (SQLAlchemyError, IdempotencyRepositoryError)):
            raise ContextStructuringJobRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyContextStructuringJobUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyContextStructuringJobUnitOfWork:
        return SqlAlchemyContextStructuringJobUnitOfWork(self._session_factory)
