import asyncio
import re

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

READINESS_TIMEOUT_SECONDS = 3.0


def normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        normalized_url = database_url
    elif database_url.startswith("postgres://"):
        normalized_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        normalized_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        normalized_url = database_url

    return re.sub(r"([?&])sslmode=", r"\1ssl=", normalized_url)


class PostgresReadinessProbe:
    def __init__(
        self,
        database_url: str | None = None,
        *,
        engine: AsyncEngine | None = None,
        timeout_seconds: float = READINESS_TIMEOUT_SECONDS,
    ) -> None:
        if (database_url is None) == (engine is None):
            raise ValueError("Provide exactly one of database_url or engine")
        self._owns_engine = engine is None
        self._engine = engine or create_async_engine(
            normalize_async_database_url(database_url or ""), pool_pre_ping=True
        )
        self._timeout_seconds = timeout_seconds

    async def __call__(self) -> bool:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._engine.connect() as connection:
                    result = await connection.execute(text("SELECT 1"))
                    return result.scalar_one() == 1
        except (TimeoutError, SQLAlchemyError, OSError):
            return False

    async def close(self) -> None:
        if self._owns_engine:
            await self._engine.dispose()


async def unavailable_database_probe() -> bool:
    return False
