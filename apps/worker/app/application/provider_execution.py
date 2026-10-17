from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.provider_adapter import ProviderAdapter, ProviderRequest, ProviderResult
from app.application.provider_pricing import ProviderPriceCatalog, ProviderPriceVersion


@dataclass(frozen=True, slots=True)
class ProviderCandidate:
    """An explicitly selected evaluation candidate; it is not a routing default."""

    provider: str
    model: str
    adapter: ProviderAdapter


@dataclass(frozen=True, slots=True)
class PricedProviderExecution:
    """Provider result bound to the exact price resolved before the paid call."""

    result: ProviderResult
    price: ProviderPriceVersion


async def execute_priced_candidate(
    *,
    candidate: ProviderCandidate,
    catalog: ProviderPriceCatalog,
    request: ProviderRequest,
    provider_execution_at: datetime,
) -> PricedProviderExecution:
    """Fail closed when pricing is absent, then retain the resolved price."""

    price = await catalog.resolve(
        provider=candidate.provider,
        model=candidate.model,
        provider_execution_at=provider_execution_at,
    )
    result = await candidate.adapter.execute(request)
    if (result.provider, result.model) != (candidate.provider, candidate.model):
        raise ValueError("provider_candidate_identity_mismatch")
    return PricedProviderExecution(result=result, price=price)
