from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

UsageStatus = Literal["success", "failed", "partial"]
AccountingStatus = Literal["complete", "unavailable"]


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """Provider-neutral append input for the authoritative AI Usage Ledger."""

    account_id: UUID
    provider_attempt_id: UUID
    project_id: UUID | None
    job_id: UUID | None
    task_type: str
    workflow_version: str
    prompt_version: str
    provider: str
    model: str
    provider_request_id: str | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    latency_ms: Decimal
    status: UsageStatus
    error_code: str | None
    retry_no: int
    repair_no: int
    estimated_cost: Decimal | None
    pricing_version: str
    correlation_id: UUID
    accounting_status: AccountingStatus = "complete"
    currency: str = "USD"

    def __post_init__(self) -> None:
        token_values = (
            self.input_tokens,
            self.cached_input_tokens,
            self.output_tokens,
        )
        if self.accounting_status == "complete":
            if any(value is None for value in (*token_values, self.estimated_cost)):
                raise ValueError("complete_accounting_requires_usage")
            input_tokens, cached_input_tokens, output_tokens = token_values
            assert input_tokens is not None
            assert cached_input_tokens is not None
            assert output_tokens is not None
            assert self.estimated_cost is not None
            if (
                input_tokens < 0
                or cached_input_tokens < 0
                or output_tokens < 0
                or cached_input_tokens > input_tokens
                or self.estimated_cost < 0
            ):
                raise ValueError("invalid_token_accounting")
        elif self.accounting_status == "unavailable":
            if self.status != "failed" or any(value is not None for value in token_values):
                raise ValueError("unavailable_accounting_requires_failed_null_usage")
            if self.estimated_cost is not None:
                raise ValueError("unavailable_accounting_requires_failed_null_usage")
        else:
            raise ValueError("invalid_accounting_status")

        if self.latency_ms < 0:
            raise ValueError("invalid_usage_latency")


class UsageLedgerError(RuntimeError):
    """Declared persistence failure at the Usage Ledger boundary."""


class UsageLedger(Protocol):
    """Append-only Application port; raw reads and mutations are not exposed."""

    async def append(self, record: UsageRecord) -> None: ...
