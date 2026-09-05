from __future__ import annotations

from types import TracebackType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.context.application.ports import ContextSourceRepository
from app.modules.context.application.text_ingestion_ports import (
    TextContextIngestionRepositoryError,
    TextContextIngestionUnitOfWork,
)
from app.modules.context.infrastructure.repository import SqlAlchemyContextSourceRepository
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.infrastructure.repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.modules.projects.application.ports import ProjectRepository
from app.modules.projects.infrastructure.repository import SqlAlchemyProjectRepository
from app.shared.idempotency import IdempotencyRepository, IdempotencyRepositoryError


class SqlAlchemyTextContextIngestionUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: SqlAlchemyProjectRepository | None = None
        self._context_sources: SqlAlchemyContextSourceRepository | None = None
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
    def context_sources(self) -> ContextSourceRepository:
        if self._context_sources is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._context_sources

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

    async def __aenter__(self) -> SqlAlchemyTextContextIngestionUnitOfWork:
        self._session = self._session_factory()
        self._projects = SqlAlchemyProjectRepository(self._session)
        self._context_sources = SqlAlchemyContextSourceRepository(self._session)
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
        if isinstance(exc, (SQLAlchemyError, IdempotencyRepositoryError)):
            raise TextContextIngestionRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyTextContextIngestionUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> TextContextIngestionUnitOfWork:
        return SqlAlchemyTextContextIngestionUnitOfWork(self._session_factory)
