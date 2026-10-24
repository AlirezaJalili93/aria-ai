from __future__ import annotations

import asyncio
import os
from io import StringIO
from uuid import uuid4

import pytest
from aria_observability import create_event_logger
from sqlalchemy import text

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.gaps.application.detection_jobs import (
    ExplicitSyntheticGapDetectionProjects,
    GapDetectionContextRequired,
    ScheduleGapDetectionCommand,
    ScheduleGapDetectionUseCase,
)
from app.modules.gaps.infrastructure.detection_jobs import (
    SqlAlchemyGapDetectionJobUnitOfWorkFactory,
)
from app.modules.gaps.infrastructure.detection_repository import (
    SqlAlchemyGapDetectionSnapshotReader,
)
from app.modules.requirements.application.generation_jobs import (
    ExplicitSyntheticRequirementGenerationProjects,
    RequirementGenerationContextRequired,
    ScheduleRequirementGenerationCommand,
    ScheduleRequirementGenerationUseCase,
)
from app.modules.requirements.infrastructure.generation_jobs import (
    SqlAlchemyRequirementGenerationJobUnitOfWorkFactory,
)
from app.modules.requirements.infrastructure.generation_repository import (
    SqlAlchemyRequirementContextSnapshotReader,
)
from app.modules.scope.application.generation_jobs import (
    ExplicitSyntheticScopeProjects,
    ScheduleScopeGenerationCommand,
    ScheduleScopeGenerationUseCase,
    ScopeGenerationContextRequired,
)
from app.modules.scope.infrastructure.generation_jobs import (
    SqlAlchemyScopeGenerationJobUnitOfWorkFactory,
    SqlAlchemyScopeGenerationPreflightReader,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL isolation evidence",
)


@pytest.mark.parametrize("workflow", ("requirements", "gaps", "scope"))
def test_foreign_tenant_project_is_indistinguishable_from_missing_project(workflow: str) -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        owner_id, foreign_account_id, actor_id, project_id, foreign_project_id = (
            uuid4() for _ in range(5)
        )
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("TRUNCATE public.accounts CASCADE"))
                await connection.execute(
                    text("INSERT INTO public.profiles (user_id) VALUES (:id)"),
                    {"id": actor_id},
                )
                await connection.execute(
                    text("INSERT INTO public.accounts (id) VALUES (:id), (:foreign_id)"),
                    {"id": owner_id, "foreign_id": foreign_account_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.projects "
                        "(id, account_id, owner_id, title, project_type, current_context_version) "
                        "VALUES (:id, :account_id, :owner_id, 'Synthetic', 'landing', 1)"
                    ),
                    {"id": project_id, "account_id": owner_id, "owner_id": actor_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.projects "
                        "(id, account_id, owner_id, title, project_type, current_context_version) "
                        "VALUES (:id, :account_id, :owner_id, 'Synthetic', 'corporate', 1)"
                    ),
                    {
                        "id": foreign_project_id,
                        "account_id": foreign_account_id,
                        "owner_id": actor_id,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.context_items "
                        "(id, account_id, project_id, context_version, item_type, content, "
                        "source_refs, status, created_by_type) VALUES "
                        "(:id, :account_id, :project_id, 1, 'fact', 'synthetic only', "
                        "'[]'::jsonb, 'proposed', 'ai')"
                    ),
                    {"id": uuid4(), "account_id": owner_id, "project_id": project_id},
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.requirements "
                        "(id, account_id, project_id, context_version, category, title, "
                        "description, priority, status, created_by_type) VALUES "
                        "(:id, :account_id, :project_id, 1, 'functional', 'Synthetic', "
                        "'Synthetic only', 'must', 'draft', 'ai')"
                    ),
                    {"id": uuid4(), "account_id": owner_id, "project_id": project_id},
                )

            logger = create_event_logger(
                service="aria-api",
                environment="test",
                app_version="0.1.0",
                release_commit_sha=None,
                level="INFO",
                stream=StringIO(),
            )
            missing_project_id = uuid4()
            # Keep the synthetic allowlist from masking the tenant-scoped DB check.
            approved = frozenset(
                {
                    (foreign_account_id, project_id),
                    (foreign_account_id, missing_project_id),
                }
            )
            if workflow == "requirements":
                service = ScheduleRequirementGenerationUseCase(
                    snapshot_reader=SqlAlchemyRequirementContextSnapshotReader(
                        runtime.session_factory
                    ),
                    unit_of_work_factory=SqlAlchemyRequirementGenerationJobUnitOfWorkFactory(
                        runtime.session_factory
                    ),
                    synthetic_authorizer=ExplicitSyntheticRequirementGenerationProjects(approved),
                    event_logger=logger,
                )
                command_type = ScheduleRequirementGenerationCommand
                required_error = RequirementGenerationContextRequired
            elif workflow == "gaps":
                service = ScheduleGapDetectionUseCase(
                    snapshot_reader=SqlAlchemyGapDetectionSnapshotReader(
                        runtime.session_factory
                    ),
                    unit_of_work_factory=SqlAlchemyGapDetectionJobUnitOfWorkFactory(
                        runtime.session_factory
                    ),
                    synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(approved),
                    event_logger=logger,
                )
                command_type = ScheduleGapDetectionCommand
                required_error = GapDetectionContextRequired
            else:
                service = ScheduleScopeGenerationUseCase(
                    preflight_reader=SqlAlchemyScopeGenerationPreflightReader(
                        runtime.session_factory
                    ),
                    unit_of_work_factory=SqlAlchemyScopeGenerationJobUnitOfWorkFactory(
                        runtime.session_factory
                    ),
                    synthetic_authorizer=ExplicitSyntheticScopeProjects(approved),
                    event_logger=logger,
                )
                command_type = ScheduleScopeGenerationCommand
                required_error = ScopeGenerationContextRequired

            for attempted_project_id in (project_id, missing_project_id):
                with pytest.raises(required_error):
                    await service.execute(
                        command_type(
                            account_id=foreign_account_id,
                            project_id=attempted_project_id,
                            context_version=1,
                            correlation_id=uuid4(),
                        )
                    )
            async with runtime.engine.connect() as connection:
                counts = (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM public.jobs) AS jobs, "
                            "(SELECT count(*) FROM public.outbox_events) AS outbox"
                        )
                    )
                ).mappings().one()
            assert counts == {"jobs": 0, "outbox": 0}
        finally:
            await runtime.close()

    asyncio.run(scenario())
