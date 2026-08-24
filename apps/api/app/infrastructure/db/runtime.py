from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.db.readiness import normalize_async_database_url


class DatabaseRuntime:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(
            normalize_async_database_url(database_url),
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def close(self) -> None:
        await self.engine.dispose()
