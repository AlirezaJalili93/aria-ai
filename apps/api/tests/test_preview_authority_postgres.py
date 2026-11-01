"""0102 SQL authority gate using an actual aria_worker login, never DB-owner execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from aria_backend_application.preview_delivery import PreviewError
from sqlalchemy import make_url, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from test_artifact_foundation_postgres import (
    TEST_DATABASE_URL,
    FakeManifestVerifier,
    _command,
    _seed,
)
from test_artifact_foundation_postgres import (
    clean_artifact_schema as clean_artifact_schema,
)

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.generation.application.ports import FinalizeArtifactVersionCommand
from app.modules.generation.application.preview import PreviewPublicationService
from app.modules.generation.application.service import ArtifactFoundationService
from app.modules.generation.infrastructure.preview_repository import PostgresPreviewCommands
from app.modules.generation.infrastructure.repository import (
    SqlAlchemyArtifactFoundationUnitOfWorkFactory,
)
from app.modules.identity.application.tenant_context import TenantContext

pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Throwaway PostgreSQL required")


@dataclass(frozen=True)
class Binding:
    context: TenantContext
    project: UUID
    version: UUID
    publication: UUID
    representation: UUID
    job: UUID
    event: UUID

    @property
    def manifest_ref(self) -> str:
        return (
            f"preview/{self.context.account_id}/{self.project}/{self.version}/"
            f"{self.representation}/delivery-manifest.json"
        )


def engine(*, worker: bool = False) -> AsyncEngine:
    assert TEST_DATABASE_URL is not None
    url = make_url(TEST_DATABASE_URL)
    if worker:
        url = url.set(username="aria_worker", password=None)
    return create_async_engine(url, poolclass=NullPool)


async def allocated() -> Binding:
    assert TEST_DATABASE_URL is not None
    user, account, project, scope = await _seed()
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        command = _command(
            user_id=user, account_id=account, project_id=project, scope_version_id=scope
        )
        foundation = ArtifactFoundationService(
            SqlAlchemyArtifactFoundationUnitOfWorkFactory(runtime.session_factory),
            FakeManifestVerifier(),
        )
        await foundation.allocate(command)
        await foundation.finalize(
            FinalizeArtifactVersionCommand(
                account_id=account,
                project_id=project,
                artifact_version_id=command.artifact_version_id,
                generation_job_id=command.job.id,
            )
        )
        actor = TenantContext(user, account, uuid4(), "owner", "active")
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory),
            synthetic_sources=frozenset({(command.artifact_version_id, "sha256:" + "1" * 64)}),
        )
        result = await service.publish(
            actor,
            project_id=project,
            artifact_version_id=command.artifact_version_id,
            key="publish",
        )
        async with runtime.engine.connect() as conn:
            rep = await conn.scalar(
                text("SELECT representation_id FROM preview_publications WHERE id=:id"),
                {"id": result.publication_id},
            )
            event = await conn.scalar(
                text("SELECT id FROM outbox_events WHERE aggregate_id=:id"), {"id": result.job_id}
            )
        return Binding(
            actor,
            project,
            command.artifact_version_id,
            result.publication_id,
            rep,
            result.job_id,
            event,
        )
    finally:
        await runtime.close()


async def claim(conn: AsyncConnection, binding: Binding, *, event: UUID | None = None):
    return await conn.scalar(
        text("SELECT aria_internal.claim_preview(:job, :event)"),
        {"job": binding.job, "event": event or binding.event},
    )


async def finalize(conn: AsyncConnection, binding: Binding) -> None:
    await conn.execute(
        text("SELECT aria_internal.finalize_preview(:job, :event, :ref, :hash)"),
        {
            "job": binding.job,
            "event": binding.event,
            "ref": binding.manifest_ref,
            "hash": "sha256:" + "2" * 64,
        },
    )


async def release(conn: AsyncConnection, binding: Binding, *, event: UUID | None = None) -> None:
    await conn.execute(
        text("SELECT aria_internal.release_preview(:job, :event)"),
        {"job": binding.job, "event": event or binding.event},
    )


async def states(owner: AsyncEngine, binding: Binding) -> tuple[str, str, str]:
    async with owner.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT r.status, p.status, j.status FROM preview_publications p "
                    "JOIN preview_representations r ON r.id=p.representation_id "
                    "JOIN jobs j ON j.id=p.publish_job_id WHERE p.id=:id"
                ),
                {"id": binding.publication},
            )
        ).one()
        return tuple(row)


def test_helper_owner_security_and_runtime_principal() -> None:
    async def scenario() -> None:
        owner, worker = engine(), engine(worker=True)
        try:
            async with worker.connect() as conn:
                assert (await conn.execute(text("SELECT session_user, current_user"))).one() == (
                    "aria_worker",
                    "aria_worker",
                )
            async with owner.connect() as conn:
                flags = (
                    await conn.execute(
                        text(
                            "SELECT rolcanlogin, rolinherit, rolsuper, rolbypassrls, rolcreatedb, "
                            "rolcreaterole, rolreplication FROM pg_roles "
                            "WHERE rolname='aria_preview_runtime_owner'"
                        )
                    )
                ).one()
                assert tuple(flags) == (False,) * 7
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner "
                            "WHERE r.rolname='aria_preview_runtime_owner'"
                        )
                    )
                    == 0
                )
                functions = (
                    await conn.execute(
                        text(
                            "SELECT p.oid, p.prosecdef, p.proconfig, r.rolname FROM pg_proc p "
                            "JOIN pg_namespace n ON n.oid=p.pronamespace "
                            "JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname='aria_internal' "
                            "AND p.proname IN ('claim_preview','finalize_preview',"
                            "'release_preview','resolve_preview')"
                        )
                    )
                ).all()
                assert len(functions) == 4
                for oid, definer, config, name in functions:
                    assert definer and config == ['search_path=""']
                    assert name == "aria_preview_runtime_owner"
                    assert await conn.scalar(
                        text(
                            "SELECT has_function_privilege('aria_worker', "
                            "CAST(:oid AS oid), 'EXECUTE')"
                        ),
                        {"oid": oid},
                    )
                    assert not await conn.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_proc p, "
                            "LATERAL aclexplode(p.proacl) a WHERE p.oid=CAST(:oid AS oid) "
                            "AND a.grantee=0 AND a.privilege_type='EXECUTE')"
                        ),
                        {"oid": oid},
                    )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE c.relname IN ('preview_representations','preview_publications',"
                            "'preview_execution_claims') AND c.relrowsecurity "
                            "AND n.nspname IN ('public','aria_internal')"
                        )
                    )
                    == 3
                )
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "relation",
    [
        "public.preview_publications",
        "public.preview_representations",
        "aria_internal.preview_execution_claims",
    ],
)
@pytest.mark.parametrize("operation", ["SELECT", "INSERT", "UPDATE", "DELETE"])
def test_worker_direct_access_denied(relation: str, operation: str) -> None:
    async def scenario() -> None:
        worker = engine(worker=True)
        statements = {
            "SELECT": f"SELECT * FROM {relation}",
            "INSERT": f"INSERT INTO {relation} DEFAULT VALUES",
            "UPDATE": f"UPDATE {relation} SET job_id=job_id"
            if "claims" in relation
            else f"UPDATE {relation} SET status=status",
            "DELETE": f"DELETE FROM {relation}",
        }
        try:
            async with worker.begin() as conn:
                with pytest.raises(DBAPIError) as caught:
                    await conn.execute(text(statements[operation]))
                assert caught.value.orig.sqlstate == "42501"
        finally:
            await worker.dispose()

    asyncio.run(scenario())


def test_claim_finalize_replay_and_release_as_worker() -> None:
    async def scenario() -> None:
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    result = await claim(conn, binding)
                    assert not result["already_completed"]
                    assert result["account_id"] == str(binding.context.account_id)
                assert await states(owner, binding) == ("preparing", "publishing", "running")
                async with conn.begin():
                    await finalize(conn, binding)
                assert await states(owner, binding) == ("ready", "ready", "succeeded")
                async with conn.begin():
                    await release(conn, binding)
                    await release(conn, binding)
                async with conn.begin():
                    assert (await claim(conn, binding))["already_completed"]
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_cross_bound_job_event_denied_without_state_change() -> None:
    async def scenario() -> None:
        first, second = await allocated(), await allocated()
        owner, worker = engine(), engine(worker=True)
        try:
            assert first.context.account_id != second.context.account_id
            async with worker.begin() as conn:
                with pytest.raises(DBAPIError) as caught:
                    await claim(conn, first, event=second.event)
                assert caught.value.orig.sqlstate == "42501"
            assert await states(owner, first) == ("allocated", "allocated", "queued")
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_concurrent_claim_and_wrong_event_release_cannot_steal_execution() -> None:
    async def scenario() -> None:
        binding, worker = await allocated(), engine(worker=True)
        try:
            async with worker.connect() as first, worker.connect() as second:
                async with first.begin():
                    await claim(first, binding)
                async with first.begin():
                    await release(first, binding, event=uuid4())
                async with second.begin():
                    with pytest.raises(DBAPIError) as caught:
                        await claim(second, binding)
                    assert caught.value.orig.sqlstate == "55P03"
                async with first.begin():
                    await release(first, binding)
                async with second.begin():
                    await claim(second, binding)
                async with second.begin():
                    await release(second, binding)
        finally:
            await worker.dispose()

    asyncio.run(scenario())


def test_finalization_rollback_is_atomic_and_same_claim_can_finalize() -> None:
    async def scenario() -> None:
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                with pytest.raises(RuntimeError, match="synthetic rollback"):
                    async with conn.begin():
                        await finalize(conn, binding)
                        raise RuntimeError("synthetic rollback")
                assert await states(owner, binding) == ("preparing", "publishing", "running")
                async with conn.begin():
                    await finalize(conn, binding)
                    await release(conn, binding)
                assert await states(owner, binding) == ("ready", "ready", "succeeded")
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_worker_backend_death_reclaims_same_running_job() -> None:
    async def scenario() -> None:
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        try:
            async with worker.connect() as first:
                async with first.begin():
                    await claim(first, binding)
                    pid = await first.scalar(text("SELECT pg_backend_pid()"))
                async with owner.begin() as conn:
                    assert await conn.scalar(
                        text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
                    )
            async with worker.connect() as second:
                async with second.begin():
                    assert not (await claim(second, binding))["already_completed"]
                async with second.begin():
                    await finalize(second, binding)
                    await release(second, binding)
            assert await states(owner, binding) == ("ready", "ready", "succeeded")
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_revoke_blocks_inflight_finalization() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                await service.revoke(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="revoke",
                )
                async with conn.begin():
                    with pytest.raises(DBAPIError) as caught:
                        await finalize(conn, binding)
                    assert caught.value.orig.sqlstate == "42501"
                assert await states(owner, binding) == ("preparing", "revoked", "cancelled")
                async with conn.begin():
                    await release(conn, binding)
        finally:
            await runtime.close()
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("initial", ["queued", "running", "failed", "succeeded"])
def test_revoke_cancels_only_active_job_and_replay_preserves_terminal_time(initial: str) -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        now = datetime.now(UTC)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory),
            synthetic_sources=frozenset(),
            clock=lambda: now,
        )
        try:
            async with worker.connect() as conn:
                if initial != "queued":
                    async with conn.begin():
                        await claim(conn, binding)
                if initial == "succeeded":
                    async with conn.begin():
                        await finalize(conn, binding)
                if initial == "failed":
                    async with conn.begin():
                        await conn.execute(
                            text("SELECT aria_internal.fail_preview(:job, :event, :code)"),
                            {
                                "job": binding.job,
                                "event": binding.event,
                                "code": "PREVIEW_SOURCE_INVALID",
                            },
                        )
                async with owner.connect() as reader:
                    previous = (
                        await reader.execute(
                            text("SELECT finished_at, error_code FROM jobs WHERE id=:id"),
                            {"id": binding.job},
                        )
                    ).one()
                await service.revoke(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="cancel-preview",
                )
                expected = "cancelled" if initial in {"queued", "running"} else initial
                assert (await states(owner, binding))[1:] == ("revoked", expected)
                async with owner.connect() as reader:
                    after = (
                        await reader.execute(
                            text("SELECT finished_at, error_code FROM jobs WHERE id=:id"),
                            {"id": binding.job},
                        )
                    ).one()
                if expected == "cancelled":
                    assert after == (now, None)
                else:
                    assert after == previous
                now += timedelta(minutes=1)
                await service.revoke(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="cancel-preview",
                )
                async with owner.connect() as reader:
                    assert (
                        await reader.execute(
                            text("SELECT finished_at, error_code FROM jobs WHERE id=:id"),
                            {"id": binding.job},
                        )
                    ).one() == after
                    assert (
                        await reader.scalar(
                            text("SELECT count(*) FROM outbox_events WHERE aggregate_id=:id"),
                            {"id": binding.job},
                        )
                        == 1
                    )
                if initial != "queued":
                    async with conn.begin():
                        await release(conn, binding)
                if expected == "cancelled":
                    async with conn.begin():
                        with pytest.raises(DBAPIError) as caught:
                            await claim(conn, binding)
                        assert caught.value.orig.sqlstate == "42501"
        finally:
            await runtime.close()
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_revoke_rollback_keeps_publication_job_and_idempotency_atomic(monkeypatch) -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, owner = await allocated(), engine()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        original = SqlAlchemyIdempotencyRepository.complete

        async def fail_after_persistence(self, **kwargs):
            await original(self, **kwargs)
            await self._session.flush()
            raise RuntimeError("synthetic revoke rollback")

        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        try:
            with monkeypatch.context() as patch:
                patch.setattr(SqlAlchemyIdempotencyRepository, "complete", fail_after_persistence)
                with pytest.raises(RuntimeError, match="synthetic revoke rollback"):
                    await service.revoke(
                        binding.context,
                        project_id=binding.project,
                        publication_id=binding.publication,
                        key="atomic-revoke",
                    )
            assert await states(owner, binding) == ("allocated", "allocated", "queued")
            async with owner.connect() as conn:
                assert (
                    await conn.execute(
                        text("SELECT revoked_at FROM preview_publications WHERE id=:id"),
                        {"id": binding.publication},
                    )
                ).scalar_one() is None
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM idempotency_records WHERE idempotency_key=:key"),
                        {"key": "atomic-revoke"},
                    )
                    == 0
                )
            await service.revoke(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="atomic-revoke",
            )
            assert await states(owner, binding) == ("allocated", "revoked", "cancelled")
        finally:
            await runtime.close()
            await owner.dispose()

    asyncio.run(scenario())


def test_revoke_waits_on_job_not_publication_when_worker_finalizes() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, owner, worker = await allocated(), engine(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        pending = None
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                    pid = await conn.scalar(text("SELECT pg_backend_pid()"))
                async with conn.begin():
                    await conn.execute(
                        text("SELECT id FROM jobs WHERE id=:id FOR UPDATE"), {"id": binding.job}
                    )
                    pending = asyncio.create_task(
                        service.revoke(
                            binding.context,
                            project_id=binding.project,
                            publication_id=binding.publication,
                            key="race-revoke",
                        )
                    )

                    async def wait_for_blocked_revoke():
                        async with owner.connect() as reader:
                            while not await reader.scalar(
                                text(
                                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                    "WHERE :pid = ANY(pg_blocking_pids(pid)))"
                                ),
                                {"pid": pid},
                            ):
                                if pending.done():
                                    await pending
                                    pytest.fail("Revoke completed before Worker released Job lock")
                                await asyncio.sleep(0.01)

                    await asyncio.wait_for(wait_for_blocked_revoke(), 5)
                    await asyncio.wait_for(finalize(conn, binding), 5)
                await asyncio.wait_for(pending, 5)
                assert await states(owner, binding) == ("ready", "revoked", "succeeded")
                async with conn.begin():
                    await release(conn, binding)
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            await runtime.close()
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())


def test_revoke_rejects_job_payload_binding_mismatch() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, owner = await allocated(), engine()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        try:
            async with owner.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE jobs SET payload_ref=jsonb_set(payload_ref, "
                        "'{artifact_version_id}', "
                        "to_jsonb(CAST(:other AS text))) WHERE id=:id"
                    ),
                    {"other": str(uuid4()), "id": binding.job},
                )
            with pytest.raises(PreviewError) as caught:
                await service.revoke(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="wrong-binding",
                )
            assert caught.value.code == "RESOURCE_NOT_FOUND"
            assert await states(owner, binding) == ("allocated", "allocated", "queued")
        finally:
            await runtime.close()
            await owner.dispose()

    asyncio.run(scenario())


def test_capability_issue_replay_hash_only_resolution_and_revoke() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, worker = await allocated(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        now = datetime.now(UTC)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory),
            synthetic_sources=frozenset(),
            clock=lambda: now,
        )
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                async with conn.begin():
                    await finalize(conn, binding)
                    await release(conn, binding)
            first = await service.issue(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="issue",
                expires_at=now + timedelta(hours=1),
            )
            replay = await service.issue(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="issue",
                expires_at=now + timedelta(hours=1),
            )
            assert first.token_available and not replay.token_available and replay.replayed
            assert first.token is not None and len(first.token) == 43
            with pytest.raises(PreviewError, match="IDEMPOTENCY_CONFLICT"):
                await service.issue(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="issue",
                    expires_at=now + timedelta(hours=2),
                )
            with pytest.raises(PreviewError, match="PREVIEW_CAPABILITY_ALREADY_ISSUED"):
                await service.issue(
                    binding.context,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="new-key",
                    expires_at=now + timedelta(hours=1),
                )
            async with runtime.engine.connect() as owner:
                token_hash = await owner.scalar(
                    text("SELECT token_hash FROM preview_publications WHERE id=:id"),
                    {"id": binding.publication},
                )
                safe_replay = await owner.scalar(
                    text(
                        "SELECT response_ref FROM idempotency_records WHERE idempotency_key='issue'"
                    )
                )
                assert safe_replay == {"publication_id": str(binding.publication)}
                assert first.token != token_hash and first.token not in repr(safe_replay)
            async with worker.begin() as conn:
                result = await conn.scalar(
                    text("SELECT aria_internal.resolve_preview(:hash)"), {"hash": token_hash}
                )
                assert result["artifact_version_id"] == str(binding.version)
                assert "token_hash" not in result and first.token not in repr(result)
                assert (
                    await conn.scalar(
                        text("SELECT aria_internal.resolve_preview(:hash)"), {"hash": "0" * 64}
                    )
                    is None
                )
                assert (
                    await conn.scalar(
                        text("SELECT aria_internal.resolve_preview(:hash)"), {"hash": first.token}
                    )
                    is None
                )
            await service.revoke(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="revoke",
            )
            async with worker.begin() as conn:
                assert (
                    await conn.scalar(
                        text("SELECT aria_internal.resolve_preview(:hash)"), {"hash": token_hash}
                    )
                    is None
                )
        finally:
            await runtime.close()
            await worker.dispose()

    asyncio.run(scenario())


def test_expired_capability_denied_by_database_clock_without_mutating_issuance() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, worker = await allocated(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        # Test-only historical issuance clock; creates a naturally expired immutable capability.
        created = datetime.now(UTC) - timedelta(hours=2)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory),
            synthetic_sources=frozenset(),
            clock=lambda: created,
        )
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                async with conn.begin():
                    await finalize(conn, binding)
                    await release(conn, binding)
            await service.issue(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="historical-issue",
                expires_at=created + timedelta(hours=1),
            )
            async with runtime.engine.connect() as conn:
                token_hash = await conn.scalar(
                    text("SELECT token_hash FROM preview_publications WHERE id=:id"),
                    {"id": binding.publication},
                )
            async with worker.begin() as conn:
                assert (
                    await conn.scalar(
                        text("SELECT aria_internal.resolve_preview(:hash)"), {"hash": token_hash}
                    )
                    is None
                )
            later = PreviewPublicationService(
                PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
            )
            replay = await later.issue(
                binding.context,
                project_id=binding.project,
                publication_id=binding.publication,
                key="historical-issue",
                expires_at=created + timedelta(hours=1),
            )
            assert replay.replayed and not replay.token_available
        finally:
            await runtime.close()
            await worker.dispose()

    asyncio.run(scenario())


def test_concurrent_issue_same_key_discloses_exactly_one_token() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding, worker = await allocated(), engine(worker=True)
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        try:
            async with worker.connect() as conn:
                async with conn.begin():
                    await claim(conn, binding)
                async with conn.begin():
                    await finalize(conn, binding)
                    await release(conn, binding)
            expiry = datetime.now(UTC) + timedelta(hours=1)
            results = await asyncio.gather(
                *[
                    service.issue(
                        binding.context,
                        project_id=binding.project,
                        publication_id=binding.publication,
                        key="same-key",
                        expires_at=expiry,
                    )
                    for _ in range(2)
                ]
            )
            assert sum(result.token_available for result in results) == 1
            assert sum(result.replayed for result in results) == 1
            async with runtime.engine.connect() as conn:
                assert (
                    await conn.scalar(
                        text(
                            "SELECT count(*) FROM preview_publications WHERE token_hash IS NOT NULL"
                        )
                    )
                    == 1
                )
        finally:
            await runtime.close()
            await worker.dispose()

    asyncio.run(scenario())


def test_member_cannot_issue_or_revoke_another_members_publication() -> None:
    async def scenario() -> None:
        assert TEST_DATABASE_URL is not None
        binding = await allocated()
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        member = TenantContext(uuid4(), binding.context.account_id, uuid4(), "member", "active")
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=frozenset()
        )
        try:
            async with runtime.engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO profiles (user_id) VALUES (:id)"), {"id": member.subject_id}
                )
            with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
                await service.issue(
                    member,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="member-issue",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
                await service.revoke(
                    member,
                    project_id=binding.project,
                    publication_id=binding.publication,
                    key="member-revoke",
                )
        finally:
            await runtime.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("mutation", ["delete_publication", "delete_representation", "identity"])
def test_database_rejects_hard_delete_and_identity_rebinding(mutation: str) -> None:
    async def scenario() -> None:
        binding, owner = await allocated(), engine()
        statements = {
            "delete_publication": "DELETE FROM preview_publications WHERE id=:id",
            "delete_representation": "DELETE FROM preview_representations WHERE id=:id",
            "identity": "UPDATE preview_publications SET project_id=:other WHERE id=:id",
        }
        target = (
            binding.representation if mutation == "delete_representation" else binding.publication
        )
        try:
            async with owner.begin() as conn:
                with pytest.raises(DBAPIError) as caught:
                    await conn.execute(text(statements[mutation]), {"id": target, "other": uuid4()})
                assert caught.value.orig.sqlstate == "55000"
        finally:
            await owner.dispose()

    asyncio.run(scenario())


def test_active_job_uniqueness_is_database_enforced() -> None:
    async def scenario() -> None:
        binding, owner = await allocated(), engine()
        try:
            async with owner.begin() as conn:
                with pytest.raises(DBAPIError) as caught:
                    await conn.execute(
                        text(
                            "INSERT INTO jobs (id, account_id, project_id, "
                            "job_type, status, payload_ref, "
                            "attempt_count, max_attempts, correlation_id, available_at) "
                            "SELECT :id, account_id, project_id, job_type, status, payload_ref, "
                            "0, 1, :correlation, now() FROM jobs WHERE id=:job"
                        ),
                        {"id": uuid4(), "correlation": uuid4(), "job": binding.job},
                    )
                assert caught.value.orig.sqlstate == "23505"
        finally:
            await owner.dispose()

    asyncio.run(scenario())


def test_anonymous_data_api_roles_have_no_table_or_helper_access() -> None:
    async def scenario() -> None:
        owner = engine()
        try:
            async with owner.begin() as conn:
                await conn.execute(
                    text("""
                    DO $roles$ BEGIN
                      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                        CREATE ROLE anon NOLOGIN;
                      END IF;
                      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                        CREATE ROLE authenticated NOLOGIN;
                      END IF;
                    END; $roles$;
                """)
                )
                for role in ("anon", "authenticated"):
                    for signature in (
                        "aria_internal.claim_preview(uuid,uuid)",
                        "aria_internal.finalize_preview(uuid,uuid,text,text)",
                        "aria_internal.release_preview(uuid,uuid)",
                        "aria_internal.resolve_preview(text)",
                    ):
                        assert not await conn.scalar(
                            text("SELECT has_function_privilege(:role, :signature, 'EXECUTE')"),
                            {"role": role, "signature": signature},
                        )
                    assert not await conn.scalar(
                        text(
                            "SELECT has_table_privilege(:role, "
                            "'public.preview_publications', 'SELECT')"
                        ),
                        {"role": role},
                    )
                assert not await conn.scalar(
                    text("SELECT pg_has_role('aria_worker','aria_preview_runtime_owner','MEMBER')")
                )
        finally:
            await owner.dispose()

    asyncio.run(scenario())


def test_composite_source_fk_rejects_cross_tenant_representation() -> None:
    async def scenario() -> None:
        first, second, owner = await allocated(), await allocated(), engine()
        try:
            async with owner.begin() as conn:
                with pytest.raises(DBAPIError) as caught:
                    await conn.execute(
                        text(
                            "INSERT INTO preview_representations "
                            "(id, account_id, project_id, artifact_id, "
                            "artifact_version_id, source_hash, "
                            "transformer_version, delivery_policy_version, status, created_by) "
                            "SELECT :id, :account, :project, artifact_id, artifact_version_id, "
                            "source_hash, transformer_version, delivery_policy_version, "
                            "'allocated', "
                            ":creator FROM preview_representations WHERE id=:other"
                        ),
                        {
                            "id": uuid4(),
                            "account": first.context.account_id,
                            "project": first.project,
                            "creator": first.context.subject_id,
                            "other": second.representation,
                        },
                    )
                assert caught.value.orig.sqlstate == "23503"
        finally:
            await owner.dispose()

    asyncio.run(scenario())
