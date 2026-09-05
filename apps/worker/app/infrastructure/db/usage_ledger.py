from __future__ import annotations

from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    insert,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.usage_ledger import UsageLedgerError, UsageRecord

usage_records = Table(
    "usage_records",
    MetaData(),
    Column(
        "id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("account_id", PostgreSQLUUID(as_uuid=True), nullable=False),
    Column("project_id", PostgreSQLUUID(as_uuid=True), nullable=True),
    Column("job_id", PostgreSQLUUID(as_uuid=True), nullable=True),
    Column("task_type", Text, nullable=False),
    Column("workflow_version", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("provider", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("provider_request_id", Text, nullable=True),
    Column("input_tokens", BigInteger, nullable=False),
    Column("cached_input_tokens", BigInteger, nullable=False),
    Column("output_tokens", BigInteger, nullable=False),
    Column("latency_ms", Numeric(14, 3), nullable=False),
    Column("status", Text, nullable=False),
    Column("error_code", Text, nullable=True),
    Column("retry_no", Integer, nullable=False),
    Column("estimated_cost", Numeric(14, 8), nullable=False),
    Column("currency", CHAR(3), nullable=False, server_default="USD"),
    Column("pricing_version", Text, nullable=False),
    Column("correlation_id", PostgreSQLUUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    implicit_returning=False,
)


class SqlAlchemyUsageLedger:
    """Least-privilege Worker adapter that can only append a Usage record."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def append(self, record: UsageRecord) -> None:
        statement = insert(usage_records).values(
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
            estimated_cost=record.estimated_cost,
            currency=record.currency,
            pricing_version=record.pricing_version,
            correlation_id=record.correlation_id,
        )
        try:
            async with self._engine.begin() as connection:
                await connection.execute(statement)
        except SQLAlchemyError:
            raise UsageLedgerError from None
