from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

ExecutionAcquisition = Literal["acquired", "already_in_progress", "already_completed"]


class JobExecutionGuard(Protocol):
    """Atomic PostgreSQL-backed boundary selected by a future storage adapter."""

    async def acquire(self, job_id: UUID) -> ExecutionAcquisition: ...

    async def complete(self, job_id: UUID) -> None: ...
