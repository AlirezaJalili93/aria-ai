from __future__ import annotations

from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.context.domain.context_source import (
    ContextSource,
    ContextSourceStatus,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
)


class ContextSourceRepositoryError(Exception):
    """A declared Context Source persistence failure."""


class ContextSourceRepository(Protocol):
    async def add_source(self, source: NewContextSource) -> ContextSource: ...

    async def get_source(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSource | None: ...

    async def set_source_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        status: ContextSourceStatus,
    ) -> ContextSource | None: ...

    async def add_version(self, version: NewContextSourceVersion) -> ContextSourceVersion: ...

    async def mark_version_ready(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
        content_hash: str | None,
        canonical_text: str | None,
        storage_ref: str | None,
        metadata: dict[str, object] | None,
    ) -> ContextSourceVersion | None: ...

    async def mark_version_failed(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
    ) -> ContextSourceVersion | None: ...

    async def get_current_ready_version(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSourceVersion | None: ...


class ContextSourceUnitOfWork(Protocol):
    @property
    def repository(self) -> ContextSourceRepository: ...

    async def __aenter__(self) -> ContextSourceUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ContextSourceUnitOfWorkFactory(Protocol):
    def __call__(self) -> ContextSourceUnitOfWork: ...
