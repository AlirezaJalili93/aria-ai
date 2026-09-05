from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.jobs.application.ports import (
    JobRepository,
    JobsRepositoryError,
    JobsUnitOfWork,
    OutboxRepository,
)
from app.modules.jobs.domain.job import (
    JOB_STATUSES,
    OUTBOX_STATUSES,
    Job,
    JobStatus,
    JobValidationError,
    NewJob,
    NewOutboxEvent,
    OutboxEvent,
    OutboxStatus,
)
from app.modules.jobs.infrastructure.models import JobModel, OutboxEventModel


class SqlAlchemyJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: NewJob) -> Job:
        model = JobModel(
            id=job.id,
            account_id=job.account_id,
            project_id=job.project_id,
            job_type=job.job_type,
            status=job.status,
            payload_ref=job.payload_ref,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            idempotency_key=job.idempotency_key,
            correlation_id=job.correlation_id,
            available_at=job.available_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _job_from_model(model)

    async def get(self, job_id: UUID) -> Job | None:
        model = await self._session.scalar(select(JobModel).where(JobModel.id == job_id))
        return _job_from_model(model) if model is not None else None

    async def get_for_account(self, account_id: UUID, job_id: UUID) -> Job | None:
        model = await self._session.scalar(
            select(JobModel).where(
                JobModel.id == job_id,
                JobModel.account_id == account_id,
            )
        )
        return _job_from_model(model) if model is not None else None


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: NewOutboxEvent) -> OutboxEvent:
        model = OutboxEventModel(
            id=event.id,
            account_id=event.account_id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=event.payload,
            status=event.status,
            attempt_count=event.attempt_count,
            available_at=event.available_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _outbox_from_model(model)

    async def get(self, event_id: UUID) -> OutboxEvent | None:
        model = await self._session.scalar(
            select(OutboxEventModel).where(OutboxEventModel.id == event_id)
        )
        return _outbox_from_model(model) if model is not None else None

    async def mark_published(self, event_id: UUID, published_at: datetime) -> None:
        model = await self._session.scalar(
            select(OutboxEventModel).where(OutboxEventModel.id == event_id)
        )
        if model is None:
            raise JobsRepositoryError from None
        model.status = "published"
        model.published_at = published_at
        await self._session.flush()


class SqlAlchemyJobsUnitOfWork:
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

    async def __aenter__(self) -> SqlAlchemyJobsUnitOfWork:
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
        if isinstance(exc, SQLAlchemyError):
            raise JobsRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyJobsUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> JobsUnitOfWork:
        return SqlAlchemyJobsUnitOfWork(self._session_factory)


def _job_from_model(model: JobModel) -> Job:
    if model.status not in JOB_STATUSES:
        raise JobValidationError("Persisted Job status is invalid")
    return Job(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        job_type=model.job_type,
        status=cast(JobStatus, model.status),
        payload_ref=model.payload_ref,
        attempt_count=model.attempt_count,
        max_attempts=model.max_attempts,
        idempotency_key=model.idempotency_key,
        correlation_id=model.correlation_id,
        available_at=model.available_at,
        started_at=model.started_at,
        finished_at=model.finished_at,
        error_code=model.error_code,
        error_detail=model.error_detail,
        created_at=model.created_at,
    )


def _outbox_from_model(model: OutboxEventModel) -> OutboxEvent:
    if model.status not in OUTBOX_STATUSES:
        raise JobValidationError("Persisted Outbox status is invalid")
    return OutboxEvent(
        id=model.id,
        account_id=model.account_id,
        aggregate_type=model.aggregate_type,
        aggregate_id=model.aggregate_id,
        event_type=model.event_type,
        payload=model.payload,
        status=cast(OutboxStatus, model.status),
        attempt_count=model.attempt_count,
        available_at=model.available_at,
        created_at=model.created_at,
        published_at=model.published_at,
    )
