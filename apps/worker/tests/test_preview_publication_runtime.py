from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from aria_backend_application.preview_delivery import PreviewError, digest
from test_preview_manifest import fixture

from app.application.preview_publication_runtime import (
    PreviewPublicationJob,
    PreviewPublicationMessage,
    PreviewPublicationRuntime,
    preview_prefix,
)


class Storage:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.writes = []
        self.fail_at = None
        self.corrupt_readback = False

    async def read(self, key):
        value = self.values.get(key)
        return b"corrupt" if self.corrupt_readback and key in self.writes else value

    async def create_or_verify(self, key, value):
        if self.fail_at == len(self.writes):
            raise OSError("prohibited storage diagnostic")
        if key in self.values and self.values[key] != value:
            raise PreviewError("PREVIEW_DELIVERY_CONFLICT")
        self.values.setdefault(key, value)
        self.writes.append(key)


class Store:
    def __init__(self, job):
        self.job = job
        self.finalizations = []
        self.releases = []
        self.fail_commit = False
        self.failures = []
        self.fail_failure_commit = False

    async def prepare(self, message):
        assert message.job_id == self.job.job_id
        if self.failures:
            raise PreviewError("RESOURCE_NOT_FOUND")
        return self.job

    async def finalize_failure(self, job, *, error_code):
        if self.fail_failure_commit:
            raise RuntimeError("prohibited failure commit diagnostic")
        self.failures.append((job.job_id, error_code))

    async def finalize(self, job, *, manifest_ref, manifest_hash):
        if self.fail_commit:
            raise RuntimeError("prohibited database diagnostic")
        self.finalizations.append((job.job_id, manifest_ref, manifest_hash))
        self.job = replace(job, already_completed=True)

    async def release(self, message):
        self.releases.append(message)


class Validator:
    def __init__(self):
        self.calls = []
        self.fail = False

    async def validate(self, ast):
        self.calls.append(ast)
        if self.fail:
            raise ValueError("prohibited synthetic content")


def setup():
    binding, manifest, files, transformer = fixture()
    source_prefix = (
        f"artifacts/{binding.account_id}/{binding.project_id}/{binding.artifact_id}"
        f"/versions/{binding.artifact_version_id}"
    )
    binding = replace(binding, source_ref=source_prefix + "/manifest.json")
    job = PreviewPublicationJob(job_id=uuid4(), publication_id=uuid4(), binding=binding)
    message = PreviewPublicationMessage("1", uuid4(), job.job_id)
    source = Storage({binding.source_ref: manifest})
    source.values.update({source_prefix + "/files/" + p: v for p, v in files.items()})
    destination, store, validator = Storage(), Store(job), Validator()
    runtime = PreviewPublicationRuntime(
        store=store,
        source=source,
        destination=destination,
        validator=validator,
        transform=lambda p, v, pages, paths: transformer.file(p, v, pages=pages, files=paths),
        synthetic_sources=frozenset({(binding.artifact_version_id, binding.source_hash)}),
    )
    return runtime, message, job, source, destination, store, validator


def test_manifest_last_verified_copy_atomic_finalization_and_replay():
    async def scenario():
        runtime, message, job, source, destination, store, validator = setup()
        original = dict(source.values)
        result = await runtime.execute(message)
        assert result.status == "succeeded"
        prefix = preview_prefix(job.binding)
        assert destination.writes[-1] == prefix + "/delivery-manifest.json"
        assert all(p.startswith(prefix + "/files/") for p in destination.writes[:-1])
        assert store.finalizations == [
            (job.job_id, destination.writes[-1], digest(destination.values[destination.writes[-1]]))
        ]
        assert len(validator.calls) == 1 and source.values == original
        count = len(destination.writes)
        assert (await runtime.execute(message)).status == "already_completed"
        assert len(destination.writes) == count and len(validator.calls) == 1
        assert len(store.finalizations) == 1 and store.releases == [message, message]
        assert job.binding.source_ref not in repr(job)
        assert job.binding.source_hash not in repr(result)

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["source", "file", "ast", "copy", "readback", "commit"])
def test_failure_no_success_and_release_without_raw_diagnostic(stage):
    async def scenario():
        runtime, message, job, source, destination, store, validator = setup()
        if stage == "source":
            source.values[job.binding.source_ref] += b" "
        elif stage == "file":
            source.values[next(p for p in source.values if p.endswith("index.html"))] += b"!"
        elif stage == "ast":
            validator.fail = True
        elif stage == "copy":
            destination.fail_at = 1
        elif stage == "readback":
            destination.corrupt_readback = True
        else:
            store.fail_commit = True
        if stage in {"copy", "commit"}:
            with pytest.raises(PreviewError) as caught:
                await runtime.execute(message)
            assert "prohibited" not in str(caught.value)
            assert caught.value.retryable and store.failures == []
        else:
            result = await runtime.execute(message)
            assert result.status == "failed" and result.error_code is not None
            assert store.failures == [(job.job_id, result.error_code)]
        assert store.finalizations == [] and store.releases == [message]
        if stage in {"source", "file", "ast"}:
            assert destination.writes == []

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["copy", "commit"])
def test_recovery_reuses_same_objects_and_same_job(stage):
    async def scenario():
        runtime, message, job, source, destination, store, _ = setup()
        original = dict(source.values)
        if stage == "copy":
            destination.fail_at = 1
        else:
            store.fail_commit = True
        with pytest.raises(PreviewError):
            await runtime.execute(message)
        partial = dict(destination.values)
        destination.fail_at = None
        store.fail_commit = False
        assert (await runtime.execute(message)).status == "succeeded"
        assert all(destination.values[k] == v for k, v in partial.items())
        assert source.values == original
        assert store.finalizations[0][0] == job.job_id

    asyncio.run(scenario())


def test_conflicting_object_never_overwritten_or_finalized():
    async def scenario():
        runtime, message, job, _, destination, store, _ = setup()
        key = preview_prefix(job.binding) + "/files/assets/styles.css"
        destination.values[key] = b"immutable conflict"
        result = await runtime.execute(message)
        assert result.status == "failed" and result.error_code == "PREVIEW_DELIVERY_CONFLICT"
        assert destination.values[key] == b"immutable conflict" and not store.finalizations

    asyncio.run(scenario())


def test_independent_synthetic_allowlist_blocks_before_storage_or_validator():
    async def scenario():
        runtime, message, job, _, destination, store, validator = setup()
        store.job = replace(job, binding=replace(job.binding, artifact_version_id=uuid4()))
        with pytest.raises(PreviewError, match="FEATURE_NOT_ENABLED"):
            await runtime.execute(message)
        assert not destination.writes and not validator.calls
        assert not store.failures
        assert store.releases == [message]

    asyncio.run(scenario())


def test_failure_commit_error_does_not_claim_terminal_success_and_recovery_is_explicit():
    async def scenario():
        runtime, message, job, source, destination, store, _ = setup()
        source.values[job.binding.source_ref] += b" "
        store.fail_failure_commit = True
        with pytest.raises(PreviewError, match="PREVIEW_FINALIZATION_RECOVERABLE"):
            await runtime.execute(message)
        assert not store.failures and not destination.writes
        store.fail_failure_commit = False
        assert (await runtime.execute(message)).status == "failed"
        assert len(store.failures) == 1
        with pytest.raises(PreviewError, match="RESOURCE_NOT_FOUND"):
            await runtime.execute(message)
        assert len(store.failures) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"message_version": "1", "job_id": "bad"},
        {
            "message_version": "1",
            "job_id": str(uuid4()),
            "outbox_event_id": str(uuid4()),
            "text": "secret",
        },
    ],
)
def test_identifier_only_message_rejects_invalid_or_extra_fields(bad):
    with pytest.raises(PreviewError, match="VALIDATION_FAILED"):
        PreviewPublicationMessage.from_payload(bad)


def test_message_roundtrip_and_version_validation():
    _, message, *_ = setup()
    payload = {
        "message_version": "1",
        "outbox_event_id": str(message.outbox_event_id),
        "job_id": str(message.job_id),
    }
    assert PreviewPublicationMessage.from_payload(payload) == message
    payload["message_version"] = "2"
    with pytest.raises(PreviewError, match="VALIDATION_FAILED"):
        PreviewPublicationMessage.from_payload(payload)
