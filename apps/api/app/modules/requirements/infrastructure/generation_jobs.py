from __future__ import annotations

from types import TracebackType

from aria_backend_application.requirements_generation import (
    RequirementGenerationRepositoryError,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.infrastructure import models as identity_models
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.infrastructure.repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.modules.projects.infrastructure import models as project_models
from app.modules.requirements.application.generation_jobs import (
    RequirementGenerationActiveJobConflict,
    RequirementGenerationJobUnitOfWork,
)

_ACTIVE_JOB_CONSTRAINT = "uq_jobs_active_requirement_generation_revision"

del identity_models
del project_models


class SqlAlchemyRequirementGenerationJobUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._jobs: SqlAlchemyJobRepository | None = None
        self._outbox: SqlAlchemyOutboxRepository | None = None
        self._committed = False

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

    async def __aenter__(self) -> SqlAlchemyRequirementGenerationJobUnitOfWork:
        self._session = self._session_factory()
        self._jobs = SqlAlchemyJobRepository(self._session)
        self._outbox = SqlAlchemyOutboxRepository(self._session)
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
            raise RequirementGenerationActiveJobConflict from None
        if isinstance(exc, SQLAlchemyError):
            raise RequirementGenerationRepositoryError(
                "requirement_generation_schedule_failed"
            ) from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except IntegrityError as error:
            if _ACTIVE_JOB_CONSTRAINT in str(error.orig):
                raise RequirementGenerationActiveJobConflict from None
            raise RequirementGenerationRepositoryError(
                "requirement_generation_schedule_failed"
            ) from None
        except SQLAlchemyError:
            raise RequirementGenerationRepositoryError(
                "requirement_generation_schedule_failed"
            ) from None
        self._committed = True


class SqlAlchemyRequirementGenerationJobUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> RequirementGenerationJobUnitOfWork:
        return SqlAlchemyRequirementGenerationJobUnitOfWork(self._session_factory)
