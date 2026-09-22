from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

ExecutionAcquisition = Literal["acquired", "already_in_progress", "already_completed"]


class JobExecutionGuardError(RuntimeError):
    """Provider-neutral execution-guard failure."""


class JobExecutionGuardValidationError(JobExecutionGuardError):
    """The requested Job cannot enter the guarded execution boundary."""


class JobExecutionGuardPersistenceError(JobExecutionGuardError):
    """The durable execution guard could not be evaluated."""


class JobExecutionGuard(Protocol):
    """Atomic PostgreSQL-backed boundary selected by a future storage adapter."""

    async def acquire(self, job_id: UUID) -> ExecutionAcquisition: ...

    async def complete(self, job_id: UUID) -> None: ...

    async def release(self, job_id: UUID) -> None: ...
