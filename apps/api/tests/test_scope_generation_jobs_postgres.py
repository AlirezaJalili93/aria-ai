from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4

import pytest
from aria_backend_application.scope_generation import (
    ScopeGenerationRequirementsRequiredError,
)
from aria_observability import create_event_logger
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.scope.application.generation_jobs import (
    ExplicitSyntheticScopeProjects,
    ScheduleScopeGenerationCommand,
    ScheduleScopeGenerationUseCase,
    ScopeGenerationActiveJobConflict,
    ScopeGenerationBlocked,
)
from app.modules.scope.infrastructure.generation_jobs import (
    SqlAlchemyScopeGenerationJobUnitOfWorkFactory,
    SqlAlchemyScopeGenerationPreflightReader,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


def test_scheduler_pins_exact_inputs_and_has_db_active_job_guard() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        account_id, project_id, user_id, context_item_id, requirement_id = (
            uuid4() for _ in range(5)
        )
        updated_at = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("TRUNCATE public.accounts CASCADE"))
                await connection.execute(
                    text("INSERT INTO public.profiles (user_id) VALUES (:id)"),
                    {"id": user_id},
                )
                await connection.execute(
                    text("INSERT INTO public.accounts (id) VALUES (:id)"),
                    {"id": account_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.projects "
                        "(id, account_id, owner_id, title, project_type, "
                        "current_context_version) VALUES "
                        "(:project_id, :account_id, :user_id, 'Synthetic', 'landing', 1)"
                    ),
                    {"project_id": project_id, "account_id": account_id, "user_id": user_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.context_items "
                        "(id, account_id, project_id, context_version, item_type, "
                        "content, source_refs, status, created_by_type, updated_at) "
                        "VALUES (:id, :account_id, :project_id, 1, 'fact', "
                        "'synthetic only', '[]'::jsonb, 'proposed', 'ai', :updated_at)"
                    ),
                    {
                        "id": context_item_id,
                        "account_id": account_id,
                        "project_id": project_id,
                        "updated_at": updated_at,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.requirements "
                        "(id, account_id, project_id, context_version, category, title, "
                        "description, priority, status, created_by_type, updated_at) "
                        "VALUES (:id, :account_id, :project_id, 1, 'functional', "
                        "'Synthetic', 'Synthetic only', 'must', 'draft', 'ai', :updated_at)"
                    ),
                    {
                        "id": requirement_id,
                        "account_id": account_id,
                        "project_id": project_id,
                        "updated_at": updated_at,
                    },
                )
            service = ScheduleScopeGenerationUseCase(
                preflight_reader=SqlAlchemyScopeGenerationPreflightReader(runtime.session_factory),
                unit_of_work_factory=SqlAlchemyScopeGenerationJobUnitOfWorkFactory(
                    runtime.session_factory
                ),
                synthetic_authorizer=ExplicitSyntheticScopeProjects(
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
            command = ScheduleScopeGenerationCommand(
                account_id=account_id,
                project_id=project_id,
                context_version=1,
                correlation_id=uuid4(),
            )
            scheduled = await service.execute(command)
            with pytest.raises(ScopeGenerationActiveJobConflict):
                await service.execute(command)
            async with runtime.engine.connect() as connection:
                payload = await connection.scalar(
                    text("SELECT payload_ref FROM public.jobs WHERE id=:id"),
                    {"id": scheduled.job_id},
                )
                counts = (
                    (
                        await connection.execute(
                            text(
                                "SELECT (SELECT count(*) FROM public.jobs) AS jobs, "
                                "(SELECT count(*) FROM public.outbox_events) AS outbox"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
            assert payload == {
                "context_version": 1,
                "context_item_revisions": [
                    {
                        "id": str(context_item_id),
                        "updated_at": updated_at.isoformat(),
                    }
                ],
                "requirement_revisions": [
                    {
                        "id": str(requirement_id),
                        "updated_at": updated_at.isoformat(),
                    }
                ],
                "gap_revisions": [],
            }
            assert counts == {"jobs": 1, "outbox": 1}

            async with runtime.engine.begin() as connection:
                await connection.execute(
                    text("UPDATE public.jobs SET status='failed' WHERE id=:id"),
                    {"id": scheduled.job_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.gaps "
                        "(id, account_id, project_id, context_version, gap_type, "
                        "severity, status) VALUES "
                        "(:id, :account_id, :project_id, 1, 'missing_information', "
                        "'critical', 'open')"
                    ), {"id": uuid4(), "account_id": account_id,
                        "project_id": project_id},
                )
            with pytest.raises(ScopeGenerationBlocked):
                await service.execute(command)
            async with runtime.engine.begin() as connection:
                await connection.execute(
                    text("UPDATE public.gaps SET status='dismissed' "
                         "WHERE account_id=:account_id AND project_id=:project_id"),
                    {"account_id": account_id, "project_id": project_id},
                )
            scheduled_after_dismissal = await service.execute(command)
            assert scheduled_after_dismissal.job_id != scheduled.job_id
            async with runtime.engine.begin() as connection:
                await connection.execute(
                    text("UPDATE public.jobs SET status='failed' WHERE id=:id"),
                    {"id": scheduled_after_dismissal.job_id},
                )
                await connection.execute(
                    text("DELETE FROM public.requirements WHERE id=:id"),
                    {"id": requirement_id},
                )
            with pytest.raises(ScopeGenerationRequirementsRequiredError):
                await service.execute(command)
            async with runtime.engine.connect() as connection:
                count = await connection.scalar(text("SELECT count(*) FROM public.jobs"))
            assert count == 2
        finally:
            await runtime.close()

    asyncio.run(scenario())
