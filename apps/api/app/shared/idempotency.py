from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class IdempotencyRepositoryError(Exception):
    """The generic idempotency store is internally inconsistent or unavailable."""


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    acquired: bool
    request_hash: str
    response_status: int | None
    response_ref: dict[str, object] | None


class IdempotencyRepository(Protocol):
    async def reserve(
        self,
        *,
        record_id: UUID,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        now: datetime,
        expires_at: datetime,
    ) -> IdempotencyReservation: ...

    async def complete(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        route_key: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_ref: dict[str, object],
    ) -> None: ...
