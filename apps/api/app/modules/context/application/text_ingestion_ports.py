from __future__ import annotations

from types import TracebackType
from typing import Protocol

from app.modules.context.application.ports import ContextSourceRepository
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.projects.application.ports import ProjectRepository
from app.shared.idempotency import IdempotencyRepository


class TextContextIngestionRepositoryError(Exception):
    """A declared Text Context transaction persistence failure."""


class TextContextIngestionUnitOfWork(Protocol):
    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def context_sources(self) -> ContextSourceRepository: ...

    @property
    def jobs(self) -> JobRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    @property
    def idempotency(self) -> IdempotencyRepository: ...

    async def __aenter__(self) -> TextContextIngestionUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class TextContextIngestionUnitOfWorkFactory(Protocol):
    def __call__(self) -> TextContextIngestionUnitOfWork: ...
