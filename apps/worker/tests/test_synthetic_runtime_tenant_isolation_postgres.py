from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.application.gap_detection_consumer import (
    GapDetectionJobMessage,
    GapDetectionMessageValidationError,
)
from app.application.requirement_generation_consumer import (
    RequirementGenerationJobMessage,
    RequirementGenerationMessageValidationError,
)
from app.application.scope_generation_consumer import (
    ScopeGenerationJobMessage,
    ScopeGenerationMessageValidationError,
)
from app.infrastructure.db.gap_detection_runtime import SqlAlchemyGapDetectionJobStore
from app.infrastructure.db.requirement_generation_runtime import (
    SqlAlchemyRequirementGenerationJobStore,
)
from app.infrastructure.db.scope_generation_runtime import SqlAlchemyScopeGenerationJobStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL isolation evidence",
)


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


@pytest.mark.parametrize("workflow", ("requirements", "gaps", "scope"))
def test_foreign_tenant_outbox_cannot_prepare_job(workflow: str) -> None:
    async def scenario() -> None:
        owner_engine = create_async_engine(_database_url(), poolclass=NullPool)
        worker_engine = create_async_engine(
            _database_url(),
            poolclass=NullPool,
            connect_args={"server_settings": {"role": "aria_worker"}},
        )
        owner_id, foreign_account_id, actor_id = (uuid4() for _ in range(3))
        owner_project_id, foreign_project_id = uuid4(), uuid4()
        job_id, foreign_event_id, context_id, requirement_id = (uuid4() for _ in range(4))
        revision_time = datetime(2026, 9, 22, 12, 0, tzinfo=UTC).isoformat()
        context_revision = {
            "context_item_id": str(context_id),
            "updated_at": revision_time,
        }
        if workflow == "requirements":
            job_type, event_type = "requirement_generation", "requirement.generation_requested.v1"
            payload_ref = {
                "context_version": 1,
                "context_item_revisions": [context_revision],
            }
            store_type = SqlAlchemyRequirementGenerationJobStore
            message_type = RequirementGenerationJobMessage
            validation_error = RequirementGenerationMessageValidationError
        elif workflow == "gaps":
            job_type, event_type = "gap_detection", "gap.detection_requested.v1"
            payload_ref = {
                "context_version": 1,
                "context_item_revisions": [context_revision],
                "requirement_revisions": [],
                "completion_checklist_version": "completion_checklist_v1",
                "critical_rule_pack_version": "critical_gap_rule_pack_v1",
            }
            store_type = SqlAlchemyGapDetectionJobStore
            message_type = GapDetectionJobMessage
            validation_error = GapDetectionMessageValidationError
        else:
            job_type, event_type = "scope_generation", "scope.generation_requested.v1"
            payload_ref = {
                "context_version": 1,
                "context_item_revisions": [
                    {"id": str(context_id), "updated_at": revision_time}
                ],
                "requirement_revisions": [
                    {"id": str(requirement_id), "updated_at": revision_time}
                ],
                "gap_revisions": [],
            }
            store_type = SqlAlchemyScopeGenerationJobStore
            message_type = ScopeGenerationJobMessage
            validation_error = ScopeGenerationMessageValidationError

        try:
            async with owner_engine.begin() as connection:
                await connection.execute(text("TRUNCATE public.accounts CASCADE"))
                await connection.execute(
                    text("INSERT INTO public.profiles (user_id) VALUES (:id)"),
                    {"id": actor_id},
                )
                await connection.execute(
                    text("INSERT INTO public.accounts (id) VALUES (:owner_id), (:foreign_id)"),
                    {"owner_id": owner_id, "foreign_id": foreign_account_id},
                )
                for account_id, project_id, project_type in (
                    (owner_id, owner_project_id, "landing"),
                    (foreign_account_id, foreign_project_id, "corporate"),
                ):
                    await connection.execute(
                        text(
                            "INSERT INTO public.projects "
                            "(id, account_id, owner_id, title, project_type, "
                            "current_context_version) VALUES "
                            "(:id, :account_id, :owner_id, 'Synthetic', :project_type, 1)"
                        ),
                        {
                            "id": project_id,
                            "account_id": account_id,
                            "owner_id": actor_id,
                            "project_type": project_type,
                        },
                    )
                await connection.execute(
                    text(
                        "INSERT INTO public.jobs "
                        "(id, account_id, project_id, job_type, status, payload_ref, "
                        "attempt_count, max_attempts, correlation_id, available_at) VALUES "
                        "(:id, :account_id, :project_id, :job_type, 'queued', "
                        "CAST(:payload_ref AS jsonb), 0, 1, :correlation_id, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "id": job_id,
                        "account_id": owner_id,
                        "project_id": owner_project_id,
                        "job_type": job_type,
                        "payload_ref": json.dumps(payload_ref),
                        "correlation_id": uuid4(),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.outbox_events "
                        "(id, account_id, aggregate_type, aggregate_id, event_type, "
                        "delivery_channel, payload, status, attempt_count, available_at) "
                        "VALUES (:id, :account_id, 'project', :project_id, :event_type, "
                        "'job_queue', CAST(:payload AS jsonb), 'pending', 0, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "id": foreign_event_id,
                        "account_id": foreign_account_id,
                        "project_id": foreign_project_id,
                        "event_type": event_type,
                        "payload": json.dumps(
                            {"jobId": str(job_id), "taskType": job_type, "payloadVersion": "1"}
                        ),
                    },
                )

            with pytest.raises(validation_error):
                await store_type(worker_engine).prepare(
                    message_type("1", foreign_event_id, job_id)
                )
            async with owner_engine.connect() as connection:
                state = (
                    await connection.execute(
                        text("SELECT status, attempt_count FROM public.jobs WHERE id=:id"),
                        {"id": job_id},
                    )
                ).mappings().one()
                effects = (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM public.requirements) AS requirements, "
                            "(SELECT count(*) FROM public.gaps) AS gaps, "
                            "(SELECT count(*) FROM public.scope_drafts) AS drafts"
                        )
                    )
                ).mappings().one()
            assert state == {"status": "queued", "attempt_count": 0}
            assert effects == {"requirements": 0, "gaps": 0, "drafts": 0}
        finally:
            await worker_engine.dispose()
            await owner_engine.dispose()

    asyncio.run(scenario())
