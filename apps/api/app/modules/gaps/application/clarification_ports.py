from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationResolution,
    ClarificationStatus,
    NewClarification,
    NewClarificationResolution,
)
from app.modules.gaps.domain.gap import Gap, GapSeverity, GapStatus, GapType
from app.shared.idempotency import IdempotencyRepository


class ClarificationRepositoryError(Exception):
    """A declared Clarification persistence failure."""


class DuplicateClarificationRepositoryError(Exception):
    """The same normalized open question already exists for the Gap."""


@dataclass(frozen=True, slots=True)
class ClarificationHistoryEntry:
    question: Clarification
    resolution: ClarificationResolution | None


class ClarificationRepository(Protocol):
    async def list_current_gaps(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        status: GapStatus | None,
        severity: GapSeverity | None,
        gap_type: GapType | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> tuple[Gap, ...] | None: ...

    async def list_clarification_history(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
    ) -> tuple[ClarificationHistoryEntry, ...] | None: ...

    async def get_gap_for_update(
        self, *, account_id: UUID, project_id: UUID, gap_id: UUID
    ) -> Gap | None: ...

    async def add_question(self, question: NewClarification) -> Clarification: ...

    async def get_question_by_id(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
    ) -> Clarification | None: ...

    async def get_question_for_update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
    ) -> Clarification | None: ...

    async def update_question_text(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        expected_updated_at: datetime,
        question_text: str,
    ) -> Clarification | None: ...

    async def set_question_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        status: ClarificationStatus,
    ) -> Clarification: ...

    async def add_resolution(
        self, resolution: NewClarificationResolution
    ) -> ClarificationResolution: ...

    async def get_resolution_by_id(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        resolution_id: UUID,
    ) -> ClarificationResolution | None: ...

    async def has_open_questions(
        self, *, account_id: UUID, project_id: UUID, gap_id: UUID
    ) -> bool: ...

    async def set_gap_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        expected_updated_at: datetime,
        status: GapStatus,
        resolved_at: datetime | None,
    ) -> Gap | None: ...


class ClarificationUnitOfWork(Protocol):
    @property
    def repository(self) -> ClarificationRepository: ...

    @property
    def idempotency(self) -> IdempotencyRepository: ...

    async def __aenter__(self) -> ClarificationUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ClarificationUnitOfWorkFactory(Protocol):
    def __call__(self) -> ClarificationUnitOfWork: ...
