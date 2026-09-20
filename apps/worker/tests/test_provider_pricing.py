from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from aria_backend_application.provider_pricing import (
    InvalidTokenUsageError,
    ProviderPriceNotFoundError,
    ProviderPriceVersion,
    TokenUsage,
    UnpricedUsageRecord,
    calculate_estimated_cost,
    price_usage_record,
)


def _price(**overrides: object) -> ProviderPriceVersion:
    values: dict[str, object] = {
        "provider": "synthetic-provider",
        "model": "synthetic-model",
        "pricing_version": "synthetic-v1",
        "currency": "USD",
        "input_rate_per_1m": Decimal("2.00000000"),
        "cached_input_rate_per_1m": Decimal("0.50000000"),
        "output_rate_per_1m": Decimal("8.00000000"),
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return ProviderPriceVersion(**values)  # type: ignore[arg-type]


def test_calculator_uses_cached_tokens_as_subset_without_intermediate_rounding() -> None:
    usage = TokenUsage(input_tokens=1_000_000, cached_input_tokens=250_000, output_tokens=50_000)

    result = calculate_estimated_cost(_price(), usage)

    assert result == Decimal("2.02500000")


def test_calculator_rounds_total_once_with_round_half_up() -> None:
    price = _price(
        input_rate_per_1m=Decimal("0.00500000"),
        cached_input_rate_per_1m=Decimal("0"),
        output_rate_per_1m=Decimal("0"),
    )

    assert calculate_estimated_cost(price, TokenUsage(1, 0, 0)) == Decimal("0.00000001")


@pytest.mark.parametrize(
    "usage",
    [
        TokenUsage(-1, 0, 0),
        TokenUsage(0, -1, 0),
        TokenUsage(0, 0, -1),
        TokenUsage(1, 2, 0),
    ],
)
def test_invalid_token_accounting_is_rejected(usage: TokenUsage) -> None:
    with pytest.raises(InvalidTokenUsageError):
        calculate_estimated_cost(_price(), usage)


class EmptyCatalog:
    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion:
        raise ProviderPriceNotFoundError(provider=provider, model=model)


def test_missing_price_is_an_explicit_preflight_failure() -> None:
    async def resolve_before_provider_call() -> None:
        catalog = EmptyCatalog()
        provider_called = False
        with pytest.raises(ProviderPriceNotFoundError):
            await catalog.resolve(
                provider="synthetic-provider",
                model="synthetic-model",
                provider_execution_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        assert provider_called is False

    asyncio.run(resolve_before_provider_call())


def test_resolved_price_builds_authoritative_usage_record() -> None:
    draft = UnpricedUsageRecord(
        account_id=uuid4(),
        project_id=None,
        job_id=None,
        task_type="synthetic-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        provider="synthetic-provider",
        model="synthetic-model",
        provider_request_id="synthetic-request",
        input_tokens=1_000_000,
        cached_input_tokens=250_000,
        output_tokens=50_000,
        latency_ms=Decimal("12.345"),
        status="success",
        error_code=None,
        retry_no=0,
        repair_no=0,
        correlation_id=uuid4(),
    )

    record = price_usage_record(draft, _price())

    assert record.estimated_cost == Decimal("2.02500000")
    assert record.pricing_version == "synthetic-v1"
    assert record.currency == "USD"
