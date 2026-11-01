from __future__ import annotations

import re

from aria_observability import StructuredEventLogger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.application.outbox_delivery import DurableOutboxRelay, OutboxRelayRunner
from app.core.config import WorkerSettings
from app.infrastructure.db.outbox_delivery import PostgresOutboxDeliveryRepository
from app.infrastructure.queue.celery_runtime import create_celery_app
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher


async def run_outbox_relay(
    settings: WorkerSettings,
    event_logger: StructuredEventLogger,
) -> None:
    if settings.database_url is None:
        raise ValueError("Missing Outbox Relay configuration: database_url")
    queue_configuration = settings.require_queue_runtime_configuration()
    engine = create_async_engine(
        _normalize_async_database_url(settings.database_url.get_secret_value()),
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    relay = DurableOutboxRelay(
        repository=PostgresOutboxDeliveryRepository(engine),
        publisher=CeleryOutboxPublisher(
            create_celery_app(queue_configuration),
            queue_name=queue_configuration.queue_name,
        ),
        event_logger=event_logger,
    )
    event_logger.emit(
        "outbox.relay_started",
        status="started",
        process_mode="relay",
    )
    try:
        await OutboxRelayRunner(relay).run_forever()
    finally:
        await engine.dispose()


def _normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        normalized = database_url
    elif database_url.startswith("postgres://"):
        normalized = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        normalized = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", normalized)
