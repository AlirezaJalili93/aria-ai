"""Local fixture allocation + actual aria_worker preview preparation, not product orchestration."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from aria_backend_application.preview_delivery import (
    DELIVERY_POLICY_VERSION,
    TRANSFORMER_VERSION,
    PreviewBinding,
    PreviewError,
)
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from test_artifact_generation_runtime_postgres import (
    TEST_DATABASE_URL,
    _MemoryStorage,
    _message,
    _seed,
)

from app.application.artifact_generation_runtime import ArtifactGenerationRuntime
from app.application.preview_access import PreviewAccessService
from app.application.preview_publication_runtime import (
    PreviewPublicationMessage,
    PreviewPublicationRuntime,
)
from app.infrastructure.artifact_builder import FixedNodeArtifactBuilder
from app.infrastructure.db.artifact_generation_runtime import PostgresArtifactGenerationJobStore
from app.infrastructure.db.preview_access import PostgresPreviewCapabilityResolver
from app.infrastructure.db.preview_publication import PostgresPreviewPublicationStore
from app.infrastructure.preview_canonical_validator import FixedNodePreviewCanonicalValidator
from app.infrastructure.preview_storage import LocalSyntheticPreviewStorage
from app.infrastructure.preview_transformer import PreviewTransformer
from app.infrastructure.synthetic_artifact_candidate import (
    VersionedSyntheticArtifactCandidateSource,
)

ROOT = Path(__file__).parents[3]
pytestmark = pytest.mark.skipif(TEST_DATABASE_URL is None, reason="Throwaway PostgreSQL required")


@pytest.mark.parametrize("project_type", ["landing", "corporate", "portfolio"])
@pytest.mark.parametrize("failure_mode", ["none", "copy", "source", "failure_commit"])
def test_real_worker_source_copy_recovery_and_exact_atomic_ready(
    tmp_path, project_type, failure_mode
):
    async def scenario():
        assert TEST_DATABASE_URL is not None
        url = make_url(TEST_DATABASE_URL)
        owner = create_async_engine(url, poolclass=NullPool)
        worker = create_async_engine(
            url.set(username="aria_worker", password=None), poolclass=NullPool
        )
        source = _MemoryStorage()
        try:
            async with worker.connect() as connection:
                assert (
                    await connection.execute(text("SELECT session_user, current_user"))
                ).one() == ("aria_worker", "aria_worker")
            fixture = await _seed(owner)
            async with owner.begin() as connection:
                await connection.execute(
                    text("UPDATE projects SET project_type=:type WHERE id=:id"),
                    {"type": project_type, "id": fixture.project_id},
                )
            generation = ArtifactGenerationRuntime(
                store=PostgresArtifactGenerationJobStore(worker),
                candidate_source=VersionedSyntheticArtifactCandidateSource(repository_root=ROOT),
                builder=FixedNodeArtifactBuilder(repository_root=ROOT),
                storage=source,
            )
            assert (await generation.execute(_message(fixture))).status == "succeeded"
            representation, publication, job, event = (uuid4() for _ in range(4))
            async with owner.begin() as connection:
                source_ref, source_hash = (
                    await connection.execute(
                        text(
                            "SELECT storage_ref, artifact_hash FROM artifact_versions WHERE id=:id"
                        ),
                        {"id": fixture.artifact_version_id},
                    )
                ).one()
                params = {
                    "account": fixture.account_id,
                    "project": fixture.project_id,
                    "artifact": fixture.artifact_id,
                    "version": fixture.artifact_version_id,
                    "creator": fixture.user_id,
                    "rep": representation,
                    "pub": publication,
                    "job": job,
                    "event": event,
                    "hash": source_hash,
                    "transformer": TRANSFORMER_VERSION,
                    "policy": DELIVERY_POLICY_VERSION,
                }
                # Fixture-only atomic allocation. Auth/idempotent Application commands are
                # independently covered by the API suite; this is not an orchestration endpoint.
                await connection.execute(
                    text(
                        "INSERT INTO preview_representations (id,account_id,project_id,artifact_id,"
                        "artifact_version_id,source_hash,transformer_version,delivery_policy_version,"
                        "status,created_by) VALUES "
                        "(:rep,:account,:project,:artifact,:version,:hash,"
                        ":transformer,:policy,'allocated',:creator)"
                    ),
                    params,
                )
                await connection.execute(
                    text(
                        "INSERT INTO jobs (id,account_id,project_id,job_type,status,payload_ref,"
                        "attempt_count,max_attempts,correlation_id,available_at) VALUES "
                        "(:job,:account,:project,'preview_publication','queued',"
                        "CAST(:payload AS jsonb),"
                        "0,1,:job,CURRENT_TIMESTAMP)"
                    ),
                    {
                        **params,
                        "payload": json.dumps(
                            {
                                "publication_id": str(publication),
                                "representation_id": str(representation),
                                "artifact_version_id": str(fixture.artifact_version_id),
                            }
                        ),
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO preview_publications "
                        "(id,account_id,project_id,artifact_version_id,"
                        "representation_id,publish_job_id,status,created_by) VALUES "
                        "(:pub,:account,:project,:version,:rep,:job,'allocated',:creator)"
                    ),
                    params,
                )
                await connection.execute(
                    text(
                        "INSERT INTO outbox_events "
                        "(id,account_id,aggregate_type,aggregate_id,event_type,"
                        "delivery_channel,payload,status,attempt_count,available_at) VALUES "
                        "(:event,:account,'job',:job,'preview.publication_requested.v1','job_queue',"
                        "CAST(:payload AS jsonb),'pending',0,CURRENT_TIMESTAMP)"
                    ),
                    {
                        **params,
                        "payload": json.dumps(
                            {
                                "jobId": str(job),
                                "taskType": "preview_publication",
                                "payloadVersion": "1",
                            }
                        ),
                    },
                )
            binding = PreviewBinding(
                account_id=fixture.account_id,
                project_id=fixture.project_id,
                artifact_id=fixture.artifact_id,
                artifact_version_id=fixture.artifact_version_id,
                version_no=1,
                representation_id=representation,
                source_hash=source_hash,
                source_ref=source_ref,
            )
            destination = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)

            class ControlledStorageFailure:
                def __init__(self):
                    self.failed = failure_mode != "copy"

                async def read(self, key):
                    return await destination.read(key)

                async def create_or_verify(self, key, value):
                    if not self.failed and key.endswith("index.html"):
                        self.failed = True
                        raise OSError("prohibited failure marker")
                    await destination.create_or_verify(key, value)

            transformer = PreviewTransformer(ROOT)

            class ControlledFailureCommit(PostgresPreviewPublicationStore):
                async def finalize_failure(self, failed_job, *, error_code):
                    if failure_mode == "failure_commit" and not getattr(self, "injected", False):
                        self.injected = True
                        held_connection, owned_message, _ = self._held[failed_job.job_id]
                        # Test-only rollback immediately before commit, not an assertion about
                        # an ambiguous network commit. Same-role fixed helper remains authority.
                        async with held_connection.begin():
                            await held_connection.execute(
                                text("SELECT aria_internal.fail_preview(:job,:event,:code)"),
                                {
                                    "job": failed_job.job_id,
                                    "event": owned_message.outbox_event_id,
                                    "code": error_code,
                                },
                            )
                            raise RuntimeError("synthetic precommit failure")
                    await super().finalize_failure(failed_job, error_code=error_code)

            runtime = PreviewPublicationRuntime(
                store=ControlledFailureCommit(worker),
                source=source,
                destination=ControlledStorageFailure(),
                validator=FixedNodePreviewCanonicalValidator(repository_root=ROOT),
                transform=lambda p, v, pages, paths: transformer.file(
                    p, v, pages=pages, files=paths
                ),
                synthetic_sources=frozenset({(binding.artifact_version_id, binding.source_hash)}),
            )
            message = PreviewPublicationMessage("1", event, job)
            if failure_mode in {"source", "failure_commit"}:
                corrupt_key = next(k for k in source.values if k.endswith("/files/index.html"))
                source.values[corrupt_key] += b"synthetic corruption"
            before = dict(source.values)
            if failure_mode in {"copy", "failure_commit"}:
                expected_error = (
                    "PREVIEW_STORAGE_ERROR"
                    if failure_mode == "copy"
                    else "PREVIEW_FINALIZATION_RECOVERABLE"
                )
                with pytest.raises(PreviewError, match=expected_error):
                    await runtime.execute(message)
                async with owner.connect() as connection:
                    assert (
                        await connection.scalar(
                            text("SELECT status FROM jobs WHERE id=:id"), {"id": job}
                        )
                        == "running"
                    )
                    assert (
                        await connection.scalar(
                            text("SELECT count(*) FROM preview_publications WHERE status='ready'")
                        )
                        == 0
                    )
                    assert (
                        await connection.scalar(
                            text("SELECT count(*) FROM aria_internal.preview_execution_claims")
                        )
                        == 0
                    )
            if failure_mode in {"source", "failure_commit"}:
                result = await runtime.execute(message)
                assert result.status == "failed" and result.error_code == "PREVIEW_SOURCE_INVALID"
                with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
                    await runtime.execute(message)
                async with owner.connect() as connection:
                    row = (
                        await connection.execute(
                            text(
                                "SELECT j.status,j.error_code,j.error_detail,p.status,p.token_hash,"
                                "r.status,r.manifest_hash FROM jobs j JOIN preview_publications p "
                                "ON p.publish_job_id=j.id JOIN preview_representations r "
                                "ON r.id=p.representation_id WHERE j.id=:id"
                            ),
                            {"id": job},
                        )
                    ).one()
                    assert tuple(row) == (
                        "failed",
                        "PREVIEW_SOURCE_INVALID",
                        None,
                        "publishing",
                        None,
                        "preparing",
                        None,
                    )
                    assert (
                        await connection.scalar(
                            text("SELECT count(*) FROM aria_internal.preview_execution_claims")
                        )
                        == 0
                    )
                assert not list(tmp_path.iterdir()) and source.values == before
                return
            assert (await runtime.execute(message)).status == "succeeded"
            assert (await runtime.execute(message)).status == "already_completed"
            assert source.values == before
            async with owner.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            "SELECT p.status,r.status,j.status,"
                            "r.manifest_ref,r.manifest_hash,p.token_hash "
                            "FROM preview_publications p JOIN preview_representations r "
                            "ON r.id=p.representation_id JOIN jobs j ON j.id=p.publish_job_id "
                            "WHERE p.id=:id"
                        ),
                        {"id": publication},
                    )
                ).one()
                assert tuple(row[:3]) == ("ready", "ready", "succeeded")
                from aria_backend_application.preview_delivery import digest

                value = await destination.read(row[3])
                assert value is not None and digest(value) == row[4] and row[5] is None
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM aria_internal.preview_execution_claims")
                    )
                    == 0
                )
            # Fixture-only capability issuance; authenticated permission/one-time command
            # behavior is independently covered in API tests. Raw token never reaches SQL.
            token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
            issued_at = datetime.now(UTC)
            async with owner.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE preview_publications SET token_hash=:hash,issued_at=:issued,"
                        "expires_at=:expires WHERE id=:id"
                    ),
                    {
                        "hash": hashlib.sha256(token.encode()).hexdigest(),
                        "issued": issued_at,
                        "expires": issued_at + timedelta(hours=1),
                        "id": publication,
                    },
                )
            host = f"v-{binding.artifact_version_id}.aria-preview.test:8181"
            access = PreviewAccessService(
                host=host,
                core_origin="http://core.aria-core.test:8182",
                binding=binding,
                resolver=PostgresPreviewCapabilityResolver(worker),
                storage=destination,
                synthetic_sources=frozenset({(binding.artifact_version_id, binding.source_hash)}),
            )
            for method in ("GET", "HEAD"):
                for path in ("index.html", "assets/styles.css", "generation-fixtures/media.svg"):
                    read = await access.read(
                        host=host, raw_target=f"/p/{token}/{path}", method=method
                    )
                    assert read.status == 200
                    assert read.headers["Cache-Control"] == "no-store"
                    assert read.body == b"" if method == "HEAD" else bool(read.body)
                    assert token not in repr(read)
            async with owner.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE preview_publications SET status='revoked',"
                        "revoked_at=:now WHERE id=:id"
                    ),
                    {"now": datetime.now(UTC), "id": publication},
                )
            read = await access.read(
                host=host, raw_target=f"/p/{token}/assets/styles.css", method="GET"
            )
            assert read.status == 404 and read.error_code == "RESOURCE_NOT_FOUND"
        finally:
            await owner.dispose()
            await worker.dispose()

    asyncio.run(scenario())
