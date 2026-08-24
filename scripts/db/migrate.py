from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from time import monotonic

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = WORKSPACE_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.infrastructure.db.readiness import normalize_async_database_url

LOGGER = logging.getLogger("aria.database.migrations")
LOCK_NAMESPACE = "aria-ai:database-migrations"
LOCK_SQL = text(
    "SELECT pg_try_advisory_lock(hashtextextended(:namespace, 0))"
)
UNLOCK_SQL = text(
    "SELECT pg_advisory_unlock(hashtextextended(:namespace, 0))"
)
CURRENT_REVISION_SQL = text("SELECT version_num FROM alembic_version")


class MigrationLockUnavailable(RuntimeError):
    pass


def configure_safe_logger() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    LOGGER.handlers.clear()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    LOGGER.disabled = False


def migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def migrate() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for controlled migrations")

    config = migration_config()
    expected_head = ScriptDirectory.from_config(config).get_current_head()
    if expected_head is None:
        raise RuntimeError("Alembic migration chain has no head revision")

    engine = create_async_engine(
        normalize_async_database_url(database_url),
        poolclass=NullPool,
    )
    acquired = False
    started_at = monotonic()
    LOGGER.info("database.migration_started expected_revision=%s", expected_head)

    try:
        async with engine.connect() as connection:
            acquired = bool(
                (
                    await connection.execute(
                        LOCK_SQL,
                        {"namespace": LOCK_NAMESPACE},
                    )
                ).scalar_one()
            )
            if not acquired:
                raise MigrationLockUnavailable(
                    "Another controlled migration execution holds the database lock"
                )

            try:
                await asyncio.to_thread(command.upgrade, config, "head")
                # Alembic's fileConfig replaces logging configuration. Restore the
                # credential-safe operational logger before recording verification.
                configure_safe_logger()
                applied_revisions = tuple(
                    (
                        await connection.execute(CURRENT_REVISION_SQL)
                    ).scalars().all()
                )
                if applied_revisions != (expected_head,):
                    raise RuntimeError(
                        "Applied Alembic revision does not match the repository head"
                    )
            finally:
                if acquired:
                    unlocked = bool(
                        (
                            await connection.execute(
                                UNLOCK_SQL,
                                {"namespace": LOCK_NAMESPACE},
                            )
                        ).scalar_one()
                    )
                    if not unlocked:
                        LOGGER.error("database.migration_unlock_failed")
    finally:
        await engine.dispose()

    duration_ms = round((monotonic() - started_at) * 1000)
    LOGGER.info(
        "database.migration_completed revision=%s duration_ms=%d",
        expected_head,
        duration_ms,
    )


def main() -> int:
    configure_safe_logger()
    try:
        asyncio.run(migrate())
    except Exception as error:  # noqa: BLE001 - sanitize all CI failure output here
        configure_safe_logger()
        LOGGER.error(
            "database.migration_failed error_type=%s",
            type(error).__name__,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
