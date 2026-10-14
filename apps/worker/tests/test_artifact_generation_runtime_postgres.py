from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.artifact_generation_runtime import (
    ArtifactBuildFile,
    ArtifactGenerationError,
    ArtifactGenerationMessage,
    ArtifactGenerationRuntime,
    StoredObject,
    digest,
)
from app.infrastructure.db.artifact_generation_runtime import (
    PostgresArtifactGenerationJobStore,
)
from app.infrastructure.synthetic_artifact_candidate import (
    VersionedSyntheticArtifactCandidateSource,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL integration evidence",
)


@dataclass(frozen=True, slots=True)
class _Fixture:
    user_id: UUID
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    job_id: UUID
    outbox_event_id: UUID


class _MemoryStorage:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def create_or_verify(self, key: str, content: bytes) -> StoredObject:
        existing = self.values.get(key)
        if existing is not None and existing != content:
            raise ArtifactGenerationError("ARTIFACT_STORAGE_CONFLICT")
        self.values.setdefault(key, content)
        return StoredObject(key, digest(content))


class _Builder:
    def __init__(self) -> None:
        self.calls = 0

    async def build(
        self, canonical_ast: Mapping[str, object]
    ) -> tuple[ArtifactBuildFile, ...]:
        self.calls += 1
        assert canonical_ast["schema_version"] == "generation_ast_schema_v1"
        return (
            ArtifactBuildFile(
                "index.html", "text/html; charset=utf-8", b"<main>synthetic</main>"
            ),
        )


def _database_url() -> str:
    assert TEST_DATABASE_URL is not None
    value = TEST_DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _engine(*, worker: bool = False) -> AsyncEngine:
    options: dict[str, object] = {"poolclass": NullPool}
    if worker:
        options["connect_args"] = {"server_settings": {"role": "aria_worker"}}
    return create_async_engine(_database_url(), **options)  # type: ignore[arg-type]


async def _seed(engine: AsyncEngine, *, truncate: bool = True) -> _Fixture:
    fixture = _Fixture(*(uuid4() for _ in range(8)))
    async with engine.begin() as connection:
        if truncate:
            await connection.execute(text("TRUNCATE public.accounts CASCADE"))
        await connection.execute(
            text("INSERT INTO public.profiles (user_id) VALUES (:id)"),
            {"id": fixture.user_id},
        )
        await connection.execute(
            text("INSERT INTO public.accounts (id) VALUES (:id)"),
            {"id": fixture.account_id},
        )
        await connection.execute(
            text(
                "INSERT INTO public.projects "
                "(id, account_id, owner_id, title, project_type, current_context_version) "
                "VALUES (:id, :account, :owner, 'Synthetic Artifact', 'landing', 1)"
            ),
            {
                "id": fixture.project_id,
                "account": fixture.account_id,
                "owner": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO public.scope_versions "
                "(id, account_id, project_id, version_no, context_version, status, "
                "snapshot_data, snapshot_hash, created_by) "
                "VALUES (:id, :account, :project, 1, 1, 'approved', '{}'::jsonb, "
                ":hash, :creator)"
            ),
            {
                "id": fixture.scope_version_id,
                "account": fixture.account_id,
                "project": fixture.project_id,
                "hash": "sha256:" + "0" * 64,
                "creator": fixture.user_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO public.artifacts "
                "(id, account_id, project_id, artifact_type, status) "
                "VALUES (:id, :account, :project, 'website', 'draft')"
            ),
            {
                "id": fixture.artifact_id,
                "account": fixture.account_id,
                "project": fixture.project_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO public.jobs "
                "(id, account_id, project_id, job_type, status, payload_ref, "
                "attempt_count, max_attempts, correlation_id, available_at) "
                "VALUES (:id, :account, :project, 'artifact_generation', 'queued', "
                "CAST(:payload AS jsonb), 0, 1, :correlation, CURRENT_TIMESTAMP)"
            ),
            {
                "id": fixture.job_id,
                "account": fixture.account_id,
                "project": fixture.project_id,
                "payload": json.dumps(
                    {
                        "artifact_version_id": str(fixture.artifact_version_id),
                        "scope_version_id": str(fixture.scope_version_id),
                    }
                ),
                "correlation": uuid4(),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO public.artifact_versions "
                "(id, account_id, project_id, artifact_id, scope_version_id, "
                "version_no, parent_version_id, schema_name, schema_version, "
                "trigger_type, status, created_by, generation_job_id) "
                "VALUES (:id, :account, :project, :artifact, :scope, 1, NULL, "
                "'generation_ast_schema', 'v1', 'initial', 'queued', :creator, :job)"
            ),
            {
                "id": fixture.artifact_version_id,
                "account": fixture.account_id,
                "project": fixture.project_id,
                "artifact": fixture.artifact_id,
                "scope": fixture.scope_version_id,
                "creator": fixture.user_id,
                "job": fixture.job_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO public.outbox_events "
                "(id, account_id, aggregate_type, aggregate_id, event_type, "
                "delivery_channel, payload, status, attempt_count, available_at) "
                "VALUES (:id, :account, 'artifact_version', :version, "
                "'artifact.generation_requested.v1', 'job_queue', "
                "CAST(:payload AS jsonb), 'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {
                "id": fixture.outbox_event_id,
                "account": fixture.account_id,
                "version": fixture.artifact_version_id,
                "payload": json.dumps(
                    {
                        "jobId": str(fixture.job_id),
                        "taskType": "artifact_generation",
                        "payloadVersion": "1",
                    }
                ),
            },
        )
    return fixture


def _message(fixture: _Fixture) -> ArtifactGenerationMessage:
    return ArtifactGenerationMessage(
        "1", fixture.outbox_event_id, fixture.job_id
    )


def test_runtime_finalizes_once_and_replay_is_a_no_op_under_worker_role() -> None:
    async def scenario() -> None:
        owner, worker = _engine(), _engine(worker=True)
        try:
            fixture = await _seed(owner)
            builder, storage = _Builder(), _MemoryStorage()
            runtime = ArtifactGenerationRuntime(
                store=PostgresArtifactGenerationJobStore(worker),
                candidate_source=VersionedSyntheticArtifactCandidateSource(
                    repository_root=ROOT
                ),
                builder=builder,
                storage=storage,
            )
            first = await runtime.execute(_message(fixture))
            replay = await runtime.execute(_message(fixture))
            assert first.status == "succeeded"
            assert replay.status == "already_completed"
            assert builder.calls == 1

            async with owner.connect() as connection:
                state = (
                    await connection.execute(
                        text(
                            "SELECT av.status, av.checkpoint_ref, av.artifact_hash, "
                            "a.current_version_id, j.status AS job_status "
                            "FROM public.artifact_versions av "
                            "JOIN public.artifacts a ON a.id=av.artifact_id "
                            "JOIN public.jobs j ON j.id=av.generation_job_id "
                            "WHERE av.id=:id"
                        ),
                        {"id": fixture.artifact_version_id},
                    )
                ).one()
                claims = await connection.scalar(
                    text(
                        "SELECT count(*) FROM aria_internal.artifact_generation_claims"
                    )
                )
            assert state.status == "ready"
            assert state.checkpoint_ref.endswith("/checkpoint/build-bundle.tar")
            assert state.artifact_hash == first.artifact_hash
            assert state.current_version_id == fixture.artifact_version_id
            assert state.job_status == "succeeded"
            assert claims == 0
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_mismatched_event_concurrency_and_unowned_finalization_fail_closed() -> None:
    async def scenario() -> None:
        owner, first_worker, second_worker = (
            _engine(), _engine(worker=True), _engine(worker=True)
        )
        first_store = PostgresArtifactGenerationJobStore(first_worker)
        fixture: _Fixture | None = None
        try:
            fixture = await _seed(owner)
            bad_message = ArtifactGenerationMessage(
                "1", uuid4(), fixture.job_id
            )
            with pytest.raises(ArtifactGenerationError) as mismatch:
                await first_store.prepare(bad_message)
            assert mismatch.value.reason_code == "ARTIFACT_GENERATION_MESSAGE_INVALID"

            claimed = await first_store.prepare(_message(fixture))
            second_store = PostgresArtifactGenerationJobStore(second_worker)
            with pytest.raises(ArtifactGenerationError) as concurrent:
                await second_store.prepare(_message(fixture))
            assert concurrent.value.reason_code == "ARTIFACT_GENERATION_IN_PROGRESS"

            prefix = (
                f"artifacts/{fixture.account_id}/{fixture.project_id}/"
                f"{fixture.artifact_id}/versions/{fixture.artifact_version_id}"
            )
            async with second_worker.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            "SELECT aria_internal.finalize_artifact_generation("
                            ":job, :event, :ref, :hash)"
                        ),
                        {
                            "job": fixture.job_id,
                            "event": fixture.outbox_event_id,
                            "ref": prefix + "/manifest.json",
                            "hash": "sha256:" + "1" * 64,
                        },
                    )
                await transaction.rollback()
            async with second_worker.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            "UPDATE public.artifact_versions SET status='failed' "
                            "WHERE id=:id"
                        ),
                        {"id": fixture.artifact_version_id},
                    )
                await transaction.rollback()
            await first_store.release(_message(fixture))
            assert claimed.artifact_version_id == fixture.artifact_version_id
        finally:
            if fixture is not None:
                await first_store.release(_message(fixture))
            await second_worker.dispose()
            await first_worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_cross_tenant_job_event_pair_is_rejected_without_content_disclosure() -> None:
    async def scenario() -> None:
        owner, worker = _engine(), _engine(worker=True)
        try:
            first = await _seed(owner)
            second = await _seed(owner, truncate=False)
            store = PostgresArtifactGenerationJobStore(worker)
            with pytest.raises(ArtifactGenerationError) as rejected:
                await store.prepare(
                    ArtifactGenerationMessage(
                        "1", second.outbox_event_id, first.job_id
                    )
                )
            assert rejected.value.reason_code == "ARTIFACT_GENERATION_MESSAGE_INVALID"
            assert str(first.account_id) not in str(rejected.value)
            assert str(second.account_id) not in str(rejected.value)
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())


def test_wrong_event_and_cross_project_scope_mutation_are_rejected() -> None:
    async def scenario() -> None:
        owner, worker = _engine(), _engine(worker=True)
        try:
            first = await _seed(owner)
            second = await _seed(owner, truncate=False)
            async with owner.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE public.outbox_events SET event_type='wrong.event.v1' "
                        "WHERE id=:id"
                    ),
                    {"id": first.outbox_event_id},
                )
            store = PostgresArtifactGenerationJobStore(worker)
            with pytest.raises(ArtifactGenerationError) as wrong_event:
                await store.prepare(_message(first))
            assert wrong_event.value.reason_code == "ARTIFACT_GENERATION_MESSAGE_INVALID"

            async with owner.connect() as connection:
                transaction = await connection.begin()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            "UPDATE public.artifact_versions SET scope_version_id=:scope "
                            "WHERE id=:version"
                        ),
                        {
                            "scope": second.scope_version_id,
                            "version": first.artifact_version_id,
                        },
                    )
                await transaction.rollback()
        finally:
            await worker.dispose()
            await owner.dispose()

    asyncio.run(scenario())
