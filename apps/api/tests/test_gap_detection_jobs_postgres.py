from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
)
from aria_observability import create_event_logger
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.gaps.application.detection_jobs import (
    ExplicitSyntheticGapDetectionProjects,
    GapDetectionActiveJobConflict,
    ScheduleGapDetectionCommand,
    ScheduleGapDetectionUseCase,
)
from app.modules.gaps.infrastructure.detection_jobs import (
    SqlAlchemyGapDetectionJobUnitOfWorkFactory,
)
from app.modules.gaps.infrastructure.detection_repository import (
    SqlAlchemyGapDetectionSnapshotReader,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


def test_internal_scheduler_allows_zero_requirements_and_blocks_concurrent_revision() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        account_id, project_id, user_id = uuid4(), uuid4(), uuid4()
        context_item_id = uuid4()
        updated_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("TRUNCATE public.accounts CASCADE"))
                await connection.execute(
                    text("INSERT INTO profiles (user_id) VALUES (:id)"), {"id": user_id}
                )
                await connection.execute(
                    text("INSERT INTO accounts (id) VALUES (:id)"), {"id": account_id}
                )
                await connection.execute(
                    text(
                        "INSERT INTO projects "
                        "(id, account_id, owner_id, title, project_type, "
                        "current_context_version) VALUES "
                        "(:project_id, :account_id, :user_id, 'Synthetic', 'landing', 1)"
                    ),
                    {
                        "project_id": project_id,
                        "account_id": account_id,
                        "user_id": user_id,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO context_items "
                        "(id, account_id, project_id, context_version, item_type, content, "
                        "source_refs, status, created_by_type, updated_at) VALUES "
                        "(:id, :account_id, :project_id, 1, 'fact', "
                        "'synthetic fixture only', '[]'::jsonb, 'proposed', 'ai', :updated_at)"
                    ),
                    {
                        "id": context_item_id,
                        "account_id": account_id,
                        "project_id": project_id,
                        "updated_at": updated_at,
                    },
                )
            service = ScheduleGapDetectionUseCase(
                snapshot_reader=SqlAlchemyGapDetectionSnapshotReader(runtime.session_factory),
                unit_of_work_factory=SqlAlchemyGapDetectionJobUnitOfWorkFactory(
                    runtime.session_factory
                ),
                synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(
                    frozenset({(account_id, project_id)})
                ),
                event_logger=create_event_logger(
                    service="aria-api",
                    environment="test",
                    app_version="0.1.0",
                    release_commit_sha=None,
                    level="INFO",
                    stream=StringIO(),
                ),
            )
            command = ScheduleGapDetectionCommand(
                account_id=account_id,
                project_id=project_id,
                context_version=1,
                correlation_id=uuid4(),
            )
            scheduled = await service.execute(command)
            with pytest.raises(GapDetectionActiveJobConflict):
                await service.execute(command)
            async with runtime.engine.connect() as connection:
                job = (
                    await connection.execute(
                        text("SELECT payload_ref FROM jobs WHERE id=:id"),
                        {"id": scheduled.job_id},
                    )
                ).mappings().one()
                counts = (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM requirements) AS requirements, "
                            "(SELECT count(*) FROM jobs) AS jobs, "
                            "(SELECT count(*) FROM outbox_events) AS outbox"
                        )
                    )
                ).mappings().one()
            assert job["payload_ref"] == {
                "context_version": 1,
                "context_item_revisions": [
                    {
                        "context_item_id": str(context_item_id),
                        "updated_at": updated_at.isoformat(),
                    }
                ],
                "requirement_revisions": [],
                "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
                "critical_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
            }
            assert counts == {"requirements": 0, "jobs": 1, "outbox": 1}
        finally:
            await runtime.close()

    asyncio.run(scenario())
