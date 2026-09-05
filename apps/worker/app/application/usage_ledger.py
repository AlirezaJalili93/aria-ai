from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

UsageStatus = Literal["success", "failed", "partial"]


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Provider-neutral append input for the authoritative AI Usage Ledger."""

    account_id: UUID
    project_id: UUID | None
    job_id: UUID | None
    task_type: str
    workflow_version: str
    prompt_version: str
    provider: str
    model: str
    provider_request_id: str | None
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: Decimal
    status: UsageStatus
    error_code: str | None
    retry_no: int
    estimated_cost: Decimal
    pricing_version: str
    correlation_id: UUID
    currency: str = "USD"


class UsageLedgerError(RuntimeError):
    """Declared persistence failure at the Usage Ledger boundary."""


class UsageLedger(Protocol):
    """Append-only Application port; raw reads and mutations are not exposed."""

    async def append(self, record: UsageRecord) -> None: ...

