from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent


class JobsRepositoryError(Exception):
    """A declared Jobs/Outbox persistence failure."""


class JobRepository(Protocol):
    async def add(self, job: NewJob) -> Job: ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def get_for_account(self, account_id: UUID, job_id: UUID) -> Job | None: ...


class OutboxRepository(Protocol):
    async def add(self, event: NewOutboxEvent) -> OutboxEvent: ...

    async def get(self, event_id: UUID) -> OutboxEvent | None: ...

    async def mark_published(self, event_id: UUID, published_at: datetime) -> None: ...


class QueuePublisher(Protocol):
    """Provider-neutral publication boundary for a committed Outbox event."""

    async def publish(self, event: OutboxEvent) -> None: ...


class JobsUnitOfWork(Protocol):
    @property
    def jobs(self) -> JobRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    async def __aenter__(self) -> JobsUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class JobsUnitOfWorkFactory(Protocol):
    def __call__(self) -> JobsUnitOfWork: ...
