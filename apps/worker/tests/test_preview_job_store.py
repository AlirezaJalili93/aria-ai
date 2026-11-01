from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from aria_backend_application.preview_delivery import PreviewError
from sqlalchemy.exc import SQLAlchemyError
from test_preview_publication_runtime import setup

from app.infrastructure.db.preview_publication import PostgresPreviewPublicationStore


class Connection:
    def __init__(self, job):
        binding = job.binding
        self.value = {
            "job_id": str(job.job_id),
            "publication_id": str(job.publication_id),
            "account_id": str(binding.account_id),
            "project_id": str(binding.project_id),
            "artifact_id": str(binding.artifact_id),
            "artifact_version_id": str(binding.artifact_version_id),
            "representation_id": str(binding.representation_id),
            "version_no": binding.version_no,
            "source_hash": binding.source_hash,
            "source_ref": binding.source_ref,
            "manifest_ref": None,
            "manifest_hash": None,
            "already_completed": False,
        }
        self.fail = None
        self.calls = []
        self.invalidated = False
        self.closed = False

    async def begin(self):
        self.calls.append("begin")
        return self

    async def commit(self):
        self.calls.append("commit")
        if self.fail == "commit":
            raise SQLAlchemyError("prohibited database detail")

    async def scalar(self, sql, params):
        self.calls.append(str(sql))
        if self.fail == "claim":
            raise SQLAlchemyError("prohibited claim detail")
        if self.fail == "cancel":
            raise asyncio.CancelledError
        return self.value

    async def execute(self, sql, params):
        self.calls.append(str(sql))
        if self.fail == "execute":
            raise SQLAlchemyError("prohibited SQL detail")

    async def invalidate(self):
        self.invalidated = True

    async def close(self):
        self.closed = True


class Engine:
    def __init__(self, connection):
        self.connection = connection

    async def connect(self):
        return self.connection


@pytest.mark.parametrize("stage", ["claim", "commit", "cancel", "shape"])
def test_failed_or_ambiguous_claim_discards_physical_connection(stage):
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        if stage == "shape":
            connection.value["version_no"] = True
        else:
            connection.fail = stage
        store = PostgresPreviewPublicationStore(Engine(connection))
        with pytest.raises(asyncio.CancelledError if stage == "cancel" else PreviewError):
            await store.prepare(message)
        assert connection.invalidated and connection.closed

    asyncio.run(scenario())


def test_fixed_helpers_same_owned_session_no_transaction_during_storage():
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        prepared = await store.prepare(message)
        assert prepared == job
        assert connection.calls[-1] == "commit"
        assert not connection.closed
        from app.application.preview_publication_runtime import preview_prefix

        await store.finalize(
            prepared,
            manifest_ref=preview_prefix(job.binding) + "/delivery-manifest.json",
            manifest_hash="sha256:" + "a" * 64,
        )
        await store.release(message)
        assert connection.invalidated and connection.closed
        sql = [c for c in connection.calls if c.startswith("SELECT")]
        assert len(sql) == 3
        assert "claim_preview" in sql[0]
        assert "finalize_preview" in sql[1]
        assert "release_preview" in sql[2]

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["commit", "execute"])
def test_failed_finalization_discards_lock_connection_and_is_bounded(stage):
    async def scenario():
        from app.application.preview_publication_runtime import preview_prefix

        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        connection.fail = stage
        with pytest.raises(PreviewError, match="PREVIEW_FINALIZATION_RECOVERABLE"):
            await store.finalize(
                job,
                manifest_ref=preview_prefix(job.binding) + "/delivery-manifest.json",
                manifest_hash="sha256:" + "a" * 64,
            )
        assert connection.invalidated and connection.closed
        await store.release(message)

    asyncio.run(scenario())


def test_wrong_event_release_does_not_release_current_owner():
    async def scenario():
        from uuid import uuid4

        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
            await store.release(replace(message, outbox_event_id=uuid4()))
        assert not connection.closed
        await store.release(message)
        assert connection.closed

    asyncio.run(scenario())


def test_failed_release_never_returns_locked_session_to_pool():
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        connection.fail = "execute"
        await store.release(message)
        assert connection.invalidated and connection.closed

    asyncio.run(scenario())


def test_failure_port_uses_same_session_and_fixed_helper_with_bounded_code():
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        await store.finalize_failure(job, error_code="PREVIEW_SOURCE_INVALID")
        assert "fail_preview" in connection.calls[-2] and connection.calls[-1] == "commit"
        assert not connection.closed
        await store.release(message)
        assert connection.invalidated and connection.closed

    asyncio.run(scenario())


@pytest.mark.parametrize("code", ["timeout", "PREVIEW_STORAGE_ERROR", "prohibited raw error"])
def test_failure_port_rejects_other_codes_without_mutation(code):
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        before = list(connection.calls)
        with pytest.raises(PreviewError, match="VALIDATION_FAILED"):
            await store.finalize_failure(job, error_code=code)
        assert connection.calls == before
        await store.release(message)

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["execute", "commit"])
def test_failure_port_commit_error_invalidates_session(stage):
    async def scenario():
        _, message, job, *_ = setup()
        connection = Connection(job)
        store = PostgresPreviewPublicationStore(Engine(connection))
        await store.prepare(message)
        connection.fail = stage
        with pytest.raises(PreviewError, match="PREVIEW_FINALIZATION_RECOVERABLE"):
            await store.finalize_failure(job, error_code="PREVIEW_SOURCE_INVALID")
        assert connection.invalidated and connection.closed

    asyncio.run(scenario())
