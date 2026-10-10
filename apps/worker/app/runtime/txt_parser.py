from __future__ import annotations

import re

from aria_observability import StructuredEventLogger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.application.context_parser import CanonicalTextParser
from app.application.txt_parser_consumer import TxtParserConsumer
from app.core.config import WorkerSettings
from app.infrastructure.db.txt_parser_runtime import (
    PostgresJobExecutionGuard,
    SqlAlchemyTxtParserJobStore,
)
from app.infrastructure.storage.supabase_s3 import SupabaseS3PrivateObjectReader


def build_txt_parser_consumer(
    settings: WorkerSettings,
    event_logger: StructuredEventLogger,
) -> TxtParserConsumer:
    database_url = _required_secret(settings, "database_url")
    storage_access_key = _required_secret(settings, "storage_access_key")
    storage_secret_key = _required_secret(settings, "storage_secret_key")
    if settings.storage_endpoint is None:
        raise ValueError("Missing TXT Parser Worker configuration: storage_endpoint")
    if settings.storage_region is None:
        raise ValueError("Missing TXT Parser Worker configuration: storage_region")
    if settings.storage_bucket is None:
        raise ValueError("Missing TXT Parser Worker configuration: storage_bucket")

    engine = create_async_engine(
        _normalize_async_database_url(database_url),
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    parser = CanonicalTextParser(event_logger=event_logger)
    return TxtParserConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=SqlAlchemyTxtParserJobStore(engine),
        parser=parser,
        object_reader=SupabaseS3PrivateObjectReader(
            endpoint_url=str(settings.storage_endpoint),
            region_name=settings.storage_region,
            bucket=settings.storage_bucket,
            access_key_id=storage_access_key,
            secret_access_key=storage_secret_key,
        ),
        metrics=None,
        event_logger=event_logger,
    )


def _required_secret(settings: WorkerSettings, name: str) -> str:
    value = getattr(settings, name)
    if value is None:
        raise ValueError(f"Missing TXT Parser Worker configuration: {name}")
    return value.get_secret_value()


def _normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        normalized = database_url
    elif database_url.startswith("postgres://"):
        normalized = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        normalized = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", normalized)
