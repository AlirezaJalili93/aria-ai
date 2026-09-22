from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.gaps.domain.gap import Gap, NewGap


class GapRepositoryError(Exception):
    """A declared Gap persistence failure."""


@dataclass(frozen=True, slots=True)
class GapProvenanceTarget:
    account_id: UUID
    project_id: UUID
    source_id: UUID
    source_version_id: UUID
    canonical_text_length: int | None


class GapRepository(Protocol):
    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> GapProvenanceTarget | None: ...

    async def add(self, gap: NewGap) -> Gap: ...


class GapUnitOfWork(Protocol):
    @property
    def repository(self) -> GapRepository: ...

    async def __aenter__(self) -> GapUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class GapUnitOfWorkFactory(Protocol):
    def __call__(self) -> GapUnitOfWork: ...
