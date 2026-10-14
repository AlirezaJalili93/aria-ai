from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.generation.application.ports import (
    AllocateArtifactCommand,
    ArtifactAllocationConflict,
    ArtifactManifestInvalid,
    ArtifactRepositoryError,
    ArtifactScopeNotEligible,
    FinalizeArtifactVersionCommand,
    VerifiedArtifactManifest,
)
from app.modules.generation.application.service import ArtifactFoundationService
from app.modules.generation.infrastructure.repository import (
    SqlAlchemyArtifactFoundationUnitOfWorkFactory,
)
from app.modules.jobs.domain.job import NewJob, NewOutboxEvent

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)
API_ROOT = Path(__file__).parents[1]


class FakeManifestVerifier:
    def __init__(
        self,
        *,
        valid: bool = True,
        storage_ref: str = "private manifest reference",
        artifact_hash: str = "sha256:" + "1" * 64,
    ) -> None:
        self.valid = valid
        self.storage_ref = storage_ref
        self.artifact_hash = artifact_hash
        self.calls: list[UUID] = []

    async def resolve_verified(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        artifact_version_id: UUID,
    ) -> VerifiedArtifactManifest | None:
        del account_id, project_id
        self.calls.append(artifact_version_id)
        if not self.valid:
            return None
        return VerifiedArtifactManifest(
            storage_ref=self.storage_ref,
            artifact_hash=self.artifact_hash,
        )


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            return await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_artifact_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    alembic_command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE artifact_versions, artifacts, scope_change_requests, "
            "scope_approvals, scope_share_links, scope_versions, scope_drafts, "
            "clarifications, gaps, requirements, context_items, usage_records, "
            "outbox_events, jobs, idempotency_records, context_source_versions, "
            "context_sources, project_create_requests, projects, account_memberships, "
            "profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


async def _seed(*, scope_status: str = "approved") -> tuple[UUID, UUID, UUID, UUID]:
    user_id, account_id, project_id, scope_version_id = uuid4(), uuid4(), uuid4(), uuid4()
    await _execute("INSERT INTO profiles (user_id) VALUES (:id)", {"id": user_id})
    await _execute("INSERT INTO accounts (id) VALUES (:id)", {"id": account_id})
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) "
        "VALUES (:id, :account, :owner, 'Artifact Project', 'landing', 1)",
        {"id": project_id, "account": account_id, "owner": user_id},
    )
    await _execute(
        "INSERT INTO scope_versions "
        "(id, account_id, project_id, version_no, context_version, status, "
        "snapshot_data, snapshot_hash, created_by) "
        "VALUES (:id, :account, :project, 1, 1, :status, CAST(:snapshot AS jsonb), "
        ":hash, :creator)",
        {
            "id": scope_version_id,
            "account": account_id,
            "project": project_id,
            "status": scope_status,
            "snapshot": json.dumps({}),
            "hash": "sha256:" + "0" * 64,
            "creator": user_id,
        },
    )
    return user_id, account_id, project_id, scope_version_id


def _command(
    *,
    user_id: UUID,
    account_id: UUID,
    project_id: UUID,
    scope_version_id: UUID,
    artifact_id: UUID | None = None,
    version_id: UUID | None = None,
    job_id: UUID | None = None,
    event_id: UUID | None = None,
    trigger_type: str = "initial",
) -> AllocateArtifactCommand:
    now = datetime.now(UTC)
    resolved_job_id = job_id or uuid4()
    resolved_artifact_id = artifact_id or uuid4()
    resolved_version_id = version_id or uuid4()
    return AllocateArtifactCommand(
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
        artifact_id=resolved_artifact_id,
        artifact_version_id=resolved_version_id,
        created_by=user_id,
        trigger_type=trigger_type,  # type: ignore[arg-type]
        job=NewJob(
            id=resolved_job_id,
            account_id=account_id,
            project_id=project_id,
            job_type="artifact_generation",
            status="queued",
            payload_ref={
                "artifact_version_id": str(resolved_version_id),
                "scope_version_id": str(scope_version_id),
            },
            attempt_count=0,
            max_attempts=1,
            idempotency_key=None,
            correlation_id=uuid4(),
            available_at=now,
        ),
        outbox_event=NewOutboxEvent(
            id=event_id or uuid4(),
            account_id=account_id,
            aggregate_type="artifact_version",
            aggregate_id=resolved_version_id,
            event_type="artifact.generation_requested.v1",
            delivery_channel="job_queue",
            payload={
                "jobId": str(resolved_job_id),
                "taskType": "artifact_generation",
                "payloadVersion": "1",
            },
            status="pending",
            attempt_count=0,
            available_at=now,
        ),
    )


async def _service(
    verifier: FakeManifestVerifier,
) -> tuple[DatabaseRuntime, ArtifactFoundationService]:
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    service = ArtifactFoundationService(
        SqlAlchemyArtifactFoundationUnitOfWorkFactory(runtime.session_factory),
        verifier,
    )
    return runtime, service


def test_allocation_is_atomic_approved_only_and_replay_safe() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    command = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
    )

    async def scenario() -> None:
        runtime, service = await _service(
            FakeManifestVerifier(
                storage_ref="private manifest reference v1",
                artifact_hash="sha256:" + "5" * 64,
            )
        )
        try:
            created = await service.allocate(command)
            replayed = await service.allocate(command)
            assert created.replayed is False
            assert replayed.replayed is True
            assert replayed.allocation == created.allocation
            assert created.allocation.version.version_no == 1
            assert created.allocation.version.parent_version_id is None
        finally:
            await runtime.close()

    asyncio.run(scenario())
    counts = asyncio.run(
        _execute(
            "SELECT (SELECT count(*) FROM artifacts) AS artifacts, "
            "(SELECT count(*) FROM artifact_versions) AS versions, "
            "(SELECT count(*) FROM jobs) AS jobs, "
            "(SELECT count(*) FROM outbox_events) AS events"
        )
    ).one()
    assert tuple(counts) == (1, 1, 1, 1)

    unapproved_user, unapproved_account, unapproved_project, unapproved_scope = asyncio.run(
        _seed(scope_status="awaiting_approval")
    )
    rejected = _command(
        user_id=unapproved_user,
        account_id=unapproved_account,
        project_id=unapproved_project,
        scope_version_id=unapproved_scope,
    )

    async def reject() -> None:
        runtime, service = await _service(FakeManifestVerifier())
        try:
            with pytest.raises(ArtifactScopeNotEligible):
                await service.allocate(rejected)
        finally:
            await runtime.close()

    asyncio.run(reject())
    rejected_count = asyncio.run(
        _execute(
            "SELECT count(*) FROM artifact_versions WHERE project_id=:project",
            {"project": unapproved_project},
        )
    ).scalar_one()
    assert rejected_count == 0


def test_concurrent_initial_allocation_creates_one_artifact_and_version() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    artifact_id = uuid4()
    first = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
        artifact_id=artifact_id,
    )
    second = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
        artifact_id=artifact_id,
    )

    async def scenario() -> list[object]:
        first_runtime, first_service = await _service(FakeManifestVerifier())
        second_runtime, second_service = await _service(FakeManifestVerifier())
        try:
            return list(
                await asyncio.gather(
                    first_service.allocate(first),
                    second_service.allocate(second),
                    return_exceptions=True,
                )
            )
        finally:
            await first_runtime.close()
            await second_runtime.close()

    results = asyncio.run(scenario())
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ArtifactAllocationConflict) for result in results) == 1
    counts = asyncio.run(
        _execute(
            "SELECT (SELECT count(*) FROM artifacts) AS artifacts, "
            "(SELECT count(*) FROM artifact_versions) AS versions"
        )
    ).one()
    assert tuple(counts) == (1, 1)


def test_concurrent_revision_allocation_allows_only_one_active_generation() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    initial = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
    )

    async def prepare_initial() -> None:
        runtime, service = await _service(FakeManifestVerifier())
        try:
            await service.allocate(initial)
            await _execute(
                "UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP "
                "WHERE id=:id",
                {"id": initial.job.id},
            )
            await service.finalize(
                FinalizeArtifactVersionCommand(
                    account_id=account_id,
                    project_id=project_id,
                    artifact_version_id=initial.artifact_version_id,
                    generation_job_id=initial.job.id,
                )
            )
        finally:
            await runtime.close()

    asyncio.run(prepare_initial())
    first_revision = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
        artifact_id=initial.artifact_id,
        trigger_type="prompt_edit",
    )
    second_revision = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
        artifact_id=initial.artifact_id,
        trigger_type="feedback_revision",
    )

    async def allocate_revisions() -> list[object]:
        first_runtime, first_service = await _service(FakeManifestVerifier())
        second_runtime, second_service = await _service(FakeManifestVerifier())
        try:
            return list(
                await asyncio.gather(
                    first_service.allocate(first_revision),
                    second_service.allocate(second_revision),
                    return_exceptions=True,
                )
            )
        finally:
            await first_runtime.close()
            await second_runtime.close()

    results = asyncio.run(allocate_revisions())
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ArtifactAllocationConflict) for result in results) == 1
    rows = asyncio.run(
        _execute(
            "SELECT version_no, parent_version_id FROM artifact_versions "
            "WHERE artifact_id=:artifact ORDER BY version_no",
            {"artifact": initial.artifact_id},
        )
    ).all()
    assert [row.version_no for row in rows] == [1, 2]
    assert rows[0].parent_version_id is None
    assert rows[1].parent_version_id == initial.artifact_version_id


def test_finalization_is_atomic_idempotent_and_recovery_uses_same_identity() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    allocation_command = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
    )
    verifier = FakeManifestVerifier()

    async def allocate() -> None:
        runtime, service = await _service(verifier)
        try:
            await service.allocate(allocation_command)
        finally:
            await runtime.close()

    asyncio.run(allocate())
    asyncio.run(
        _execute(
            "UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=:id",
            {"id": allocation_command.job.id},
        )
    )
    asyncio.run(
        _execute(
            "CREATE FUNCTION public.fail_0099_artifact_finalize() RETURNS trigger "
            "LANGUAGE plpgsql SET search_path='' AS $aria$ BEGIN "
            "RAISE EXCEPTION '0099 finalization fault'; END $aria$"
        )
    )
    asyncio.run(
        _execute(
            "CREATE TRIGGER trg_0099_finalization_fault "
            "BEFORE UPDATE ON public.artifacts FOR EACH ROW "
            "EXECUTE FUNCTION public.fail_0099_artifact_finalize()"
        )
    )
    finalize = FinalizeArtifactVersionCommand(
        account_id=account_id,
        project_id=project_id,
        artifact_version_id=allocation_command.artifact_version_id,
        generation_job_id=allocation_command.job.id,
    )

    async def fail_then_recover() -> None:
        runtime, service = await _service(verifier)
        try:
            with pytest.raises(ArtifactRepositoryError):
                await service.finalize(finalize)
        finally:
            await runtime.close()
        failed_state = (
            await _execute(
                "SELECT av.status AS version_status, a.current_version_id, j.status AS job_status "
                "FROM artifact_versions av JOIN artifacts a ON a.id=av.artifact_id "
                "JOIN jobs j ON j.id=av.generation_job_id WHERE av.id=:id",
                {"id": allocation_command.artifact_version_id},
            )
        ).one()
        assert tuple(failed_state) == ("queued", None, "running")
        await _execute("DROP TRIGGER trg_0099_finalization_fault ON public.artifacts")
        await _execute("DROP FUNCTION public.fail_0099_artifact_finalize()")

        recovery_runtime, recovery_service = await _service(verifier)
        try:
            recovered = await recovery_service.finalize(finalize)
            replayed = await recovery_service.finalize(finalize)
            assert recovered == replayed
            assert recovered.version.id == allocation_command.artifact_version_id
            assert recovered.version.generation_job_id == allocation_command.job.id
            assert recovered.artifact.current_version_id == recovered.version.id
        finally:
            await recovery_runtime.close()

    asyncio.run(fail_then_recover())
    assert verifier.calls == [
        allocation_command.artifact_version_id,
        allocation_command.artifact_version_id,
        allocation_command.artifact_version_id,
    ]


def test_invalid_manifest_and_database_ownership_guards_fail_closed() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    allocation_command = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
    )

    async def scenario() -> None:
        runtime, service = await _service(FakeManifestVerifier(valid=False))
        try:
            await service.allocate(allocation_command)
            with pytest.raises(ArtifactManifestInvalid):
                await service.finalize(
                    FinalizeArtifactVersionCommand(
                        account_id=account_id,
                        project_id=project_id,
                        artifact_version_id=allocation_command.artifact_version_id,
                        generation_job_id=allocation_command.job.id,
                    )
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE artifacts SET current_version_id=:version WHERE id=:artifact",
                {
                    "version": allocation_command.artifact_version_id,
                    "artifact": allocation_command.artifact_id,
                },
            )
        )
    other_account = uuid4()
    asyncio.run(_execute("INSERT INTO accounts (id) VALUES (:id)", {"id": other_account}))
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "INSERT INTO artifacts (account_id, project_id, artifact_type) "
                "VALUES (:account, :project, 'website')",
                {"account": other_account, "project": project_id},
            )
        )


def test_current_and_parent_cannot_reference_another_artifact() -> None:
    first_user, first_account, first_project, first_scope = asyncio.run(_seed())
    second_user, second_account, second_project, second_scope = asyncio.run(_seed())
    first = _command(
        user_id=first_user,
        account_id=first_account,
        project_id=first_project,
        scope_version_id=first_scope,
    )
    second = _command(
        user_id=second_user,
        account_id=second_account,
        project_id=second_project,
        scope_version_id=second_scope,
    )

    async def allocate_and_finalize(
        command: AllocateArtifactCommand,
        *,
        manifest_hash: str,
    ) -> None:
        runtime, service = await _service(
            FakeManifestVerifier(artifact_hash=manifest_hash)
        )
        try:
            await service.allocate(command)
            await _execute(
                "UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP "
                "WHERE id=:id",
                {"id": command.job.id},
            )
            await service.finalize(
                FinalizeArtifactVersionCommand(
                    account_id=command.account_id,
                    project_id=command.project_id,
                    artifact_version_id=command.artifact_version_id,
                    generation_job_id=command.job.id,
                )
            )
        finally:
            await runtime.close()

    asyncio.run(
        allocate_and_finalize(first, manifest_hash="sha256:" + "6" * 64)
    )
    asyncio.run(
        allocate_and_finalize(second, manifest_hash="sha256:" + "7" * 64)
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE artifacts SET current_version_id=:foreign_version WHERE id=:id",
                {
                    "foreign_version": second.artifact_version_id,
                    "id": first.artifact_id,
                },
            )
        )

    invalid_job_id = uuid4()
    asyncio.run(
        _execute(
            "INSERT INTO jobs "
            "(id, account_id, project_id, job_type, status, payload_ref, "
            "attempt_count, max_attempts, correlation_id, available_at) "
            "VALUES (:id, :account, :project, 'web_generation', 'queued', '{}'::jsonb, "
            "0, 1, :correlation, CURRENT_TIMESTAMP)",
            {
                "id": invalid_job_id,
                "account": first_account,
                "project": first_project,
                "correlation": uuid4(),
            },
        )
    )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "INSERT INTO artifact_versions "
                "(id, account_id, project_id, artifact_id, scope_version_id, "
                "version_no, parent_version_id, schema_name, schema_version, "
                "trigger_type, status, created_by, generation_job_id) "
                "VALUES (:id, :account, :project, :artifact, :scope, 2, :foreign_parent, "
                "'generation_ast_schema', 'v1', 'prompt_edit', 'queued', :creator, :job)",
                {
                    "id": uuid4(),
                    "account": first_account,
                    "project": first_project,
                    "artifact": first.artifact_id,
                    "scope": first_scope,
                    "foreign_parent": second.artifact_version_id,
                    "creator": first_user,
                    "job": invalid_job_id,
                },
            )
        )


def test_ready_version_is_immutable_historical_and_rls_protected() -> None:
    user_id, account_id, project_id, scope_version_id = asyncio.run(_seed())
    allocation_command = _command(
        user_id=user_id,
        account_id=account_id,
        project_id=project_id,
        scope_version_id=scope_version_id,
    )

    async def scenario() -> None:
        runtime, service = await _service(
            FakeManifestVerifier(artifact_hash="sha256:" + "3" * 64)
        )
        try:
            await service.allocate(allocation_command)
            await _execute(
                "UPDATE jobs SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=:id",
                {"id": allocation_command.job.id},
            )
            await service.finalize(
                FinalizeArtifactVersionCommand(
                    account_id=account_id,
                    project_id=project_id,
                    artifact_version_id=allocation_command.artifact_version_id,
                    generation_job_id=allocation_command.job.id,
                )
            )
        finally:
            await runtime.close()

    asyncio.run(scenario())
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE artifact_versions SET artifact_hash=:hash WHERE id=:id",
                {
                    "hash": "sha256:" + "4" * 64,
                    "id": allocation_command.artifact_version_id,
                },
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "UPDATE artifacts SET current_version_id=NULL, status='draft' WHERE id=:id",
                {"id": allocation_command.artifact_id},
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "DELETE FROM artifact_versions WHERE id=:id",
                {"id": allocation_command.artifact_version_id},
            )
        )
    with pytest.raises(DBAPIError):
        asyncio.run(
            _execute(
                "DELETE FROM artifacts WHERE id=:id",
                {"id": allocation_command.artifact_id},
            )
        )
    row = asyncio.run(
        _execute(
            "SELECT count(*) FILTER (WHERE c.relrowsecurity) AS rls_tables, "
            "(SELECT count(*) FROM information_schema.role_table_grants g "
            "WHERE g.table_schema='public' AND g.table_name IN ('artifacts','artifact_versions') "
            "AND g.grantee IN ('anon','authenticated')) AS data_api_grants "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname IN ('artifacts','artifact_versions')"
        )
    ).one()
    assert (row.rls_tables, row.data_api_grants) == (2, 0)
