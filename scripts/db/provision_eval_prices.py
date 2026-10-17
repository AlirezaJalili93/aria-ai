from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = WORKSPACE_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.infrastructure.db.readiness import normalize_async_database_url

LOGGER = logging.getLogger("aria.provider_price_provisioning")
CONFIRMATION_VALUE = "provision-0086-controlled-eval-prices"
LOCK_NAMESPACE = "aria-ai:0086-provider-price-provisioning"


@dataclass(frozen=True, slots=True)
class FrozenProviderPrice:
    provider: str
    model: str
    pricing_version: str
    currency: str
    input_rate_per_1m: Decimal
    cached_input_rate_per_1m: Decimal
    output_rate_per_1m: Decimal
    effective_from: datetime


# Provider source dates are date-only. ADR-072 normalizes those dates to UTC
# start-of-day for the Catalog's TIMESTAMPTZ contract.
FROZEN_PROVIDER_PRICES = (
    FrozenProviderPrice(
        provider="openai",
        model="gpt-5.6-terra",
        pricing_version="openai-gpt-5.6-terra-standard-2026-07-30",
        currency="USD",
        input_rate_per_1m=Decimal("2.00000000"),
        cached_input_rate_per_1m=Decimal("0.20000000"),
        output_rate_per_1m=Decimal("12.00000000"),
        effective_from=datetime(2026, 7, 30, tzinfo=UTC),
    ),
    FrozenProviderPrice(
        provider="google",
        model="gemini-3.8-flash",
        pricing_version="google-gemini-3.8-flash-standard-intro-2026-09-02",
        currency="USD",
        input_rate_per_1m=Decimal("0.75000000"),
        cached_input_rate_per_1m=Decimal("0.07500000"),
        output_rate_per_1m=Decimal("3.75000000"),
        effective_from=datetime(2026, 9, 2, tzinfo=UTC),
    ),
)

LOCK_SQL = text(
    "SELECT pg_advisory_xact_lock(hashtextextended(:namespace, 0))"
)
INSERT_SQL = text(
    """
    INSERT INTO public.provider_price_versions
        (provider, model, pricing_version, currency,
         input_rate_per_1m, cached_input_rate_per_1m, output_rate_per_1m,
         effective_from)
    VALUES
        (:provider_0, :model_0, :pricing_version_0, :currency_0,
         :input_rate_0, :cached_input_rate_0, :output_rate_0, :effective_from_0),
        (:provider_1, :model_1, :pricing_version_1, :currency_1,
         :input_rate_1, :cached_input_rate_1, :output_rate_1, :effective_from_1)
    ON CONFLICT DO NOTHING
    """
)
FETCH_SQL = text(
    """
    SELECT provider, model, pricing_version, currency,
           input_rate_per_1m, cached_input_rate_per_1m, output_rate_per_1m,
           effective_from
      FROM public.provider_price_versions
     WHERE (provider = :provider_0 AND model = :model_0
            AND pricing_version = :pricing_version_0)
        OR (provider = :provider_1 AND model = :model_1
            AND pricing_version = :pricing_version_1)
     ORDER BY provider, model, pricing_version
    """
)


class PriceCatalogProvisioningConflict(RuntimeError):
    pass


def configure_safe_logger() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    LOGGER.handlers.clear()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def _parameters() -> dict[str, object]:
    values: dict[str, object] = {"namespace": LOCK_NAMESPACE}
    for index, price in enumerate(FROZEN_PROVIDER_PRICES):
        values.update(
            {
                f"provider_{index}": price.provider,
                f"model_{index}": price.model,
                f"pricing_version_{index}": price.pricing_version,
                f"currency_{index}": price.currency,
                f"input_rate_{index}": price.input_rate_per_1m,
                f"cached_input_rate_{index}": price.cached_input_rate_per_1m,
                f"output_rate_{index}": price.output_rate_per_1m,
                f"effective_from_{index}": price.effective_from,
            }
        )
    return values


def _canonical_row(mapping: Mapping[str, Any]) -> FrozenProviderPrice:
    effective_from = mapping["effective_from"]
    if not isinstance(effective_from, datetime):
        raise PriceCatalogProvisioningConflict("catalog_effective_from_invalid")
    if effective_from.tzinfo is None:
        raise PriceCatalogProvisioningConflict("catalog_effective_from_not_timezone_aware")
    return FrozenProviderPrice(
        provider=str(mapping["provider"]),
        model=str(mapping["model"]),
        pricing_version=str(mapping["pricing_version"]),
        currency=str(mapping["currency"]),
        input_rate_per_1m=Decimal(str(mapping["input_rate_per_1m"])),
        cached_input_rate_per_1m=Decimal(str(mapping["cached_input_rate_per_1m"])),
        output_rate_per_1m=Decimal(str(mapping["output_rate_per_1m"])),
        effective_from=effective_from.astimezone(UTC),
    )


def verify_catalog_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    actual = tuple(sorted((_canonical_row(row) for row in rows), key=repr))
    expected = tuple(sorted(FROZEN_PROVIDER_PRICES, key=repr))
    if actual != expected:
        raise PriceCatalogProvisioningConflict("catalog_rows_missing_or_conflicting")


async def provision_prices(engine: AsyncEngine) -> None:
    parameters = _parameters()
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL statement_timeout = '5s'"))
        await connection.execute(LOCK_SQL, parameters)
        await connection.execute(INSERT_SQL, parameters)
        rows = tuple(
            cast(Mapping[str, Any], row)
            for row in (await connection.execute(FETCH_SQL, parameters)).mappings().all()
        )
        verify_catalog_rows(rows)


async def run() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    confirmation = os.environ.get("ARIA_EVAL_DATABASE_CONFIRMED", "")
    if not database_url.strip():
        raise RuntimeError("DATABASE_URL is required")
    if confirmation != CONFIRMATION_VALUE:
        raise RuntimeError("controlled evaluation database confirmation is required")

    engine = create_async_engine(
        normalize_async_database_url(database_url),
        poolclass=NullPool,
    )
    try:
        await provision_prices(engine)
    finally:
        await engine.dispose()


def main() -> int:
    configure_safe_logger()
    LOGGER.info("provider_price.provision_started catalog=0086")
    try:
        asyncio.run(run())
    except Exception as error:  # noqa: BLE001 - sanitize all operator failure output
        LOGGER.error(
            "provider_price.provision_failed catalog=0086 error_type=%s",
            type(error).__name__,
        )
        return 1
    LOGGER.info("provider_price.provision_completed catalog=0086 rows=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
