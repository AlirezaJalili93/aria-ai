from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from uuid import UUID

from aria_backend_application.usage_ledger import UsageRecord, UsageStatus

TOKENS_PER_MILLION = Decimal(1000000)
COST_QUANTUM = Decimal("0.00000001")


class ProviderPriceError(RuntimeError):
    """Base error for the provider-neutral pricing boundary."""


class ProviderPriceNotFoundError(ProviderPriceError):
    """Raised during preflight when no effective catalog entry exists."""

    def __init__(self, *, provider: str, model: str) -> None:
        super().__init__("provider_price_not_found")
        self.provider = provider
        self.model = model


class ProviderPriceCatalogUnavailableError(ProviderPriceError):
    """Declared infrastructure failure while resolving a price."""


class InvalidTokenUsageError(ValueError):
    """Token accounting violates the normalized Provider result invariant."""


class ProviderPriceMismatchError(ValueError):
    """A resolved price does not belong to the execution being metered."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderPriceVersion:
    provider: str
    model: str
    pricing_version: str
    currency: str
    input_rate_per_1m: Decimal
    cached_input_rate_per_1m: Decimal
    output_rate_per_1m: Decimal
    effective_from: datetime

    def __post_init__(self) -> None:
        if not self.provider or not self.model or not self.pricing_version:
            raise ValueError("Provider price identity fields are required")
        if len(self.currency) != 3:
            raise ValueError("Provider price currency must be a three-letter code")
        if any(
            value < 0
            for value in (
                self.input_rate_per_1m,
                self.cached_input_rate_per_1m,
                self.output_rate_per_1m,
            )
        ):
            raise ValueError("Provider price rates must be non-negative")
        if self.effective_from.tzinfo is None:
            raise ValueError("effective_from must be timezone-aware")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Normalized token counts; cached input is a subset of total input."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True, kw_only=True)
class UnpricedUsageRecord:
    """Provider result metadata before authoritative catalog pricing is attached."""

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
    repair_no: int
    correlation_id: UUID


class ProviderPriceCatalog(Protocol):
    """Read-only deterministic catalog used before a paid Provider invocation."""

    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion: ...


def calculate_estimated_cost(
    price: ProviderPriceVersion,
    usage: TokenUsage,
) -> Decimal:
    """Calculate once at full Decimal precision, then round the total to ledger scale."""

    if (
        usage.input_tokens < 0
        or usage.cached_input_tokens < 0
        or usage.output_tokens < 0
        or usage.cached_input_tokens > usage.input_tokens
    ):
        raise InvalidTokenUsageError("invalid_token_accounting")

    normal_input_tokens = usage.input_tokens - usage.cached_input_tokens
    total = (
        Decimal(normal_input_tokens) * price.input_rate_per_1m
        + Decimal(usage.cached_input_tokens) * price.cached_input_rate_per_1m
        + Decimal(usage.output_tokens) * price.output_rate_per_1m
    ) / TOKENS_PER_MILLION
    return total.quantize(COST_QUANTUM, rounding=ROUND_HALF_UP)


def price_usage_record(
    record: UnpricedUsageRecord,
    price: ProviderPriceVersion,
) -> UsageRecord:
    """Attach the exact preflight resolution to the immutable Usage record."""

    if (record.provider, record.model) != (price.provider, price.model):
        raise ProviderPriceMismatchError("provider_price_identity_mismatch")
    usage = TokenUsage(
        input_tokens=record.input_tokens,
        cached_input_tokens=record.cached_input_tokens,
        output_tokens=record.output_tokens,
    )
    return UsageRecord(
        account_id=record.account_id,
        project_id=record.project_id,
        job_id=record.job_id,
        task_type=record.task_type,
        workflow_version=record.workflow_version,
        prompt_version=record.prompt_version,
        provider=record.provider,
        model=record.model,
        provider_request_id=record.provider_request_id,
        input_tokens=record.input_tokens,
        cached_input_tokens=record.cached_input_tokens,
        output_tokens=record.output_tokens,
        latency_ms=record.latency_ms,
        status=record.status,
        error_code=record.error_code,
        retry_no=record.retry_no,
        repair_no=record.repair_no,
        estimated_cost=calculate_estimated_cost(price, usage),
        pricing_version=price.pricing_version,
        correlation_id=record.correlation_id,
        currency=price.currency,
    )
