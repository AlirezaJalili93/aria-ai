from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.application.artifact_generation_runtime import (
    ArtifactBuildFile,
    ArtifactGenerationError,
    ArtifactGenerationJob,
    ArtifactGenerationMessage,
    ArtifactGenerationRuntime,
    StoredObject,
    digest,
)
from app.infrastructure.artifact_builder import FixedNodeArtifactBuilder
from app.infrastructure.synthetic_artifact_candidate import (
    VersionedSyntheticArtifactCandidateSource,
)

ROOT = Path(__file__).resolve().parents[3]


class MemoryStorage:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.writes: list[str] = []

    async def read(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def create_or_verify(self, key: str, content: bytes) -> StoredObject:
        self.writes.append(key)
        existing = self.values.get(key)
        if existing is not None and existing != content:
            raise ArtifactGenerationError("ARTIFACT_STORAGE_CONFLICT")
        self.values.setdefault(key, content)
        return StoredObject(key, digest(content))


class MemoryStore:
    def __init__(self, job: ArtifactGenerationJob) -> None:
        self.job = job
        self.checkpoint: tuple[str, str] | None = None
        self.finalizations = 0

    async def prepare(self, message: ArtifactGenerationMessage) -> ArtifactGenerationJob:
        assert message.job_id == self.job.job_id
        if self.checkpoint is None:
            return self.job
        values = {
            name: getattr(self.job, name) for name in self.job.__dataclass_fields__
        }
        values.update(
            checkpoint_ref=self.checkpoint[0], checkpoint_hash=self.checkpoint[1]
        )
        return ArtifactGenerationJob(**values)

    async def save_checkpoint(
        self, job: ArtifactGenerationJob, *, checkpoint_ref: str, checkpoint_hash: str
    ) -> None:
        assert job.artifact_version_id == self.job.artifact_version_id
        self.checkpoint = (checkpoint_ref, checkpoint_hash)

    async def finalize(
        self, job: ArtifactGenerationJob, *, storage_ref: str, artifact_hash: str
    ) -> str:
        assert storage_ref.endswith("/manifest.json")
        assert artifact_hash.startswith("sha256:")
        self.finalizations += 1
        return "finalized"

    async def release(self, message: ArtifactGenerationMessage) -> None:
        assert message.job_id == self.job.job_id


class CandidateSource:
    def __init__(self, candidate: object) -> None:
        self.candidate = candidate

    async def load(self, *, project_type: str) -> object:
        assert project_type == "landing"
        return self.candidate


class RecordingBuilder:
    def __init__(self) -> None:
        self.calls = 0

    async def build(
        self, canonical_ast: Mapping[str, object]
    ) -> tuple[ArtifactBuildFile, ...]:
        self.calls += 1
        assert canonical_ast["schema_version"] == "generation_ast_schema_v1"
        return (
            ArtifactBuildFile(
                "index.html", "text/html; charset=utf-8", b"<main/>"
            ),
        )


def _job() -> ArtifactGenerationJob:
    return ArtifactGenerationJob(
        job_id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        correlation_id=uuid4(),
        artifact_id=uuid4(),
        artifact_version_id=uuid4(),
        version_no=1,
        scope_version_id=uuid4(),
        scope_version_no=1,
        scope_version_hash="sha256:" + "1" * 64,
        project_type="landing",
        checkpoint_ref=None,
        checkpoint_hash=None,
    )


def _message(job: ArtifactGenerationJob) -> ArtifactGenerationMessage:
    return ArtifactGenerationMessage("1", uuid4(), job.job_id)


def test_checkpoint_recovery_never_rebuilds_and_manifest_is_last() -> None:
    candidate = json.loads(
        (
            ROOT
            / "evals/generation-output/fixtures/generation_ast_v1/fa_gen_landing_001.json"
        ).read_text(encoding="utf-8")
    )
    job = _job()
    store = MemoryStore(job)
    storage = MemoryStorage()
    builder = RecordingBuilder()
    runtime = ArtifactGenerationRuntime(
        store=store,
        candidate_source=CandidateSource(candidate),
        builder=builder,
        storage=storage,
    )
    first = asyncio.run(runtime.execute(_message(job)))
    second = asyncio.run(runtime.execute(_message(job)))
    assert first.status == second.status == "succeeded"
    assert builder.calls == 1
    assert store.finalizations == 2
    assert storage.writes[0].endswith("/checkpoint/build-bundle.tar")
    assert storage.writes[-1].endswith("/manifest.json")


def test_fixed_cli_builds_validated_local_static_bundle() -> None:
    source = VersionedSyntheticArtifactCandidateSource(repository_root=ROOT)
    candidate = asyncio.run(source.load(project_type="landing"))
    from aria_backend_application.generation_ast import (
        enrich_generation_candidate,
        validate_generation_candidate,
    )

    requirement_ids = {
        UUID(value)
        for page in candidate["pages"]
        for section in page["sections"]
        for value in section["source_requirement_ids"]
    }
    canonical = enrich_generation_candidate(
        validate_generation_candidate(candidate, pinned_requirement_ids=requirement_ids)
    )
    files = asyncio.run(FixedNodeArtifactBuilder(repository_root=ROOT).build(canonical))
    paths = {item.path for item in files}
    assert {
        "index.html",
        "contact/index.html",
        "assets/styles.css",
        "generation-fixtures/media.svg",
    } <= paths
    assert all(b"https://" not in item.content for item in files)


def test_identifier_only_message_fails_closed() -> None:
    with pytest.raises(ValueError):
        ArtifactGenerationMessage.from_payload(
            {
                "message_version": "1",
                "outbox_event_id": str(uuid4()),
                "job_id": str(uuid4()),
                "ast": {},
            }
        )
