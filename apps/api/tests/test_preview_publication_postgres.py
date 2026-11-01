from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_artifact_foundation_postgres import (
    TEST_DATABASE_URL,
    FakeManifestVerifier,
    _command,
    _seed,
)
from test_artifact_foundation_postgres import (
    clean_artifact_schema as clean_artifact_schema,
)

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.generation.application.preview import PreviewPublicationService
from app.modules.generation.application.service import ArtifactFoundationService
from app.modules.generation.infrastructure.preview_repository import PostgresPreviewCommands
from app.modules.generation.infrastructure.repository import (
    SqlAlchemyArtifactFoundationUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext

pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Throwaway PostgreSQL required")
# Import the existing isolated, CASCADE-safe autouse fixture; never use a Hosted database.


def test_publish_and_capability_are_separate_and_replay_never_returns_token() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        user, account, project, scope = await _seed()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            source = _command(
                user_id=user, account_id=account, project_id=project, scope_version_id=scope
            )
            from app.modules.generation.application.ports import FinalizeArtifactVersionCommand

            foundation = ArtifactFoundationService(
                SqlAlchemyArtifactFoundationUnitOfWorkFactory(runtime.session_factory),
                FakeManifestVerifier(),
            )
            await foundation.allocate(source)
            await foundation.finalize(
                FinalizeArtifactVersionCommand(
                    account_id=account,
                    project_id=project,
                    artifact_version_id=source.artifact_version_id,
                    generation_job_id=source.job.id,
                )
            )
            context = TenantContext(user, account, uuid4(), "owner", "active")
            service = PreviewPublicationService(
                PostgresPreviewCommands(runtime.session_factory),
                synthetic_sources=frozenset({(source.artifact_version_id, "sha256:" + "1" * 64)}),
            )
            first = await service.publish(
                context,
                project_id=project,
                artifact_version_id=source.artifact_version_id,
                key="publish",
            )
            replay = await service.publish(
                context,
                project_id=project,
                artifact_version_id=source.artifact_version_id,
                key="publish",
            )
            assert replay.publication_id == first.publication_id
            assert replay.job_id == first.job_id
            assert replay.replayed
            assert not hasattr(first, "token")
            from aria_backend_application.preview_delivery import PreviewError

            with pytest.raises(PreviewError, match="ARTIFACT_VERSION_NOT_READY"):
                await service.issue(
                    context,
                    project_id=project,
                    publication_id=first.publication_id,
                    key="issue",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            async with runtime.engine.begin() as conn:
                assert await conn.scalar(text("SELECT count(*) FROM preview_publications")) == 1
                assert await conn.scalar(text("SELECT count(*) FROM preview_representations")) == 1
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM preview_publications WHERE token_hash IS NOT NULL"
                        )
                    )
                    == 0
                )
            stranger = TenantContext(uuid4(), uuid4(), uuid4(), "owner", "active")
            with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
                await service.revoke(
                    stranger, project_id=project, publication_id=first.publication_id, key="revoke"
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())
