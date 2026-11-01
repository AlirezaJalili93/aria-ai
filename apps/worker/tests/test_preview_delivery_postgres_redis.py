"""Controlled fixture/command pipeline; optional synthetic Browser proof, no Hosted."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from io import StringIO
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from aria_backend_application.preview_delivery import (
    DELIVERY_POLICY_VERSION,
    TRANSFORMER_VERSION,
    PreviewBinding,
)
from celery import signals  # type: ignore[import-untyped]
from celery.contrib.testing.worker import start_worker  # type: ignore[import-untyped]
from preview_browser_process import BrowserProof
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from test_artifact_generation_runtime_postgres import (
    TEST_DATABASE_URL,
    _MemoryStorage,
    _message,
    _seed,
)
from test_outbox_delivery import _logger
from test_preview_publication_runtime_postgres import ROOT

from app.application.artifact_generation_runtime import ArtifactGenerationRuntime
from app.application.outbox_delivery import DurableOutboxRelay
from app.application.preview_access import PreviewAccessService
from app.application.preview_publication_runtime import (
    PREVIEW_TASK_NAME,
    PreviewPublicationMessage,
    PreviewPublicationRuntime,
    preview_prefix,
)
from app.core.config import QueueRuntimeConfiguration
from app.infrastructure.artifact_builder import FixedNodeArtifactBuilder
from app.infrastructure.db.artifact_generation_runtime import PostgresArtifactGenerationJobStore
from app.infrastructure.db.outbox_delivery import PostgresOutboxDeliveryRepository
from app.infrastructure.db.preview_access import PostgresPreviewCapabilityResolver
from app.infrastructure.db.preview_publication import PostgresPreviewPublicationStore
from app.infrastructure.preview_canonical_validator import FixedNodePreviewCanonicalValidator
from app.infrastructure.preview_http import controlled_preview_listener
from app.infrastructure.preview_storage import LocalSyntheticPreviewStorage
from app.infrastructure.preview_transformer import PreviewTransformer
from app.infrastructure.queue.celery_runtime import create_celery_app
from app.infrastructure.queue.preview_outbox_publisher import CeleryPreviewOutboxPublisher
from app.infrastructure.queue.preview_publication_task import register_preview_publication_task
from app.infrastructure.synthetic_artifact_candidate import (
    VersionedSyntheticArtifactCandidateSource,
)

BROKER = os.environ.get("TEST_QUEUE_BROKER_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None or BROKER is None, reason="Owned PostgreSQL and Redis required"
)


def http_read(port, host, target, method):
    client = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        client.request(method, target, headers={"Host": host})
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


async def api_command(payload):
    allowed_environment = {
        "PATH",
        "SYSTEMROOT",
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
        "TMP",
        "TEMP",
        "UV_PATH",
        "TEST_DATABASE_URL",
    }
    command_environment = {
        key: value for key, value in os.environ.items() if key.upper() in allowed_environment
    }
    process = await asyncio.create_subprocess_exec(
        "node",
        str(ROOT / "scripts/run-uv.mjs"),
        "--project",
        "apps/api",
        "run",
        "python",
        str(ROOT / "tests/e2e/controlled_preview_commands_api.py"),
        cwd=ROOT,
        env=command_environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, diagnostics = await process.communicate(json.dumps(payload).encode())
    assert process.returncode == 0, "API test command process failed (details withheld)"
    if diagnostics:
        pytest.fail("API test command emitted diagnostics (details withheld)")
    result = json.loads(output)
    assert isinstance(result, dict), "API test command response invalid (details withheld)"
    return result


async def allocate_command(owner, fixture):
    async with owner.begin() as conn:
        source_ref, source_hash = (
            await conn.execute(
                text("SELECT storage_ref,artifact_hash FROM artifact_versions WHERE id=:id"),
                {"id": fixture.artifact_version_id},
            )
        ).one()
        await conn.execute(
            text(
                "INSERT INTO account_memberships (id,account_id,user_id,role,status) "
                "VALUES (:id,:account,:user,'owner','active')"
            ),
            {"id": uuid4(), "account": fixture.account_id, "user": fixture.user_id},
        )
        await conn.execute(
            text(
                "UPDATE outbox_events SET status='published',published_at=CURRENT_TIMESTAMP "
                "WHERE id=:id"
            ),
            {"id": fixture.outbox_event_id},
        )
    payload = {
        "operation": "publish",
        "subject_id": str(fixture.user_id),
        "account_id": str(fixture.account_id),
        "project_id": str(fixture.project_id),
        "artifact_version_id": str(fixture.artifact_version_id),
        "source_hash": source_hash,
        "key": "joined-command-publish",
    }
    first = await api_command(payload)
    assert first.get("status") == "ok" and first.get("replayed") is False
    replay = await api_command(payload)
    assert replay.get("replayed") is True
    assert replay.get("publication_id") == first.get("publication_id")
    assert replay.get("job_id") == first.get("job_id")
    conflict = await api_command({**payload, "artifact_version_id": str(uuid4())})
    assert conflict.get("error_code") == "IDEMPOTENCY_CONFLICT"
    active = await api_command({**payload, "key": "new-active-command"})
    assert active.get("error_code") == "PREVIEW_PUBLICATION_IN_PROGRESS"
    foreign = await api_command({**payload, "project_id": str(uuid4()), "key": "not-visible"})
    assert foreign.get("error_code") == "RESOURCE_NOT_FOUND"
    publication, job = UUID(first["publication_id"]), UUID(first["job_id"])
    async with owner.connect() as conn:
        rep = await conn.scalar(
            text("SELECT representation_id FROM preview_publications WHERE id=:id"),
            {"id": publication},
        )
        event = await conn.scalar(
            text("SELECT id FROM outbox_events WHERE aggregate_id=:id"), {"id": job}
        )
    binding = PreviewBinding(
        account_id=fixture.account_id,
        project_id=fixture.project_id,
        artifact_id=fixture.artifact_id,
        artifact_version_id=fixture.artifact_version_id,
        version_no=1,
        representation_id=rep,
        source_ref=source_ref,
        source_hash=source_hash,
    )
    issue = {
        "operation": "issue",
        "subject_id": str(fixture.user_id),
        "account_id": str(fixture.account_id),
        "project_id": str(fixture.project_id),
        "publication_id": str(publication),
        "key": "joined-command-issue",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    early = await api_command(issue)
    assert early.get("error_code") == "ARTIFACT_VERSION_NOT_READY"
    return binding, publication, job, event, issue


async def allocate_fixture(owner, fixture):
    rep, pub, job, event = (uuid4() for _ in range(4))
    async with owner.begin() as conn:
        source_ref, source_hash = (
            await conn.execute(
                text("SELECT storage_ref, artifact_hash FROM artifact_versions WHERE id=:id"),
                {"id": fixture.artifact_version_id},
            )
        ).one()
        params = {
            "account": fixture.account_id,
            "project": fixture.project_id,
            "artifact": fixture.artifact_id,
            "version": fixture.artifact_version_id,
            "creator": fixture.user_id,
            "rep": rep,
            "pub": pub,
            "job": job,
            "event": event,
            "hash": source_hash,
            "transformer": TRANSFORMER_VERSION,
            "policy": DELIVERY_POLICY_VERSION,
        }
        # Source runtime was explicitly executed above; exclude its already-delivered fixture
        # event from this Preview-only relay proof. This is not automatic chaining.
        await conn.execute(
            text(
                "UPDATE outbox_events SET status='published',published_at=CURRENT_TIMESTAMP "
                "WHERE id=:id"
            ),
            {"id": fixture.outbox_event_id},
        )
        await conn.execute(
            text(
                "INSERT INTO preview_representations (id,account_id,project_id,artifact_id,"
                "artifact_version_id,source_hash,transformer_version,delivery_policy_version,"
                "status,created_by) VALUES (:rep,:account,:project,:artifact,:version,:hash,"
                ":transformer,:policy,'allocated',:creator)"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO jobs (id,account_id,project_id,job_type,status,payload_ref,"
                "attempt_count,max_attempts,correlation_id,available_at) VALUES "
                "(:job,:account,:project,'preview_publication','queued',CAST(:payload AS jsonb),"
                "0,1,:job,CURRENT_TIMESTAMP)"
            ),
            {
                **params,
                "payload": json.dumps(
                    {
                        "publication_id": str(pub),
                        "representation_id": str(rep),
                        "artifact_version_id": str(fixture.artifact_version_id),
                    }
                ),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO preview_publications (id,account_id,project_id,artifact_version_id,"
                "representation_id,publish_job_id,status,created_by) VALUES "
                "(:pub,:account,:project,:version,:rep,:job,'allocated',:creator)"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO outbox_events (id,account_id,aggregate_type,aggregate_id,event_type,"
                "delivery_channel,payload,status,attempt_count,available_at) VALUES "
                "(:event,:account,'job',:job,'preview.publication_requested.v1','job_queue',"
                "CAST(:payload AS jsonb),'pending',0,CURRENT_TIMESTAMP)"
            ),
            {
                **params,
                "payload": json.dumps(
                    {"jobId": str(job), "taskType": "preview_publication", "payloadVersion": "1"}
                ),
            },
        )
    return (
        PreviewBinding(
            account_id=fixture.account_id,
            project_id=fixture.project_id,
            artifact_id=fixture.artifact_id,
            artifact_version_id=fixture.artifact_version_id,
            version_no=1,
            representation_id=rep,
            source_hash=source_hash,
            source_ref=source_ref,
        ),
        pub,
        job,
        event,
    )


@pytest.mark.parametrize("project_type", ["landing", "corporate", "portfolio"])
@pytest.mark.parametrize("recover_copy", [False, True])
@pytest.mark.parametrize("command_mode", [False, True])
def test_real_relay_to_worker_copy_recovery_and_duplicate_delivery(
    tmp_path, project_type, recover_copy, command_mode
):
    async def scenario():
        assert TEST_DATABASE_URL is not None and BROKER is not None
        assert urlsplit(BROKER).hostname == "127.0.0.1"
        url = make_url(TEST_DATABASE_URL)
        assert url.host == "127.0.0.1"
        owner = create_async_engine(url, poolclass=NullPool)
        worker_url = url.set(username="aria_worker", password=None)
        relay_engine = create_async_engine(worker_url, poolclass=NullPool)
        source, stream = _MemoryStorage(), StringIO()
        app = None
        browser_proof = None
        browser_enabled = (
            os.environ.get("TEST_PREVIEW_BROWSER") == "controlled-synthetic-browser"
            and command_mode
            and not recover_copy
        )
        client = Redis.from_url(BROKER)
        queue = "preview-joined-" + str(uuid4())
        try:
            fixture = await _seed(owner)
            async with owner.begin() as conn:
                await conn.execute(
                    text("UPDATE projects SET project_type=:type WHERE id=:id"),
                    {"type": project_type, "id": fixture.project_id},
                )

            class CandidateSource(VersionedSyntheticArtifactCandidateSource):
                async def load(self, *, project_type):
                    value = await super().load(project_type=project_type)
                    if browser_enabled and project_type == "corporate":
                        # preview_nested_corporate_v1: in-memory recipe, fixture v1 file unchanged.
                        def nested(node):
                            if isinstance(node, dict):
                                for key, item in node.items():
                                    if key in {"path", "target_path"} and item == "/services":
                                        node[key] = "/services/design"
                                    else:
                                        nested(item)
                            elif isinstance(node, list):
                                for item in node:
                                    nested(item)

                        nested(value)
                    return value

            generation = ArtifactGenerationRuntime(
                store=PostgresArtifactGenerationJobStore(relay_engine),
                candidate_source=CandidateSource(repository_root=ROOT),
                builder=FixedNodeArtifactBuilder(repository_root=ROOT),
                storage=source,
            )
            assert (await generation.execute(_message(fixture))).status == "succeeded"
            before = dict(source.values)
            if command_mode:
                binding, pub, job, event_id, issue = await allocate_command(owner, fixture)
            else:
                binding, pub, job, event_id = await allocate_fixture(owner, fixture)
            destination = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)

            class Destination:
                attempts = 0

                async def read(self, key):
                    return await destination.read(key)

                async def create_or_verify(self, key, content):
                    self.attempts += 1
                    if recover_copy and self.attempts == 1:
                        raise OSError("synthetic-storage-failure-marker")
                    await destination.create_or_verify(key, content)

            storage = Destination()

            class Executor:
                calls = 0
                stage = "not_started"
                failure_class = None

                async def execute(self, message):
                    self.calls += 1
                    # Each Celery invocation owns its engine/loop/session lifecycle.
                    engine = create_async_engine(worker_url, poolclass=NullPool)
                    try:
                        self.stage = "principal_check"
                        async with engine.connect() as conn:
                            assert (
                                await conn.execute(text("SELECT session_user,current_user"))
                            ).one() == ("aria_worker", "aria_worker")
                        self.stage = "preview_runtime"
                        transformer = PreviewTransformer(ROOT)
                        return await PreviewPublicationRuntime(
                            store=PostgresPreviewPublicationStore(engine),
                            source=source,
                            destination=storage,
                            validator=FixedNodePreviewCanonicalValidator(repository_root=ROOT),
                            transform=lambda p, v, pages, paths: transformer.file(
                                p, v, pages=pages, files=paths
                            ),
                            synthetic_sources=frozenset(
                                {(binding.artifact_version_id, binding.source_hash)}
                            ),
                        ).execute(message)
                    except Exception as exc:
                        self.failure_class = type(exc).__name__
                        raise
                    finally:
                        await engine.dispose()

            executor = Executor()
            app = create_celery_app(
                QueueRuntimeConfiguration(
                    broker_url=SecretStr(BROKER),
                    queue_name=queue,
                    visibility_timeout_seconds=60,
                    concurrency=1,
                )
            )
            register_preview_publication_task(app, executor)
            task = app.tasks[PREVIEW_TASK_NAME]
            completed, outcomes = threading.Event(), []

            def postrun(sender=None, state=None, retval=None, **kwargs):
                if sender is task:
                    outcomes.append((state, retval))
                    completed.set()

            signals.task_postrun.connect(postrun, sender=task, weak=False)

            class Publisher(CeleryPreviewOutboxPublisher):
                events = []

                async def publish(self, event):
                    self.events.append(event)
                    await super().publish(event)

            publisher = Publisher(app, queue_name=queue)
            relay = DurableOutboxRelay(
                repository=PostgresOutboxDeliveryRepository(relay_engine),
                publisher=publisher,
                event_logger=_logger(stream),
            )
            try:
                with start_worker(
                    app,
                    pool="solo",
                    perform_ping_check=False,
                    queues=[queue],
                    logfile=os.devnull,
                    loglevel="CRITICAL",
                    shutdown_timeout=15,
                ):
                    cycle = await relay.run_once()
                    assert (cycle.claimed, cycle.published, cycle.failed, cycle.blocked) == (
                        1,
                        1,
                        0,
                        0,
                    )
                    assert await asyncio.to_thread(completed.wait, 30)
                    if outcomes[0][0] == "FAILURE" and storage.attempts == 0:
                        pytest.fail(
                            f"Controlled failure before copy: stage={executor.stage}; "
                            f"class={executor.failure_class}"
                        )
                    assert len(publisher.events) == 1 and publisher.events[0].id == event_id
                    if recover_copy:
                        assert outcomes[0][0] == "FAILURE"
                        async with owner.connect() as conn:
                            assert (
                                await conn.scalar(
                                    text("SELECT status FROM jobs WHERE id=:id"), {"id": job}
                                )
                                == "running"
                            )
                            assert (
                                await conn.scalar(
                                    text(
                                        "SELECT manifest_ref FROM preview_representations "
                                        "WHERE id=:id"
                                    ),
                                    {"id": binding.representation_id},
                                )
                                is None
                            )
                        completed.clear()
                        # Explicit controlled recovery, same event/Job; no automatic task retry.
                        await publisher.publish(publisher.events[0])
                        assert await asyncio.to_thread(completed.wait, 30)
                    assert outcomes[-1] == ("SUCCESS", {"status": "succeeded", "error_code": None})
                    copies = storage.attempts
                    completed.clear()
                    await publisher.publish(publisher.events[0])
                    assert await asyncio.to_thread(completed.wait, 30)
                    assert outcomes[-1] == (
                        "SUCCESS",
                        {"status": "already_completed", "error_code": None},
                    )
                    assert storage.attempts == copies
                    assert executor.calls == (3 if recover_copy else 2)
            finally:
                signals.task_postrun.disconnect(postrun, sender=task)
            assert set(source.values) == set(before)
            assert all(source.values[key] == before[key] for key in before)
            async with owner.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            "SELECT p.status,r.status,j.status,p.token_hash,e.status "
                            "FROM preview_publications p JOIN preview_representations r "
                            "ON r.id=p.representation_id JOIN jobs j ON j.id=p.publish_job_id "
                            "JOIN outbox_events e ON e.aggregate_id=j.id "
                            "WHERE p.id=:id"
                        ),
                        {"id": pub},
                    )
                ).one()
                assert tuple(row) == ("ready", "ready", "succeeded", None, "published")
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM jobs WHERE job_type='preview_publication'")
                    )
                    == 1
                )
                assert await conn.scalar(text("SELECT count(*) FROM preview_publications")) == 1
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM aria_internal.preview_execution_claims")
                    )
                    == 0
                )
            assert "synthetic-storage-failure-marker" not in stream.getvalue()
            assert binding.source_hash not in stream.getvalue()
            assert binding.source_ref not in stream.getvalue()
            assert client.llen(queue) == 0
            if command_mode:
                issued = await api_command(issue)
                token = issued.pop("token", None)
                assert isinstance(token, str) and len(token) == 43, "Missing one-time capability"
                assert issued.get("token_available") is True and issued.get("replayed") is False
                replay = await api_command(issue)
                if replay.get("token") is not None or replay.get("token_available") is not False:
                    pytest.fail("Capability incorrectly disclosed on replay (value withheld)")
                assert replay.get("replayed") is True

                # A ready representation is content identity, not one capability's lifecycle.
                async with owner.connect() as conn:
                    representation_before = (
                        await conn.execute(
                            text(
                                "SELECT manifest_ref,manifest_hash FROM preview_representations "
                                "WHERE id=:id"
                            ),
                            {"id": binding.representation_id},
                        )
                    ).one()
                manifest_bytes = await destination.read(representation_before[0])
                assert manifest_bytes is not None
                delivery_manifest = json.loads(manifest_bytes)
                private_before = {representation_before[0]: manifest_bytes}
                for item in delivery_manifest["files"]:
                    key = preview_prefix(binding) + "/files/" + item["path"]
                    private_before[key] = await destination.read(key)
                    assert private_before[key] is not None
                second_publish = {
                    "operation": "publish",
                    "subject_id": str(fixture.user_id),
                    "account_id": str(fixture.account_id),
                    "project_id": str(fixture.project_id),
                    "artifact_version_id": str(binding.artifact_version_id),
                    "source_hash": binding.source_hash,
                    "key": "joined-second-publication",
                }
                contenders = await asyncio.gather(
                    api_command(second_publish), api_command(second_publish)
                )
                assert all(item.get("status") == "ok" for item in contenders)
                assert sorted(item["replayed"] for item in contenders) == [False, True]
                assert contenders[0]["publication_id"] == contenders[1]["publication_id"]
                assert contenders[0]["job_id"] == contenders[1]["job_id"]
                second_pub = UUID(contenders[0]["publication_id"])
                second_job = UUID(contenders[0]["job_id"])
                assert second_pub != pub and second_job != job
                async with owner.connect() as conn:
                    second_rep = await conn.scalar(
                        text("SELECT representation_id FROM preview_publications WHERE id=:id"),
                        {"id": second_pub},
                    )
                    second_event = await conn.scalar(
                        text("SELECT id FROM outbox_events WHERE aggregate_id=:id"),
                        {"id": second_job},
                    )
                assert second_rep == binding.representation_id
                signals.task_postrun.connect(postrun, sender=task, weak=False)
                try:
                    completed.clear()
                    with start_worker(
                        app,
                        pool="solo",
                        perform_ping_check=False,
                        queues=[queue],
                        logfile=os.devnull,
                        loglevel="CRITICAL",
                        shutdown_timeout=15,
                    ):
                        cycle = await relay.run_once()
                        assert (cycle.claimed, cycle.published, cycle.failed, cycle.blocked) == (
                            1,
                            1,
                            0,
                            0,
                        )
                        assert await asyncio.to_thread(completed.wait, 30)
                        assert outcomes[-1] == (
                            "SUCCESS",
                            {"status": "succeeded", "error_code": None},
                        )
                        assert publisher.events[-1].id == second_event
                finally:
                    signals.task_postrun.disconnect(postrun, sender=task)
                assert (
                    await executor.execute(PreviewPublicationMessage("1", second_event, second_job))
                ).status == "already_completed"
                for key, content in private_before.items():
                    if await destination.read(key) != content:
                        pytest.fail("Reused private file changed (details withheld)")
                async with owner.connect() as conn:
                    representation_after = (
                        await conn.execute(
                            text(
                                "SELECT manifest_ref,manifest_hash FROM preview_representations "
                                "WHERE id=:id"
                            ),
                            {"id": binding.representation_id},
                        )
                    ).one()
                    if representation_after != representation_before:
                        pytest.fail("Reused representation metadata changed (details withheld)")
                    assert (
                        await conn.scalar(text("SELECT count(*) FROM preview_representations")) == 1
                    )
                    assert await conn.scalar(text("SELECT count(*) FROM preview_publications")) == 2
                    assert (
                        await conn.scalar(
                            text(
                                "SELECT count(*) FROM jobs WHERE job_type='preview_publication' "
                                "AND status='succeeded'"
                            )
                        )
                        == 2
                    )
                    assert (
                        await conn.scalar(
                            text("SELECT count(*) FROM aria_internal.preview_execution_claims")
                        )
                        == 0
                    )
                second_issue = {
                    **issue,
                    "publication_id": str(second_pub),
                    "key": "joined-second-issue",
                }
                second_issued = await api_command(second_issue)
                second_token = second_issued.pop("token", None)
                if (
                    not isinstance(second_token, str)
                    or len(second_token) != 43
                    or second_token == token
                ):
                    pytest.fail("Second capability identity invalid (value withheld)")
                second_replay = await api_command(second_issue)
                if (
                    second_replay.get("token") is not None
                    or second_replay.get("token_available") is not False
                ):
                    pytest.fail("Second capability disclosed on replay (value withheld)")
                assert second_replay.get("replayed") is True
                for secret in (token, second_token):
                    if any(
                        secret.encode() in value
                        for value in (*private_before.values(), *source.values.values())
                    ):
                        pytest.fail("Capability persisted in artifact files (value withheld)")
                    async with owner.connect() as conn:
                        saved_outcomes = await conn.scalar(
                            text(
                                "SELECT coalesce(string_agg(response_ref::text,''),'') "
                                "FROM idempotency_records WHERE account_id=:account"
                            ),
                            {"account": fixture.account_id},
                        )
                    if secret in saved_outcomes:
                        pytest.fail("Capability persisted in command outcome (value withheld)")

                class ReadBarrier:
                    armed = False

                    def __init__(self):
                        self.entered = asyncio.Event()
                        self.release = asyncio.Event()

                    async def read(self, key):
                        if self.armed and key.endswith("/files/index.html"):
                            self.armed = False
                            self.entered.set()
                            await self.release.wait()
                        return await destination.read(key)

                read_barrier = ReadBarrier()
                core_origin = "http://core.aria-core.test:8182"
                if browser_enabled:
                    manifest = json.loads(source.values[binding.source_ref])
                    pages = sorted(
                        f["path"] for f in manifest["files"] if f["path"].endswith("index.html")
                    )
                    browser_proof = await BrowserProof.start(
                        binding.artifact_version_id, pages, tmp_path
                    )
                    core_origin = f"http://core.aria-core.test:{browser_proof.core_port}"

                def access_factory(port):
                    return PreviewAccessService(
                        host=f"v-{binding.artifact_version_id}.aria-preview.test:{port}",
                        core_origin=core_origin,
                        binding=binding,
                        resolver=PostgresPreviewCapabilityResolver(relay_engine),
                        storage=read_barrier,
                        synthetic_sources=frozenset(
                            {(binding.artifact_version_id, binding.source_hash)}
                        ),
                    )

                async with owner.connect() as conn:
                    saved = await conn.scalar(
                        text(
                            "SELECT response_ref::text FROM idempotency_records "
                            "WHERE account_id=:account AND idempotency_key=:key"
                        ),
                        {"account": fixture.account_id, "key": issue["key"]},
                    )
                    if token in saved:
                        pytest.fail("Raw capability persisted in idempotency (value withheld)")
                revoke = {k: v for k, v in issue.items() if k != "expires_at"}
                revoke.update(operation="revoke", key="joined-command-revoke")
                async with controlled_preview_listener(access_factory) as listener:
                    host = f"v-{binding.artifact_version_id}.aria-preview.test:{listener.port}"
                    for item in delivery_manifest["files"]:
                        left = await asyncio.to_thread(
                            http_read, listener.port, host, f"/p/{token}/{item['path']}", "GET"
                        )
                        right = await asyncio.to_thread(
                            http_read,
                            listener.port,
                            host,
                            f"/p/{second_token}/{item['path']}",
                            "GET",
                        )
                        assert left[0] == right[0] == 200
                        assert left[1] == right[1]
                        expected = private_before[
                            preview_prefix(binding) + "/files/" + item["path"]
                        ]
                        if left[2] != right[2] or left[2] != expected:
                            pytest.fail("Capability file equality failed (details withheld)")
                    for path in (
                        "index.html",
                        "assets/styles.css",
                        "generation-fixtures/media.svg",
                    ):
                        for method in ("GET", "HEAD"):
                            read = await asyncio.to_thread(
                                http_read, listener.port, host, f"/p/{token}/{path}", method
                            )
                            assert read[0] == 200
                            assert read[1]["Cache-Control"] == "no-store"
                            assert "Access-Control-Allow-Origin" not in read[1]
                            if method == "HEAD":
                                assert read[2] == b""
                    if browser_proof:
                        await browser_proof.execute(listener.port, token, project_type)
                        browser_proof = None
                        assert all(source.values[key] == before[key] for key in before)
                    # SQL authorization completed, but private file IO is held deterministically.
                    # Revoke must commit without waiting for storage; the already authorized read
                    # may finish, while all new authorizations after that commit must fail.
                    read_barrier.armed = True
                    in_flight = asyncio.create_task(
                        asyncio.to_thread(
                            http_read, listener.port, host, f"/p/{token}/index.html", "GET"
                        )
                    )
                    try:
                        await asyncio.wait_for(read_barrier.entered.wait(), 30)
                        assert (await api_command(revoke)).get("status") == "ok"
                    finally:
                        read_barrier.release.set()
                        completed_read = await in_flight
                    assert completed_read[0] == 200
                    assert (await api_command(revoke)).get("status") == "ok"
                    denied = await asyncio.to_thread(
                        http_read, listener.port, host, f"/p/{token}/index.html", "GET"
                    )
                    assert denied[0] == 404 and denied[2] == b""
                    still_authorized = await asyncio.to_thread(
                        http_read, listener.port, host, f"/p/{second_token}/index.html", "GET"
                    )
                    assert still_authorized[0] == 200
                    second_revoke = {
                        **revoke,
                        "publication_id": str(second_pub),
                        "key": "joined-second-revoke",
                    }
                    assert (await api_command(second_revoke)).get("status") == "ok"
                    second_denied = await asyncio.to_thread(
                        http_read, listener.port, host, f"/p/{second_token}/index.html", "GET"
                    )
                    assert second_denied[0] == 404 and second_denied[2] == b""
                for key, content in private_before.items():
                    if await destination.read(key) != content:
                        pytest.fail("Revocation changed private file (details withheld)")
                if source.values != before:
                    pytest.fail("Publication lifecycle changed source bytes (details withheld)")
                assert client.llen(queue) == 0
                if token in stream.getvalue() or second_token in stream.getvalue():
                    pytest.fail("Capability leaked in operational log (value withheld)")
        finally:
            if browser_proof:
                await browser_proof.close()
            if app is not None:
                app.close()
            client.delete(queue)
            client.close()
            await relay_engine.dispose()
            await owner.dispose()

    asyncio.run(scenario())
