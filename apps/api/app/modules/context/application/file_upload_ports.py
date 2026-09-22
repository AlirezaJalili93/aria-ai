from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Literal, Protocol
from uuid import UUID

from app.modules.context.application.ports import ContextSourceRepository
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.projects.application.ports import ProjectRepository

UploadAllocationStatus = Literal[
    "allocated",
    "uploading",
    "committed",
    "recovery_required",
]


class ObjectStorageError(Exception):
    """A provider-neutral object storage operation failed."""

    def __init__(
        self,
        *,
        retryable: bool,
        reason_code: str,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__("Object storage operation failed")
        self.retryable = retryable
        self.reason_code = reason_code
        self.outcome_unknown = outcome_unknown


class ObjectStoragePort(Protocol):
    async def put_private(self, *, object_key: str, content: bytes, mime_type: str) -> None: ...

    async def delete(self, *, object_key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class NewFileUploadAllocation:
    id: UUID
    account_id: UUID
    actor_id: UUID
    project_id: UUID
    idempotency_key: str
    request_hash: str
    source_id: UUID
    source_version_id: UUID
    job_id: UUID
    object_key: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FileUploadAllocation:
    id: UUID
    account_id: UUID
    actor_id: UUID
    project_id: UUID
    idempotency_key: str
    request_hash: str
    source_id: UUID
    source_version_id: UUID
    job_id: UUID
    object_key: str
    status: UploadAllocationStatus
    response_status: int | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class FileUploadAllocationRepository(Protocol):
    async def allocate_or_get(
        self,
        allocation: NewFileUploadAllocation,
        *,
        now: datetime,
    ) -> FileUploadAllocation: ...

    async def get(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
    ) -> FileUploadAllocation | None: ...

    async def transition(
        self,
        *,
        allocation_id: UUID,
        expected_status: UploadAllocationStatus,
        status: UploadAllocationStatus,
        now: datetime,
        response_status: int | None = None,
    ) -> bool: ...


class FileUploadUnitOfWork(Protocol):
    @property
    def projects(self) -> ProjectRepository: ...

    @property
    def context_sources(self) -> ContextSourceRepository: ...

    @property
    def jobs(self) -> JobRepository: ...

    @property
    def outbox(self) -> OutboxRepository: ...

    @property
    def upload_allocations(self) -> FileUploadAllocationRepository: ...

    async def __aenter__(self) -> FileUploadUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class FileUploadUnitOfWorkFactory(Protocol):
    def __call__(self) -> FileUploadUnitOfWork: ...
