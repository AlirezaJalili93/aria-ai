from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.provider_adapter import ProviderRequest, ProviderResult
from app.application.provider_execution import ProviderCandidate, execute_priced_candidate
from app.application.provider_pricing import (
    ProviderPriceNotFoundError,
    ProviderPriceVersion,
)


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        self.calls += 1
        return ProviderResult(
            data={"items": []},
            provider="openai",
            model="gpt-5.6-terra",
            provider_request_id="provider-request",
            input_tokens=10,
            cached_input_tokens=0,
            output_tokens=5,
            latency_ms=10.0,
            status="success",
        )


class RecordingCatalog:
    def __init__(self, *, found: bool) -> None:
        self.found = found
        self.calls = 0

    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion:
        self.calls += 1
        if not self.found:
            raise ProviderPriceNotFoundError(provider=provider, model=model)
        return ProviderPriceVersion(
            provider=provider,
            model=model,
            pricing_version="2026-09-20",
            currency="USD",
            input_rate_per_1m=Decimal("2.00"),
            cached_input_rate_per_1m=Decimal("0.20"),
            output_rate_per_1m=Decimal("12.00"),
            effective_from=datetime(2026, 9, 20, tzinfo=UTC),
        )


def test_price_is_resolved_and_retained_before_paid_execution() -> None:
    adapter = RecordingAdapter()
    catalog = RecordingCatalog(found=True)
    candidate = ProviderCandidate(
        provider="openai", model="gpt-5.6-terra", adapter=adapter
    )

    execution = asyncio.run(
        execute_priced_candidate(
            candidate=candidate,
            catalog=catalog,
            request={"instructions": "safe", "input": {}, "output_schema": {}},
            provider_execution_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
        )
    )

    assert catalog.calls == 1
    assert adapter.calls == 1
    assert execution.price.pricing_version == "2026-09-20"
    assert execution.result.provider_request_id == "provider-request"


def test_missing_price_fails_before_adapter_invocation() -> None:
    adapter = RecordingAdapter()
    catalog = RecordingCatalog(found=False)
    candidate = ProviderCandidate(
        provider="openai", model="gpt-5.6-terra", adapter=adapter
    )

    with pytest.raises(ProviderPriceNotFoundError):
        asyncio.run(
            execute_priced_candidate(
                candidate=candidate,
                catalog=catalog,
                request={"instructions": "safe", "input": {}, "output_schema": {}},
                provider_execution_at=datetime(2026, 9, 20, 1, tzinfo=UTC),
            )
        )

    assert catalog.calls == 1
    assert adapter.calls == 0
