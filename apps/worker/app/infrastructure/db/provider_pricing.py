from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, Column, DateTime, MetaData, Numeric, Table, Text, select
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.provider_pricing import (
    ProviderPriceCatalogUnavailableError,
    ProviderPriceNotFoundError,
    ProviderPriceVersion,
)

provider_price_versions = Table(
    "provider_price_versions",
    MetaData(),
    Column("id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("pricing_version", Text, nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("input_rate_per_1m", Numeric(20, 8), nullable=False),
    Column("cached_input_rate_per_1m", Numeric(20, 8), nullable=False),
    Column("output_rate_per_1m", Numeric(20, 8), nullable=False),
    Column("effective_from", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class PostgresProviderPriceCatalog:
    """Worker read adapter for deterministic, effective-at price resolution."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion:
        if provider_execution_at.tzinfo is None:
            raise ValueError("provider_execution_at must be timezone-aware")
        statement = (
            select(provider_price_versions)
            .where(
                provider_price_versions.c.provider == provider,
                provider_price_versions.c.model == model,
                provider_price_versions.c.effective_from <= provider_execution_at,
            )
            .order_by(provider_price_versions.c.effective_from.desc())
            .limit(1)
        )
        try:
            async with self._engine.connect() as connection:
                row = (await connection.execute(statement)).mappings().one_or_none()
        except SQLAlchemyError:
            raise ProviderPriceCatalogUnavailableError from None
        if row is None:
            raise ProviderPriceNotFoundError(provider=provider, model=model)
        return ProviderPriceVersion(
            provider=row["provider"],
            model=row["model"],
            pricing_version=row["pricing_version"],
            currency=row["currency"],
            input_rate_per_1m=row["input_rate_per_1m"],
            cached_input_rate_per_1m=row["cached_input_rate_per_1m"],
            output_rate_per_1m=row["output_rate_per_1m"],
            effective_from=row["effective_from"],
        )
