from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from aria_backend_application.generation_ast import (
    enrich_generation_candidate,
    validate_generation_candidate,
)
from aria_backend_application.preview_delivery import digest, page_file
from test_preview_publication_runtime import Storage, Store, setup

from app.application.artifact_generation_runtime import (
    ArtifactBuild,
    ArtifactGenerationJob,
    _candidate_requirement_ids,
    canonical_manifest_bytes,
)
from app.application.preview_publication_runtime import PreviewPublicationRuntime, source_prefix
from app.infrastructure.artifact_builder import FixedNodeArtifactBuilder
from app.infrastructure.preview_canonical_validator import FixedNodePreviewCanonicalValidator
from app.infrastructure.preview_storage import LocalSyntheticPreviewStorage
from app.infrastructure.preview_transformer import PreviewTransformer
from app.infrastructure.synthetic_artifact_candidate import (
    VersionedSyntheticArtifactCandidateSource,
)

ROOT = Path(__file__).parents[3]


@pytest.mark.parametrize("project_type", ["landing", "corporate", "portfolio"])
def test_actual_0100_bundle_satisfies_preview_profile(project_type: str) -> None:
    async def scenario() -> None:
        candidate = await VersionedSyntheticArtifactCandidateSource(repository_root=ROOT).load(
            project_type=project_type
        )
        validated = validate_generation_candidate(
            candidate, pinned_requirement_ids=_candidate_requirement_ids(candidate)
        )
        sequence = 0

        def next_id():
            nonlocal sequence
            sequence += 1
            return uuid5(NAMESPACE_URL, f"0102:{project_type}:{sequence}")

        ast = enrich_generation_candidate(validated, id_factory=next_id)
        files = await FixedNodeArtifactBuilder(repository_root=ROOT).build(ast)
        before = {f.path: digest(f.content) for f in files}
        pages = {p["path"]: page_file(p["path"]) for p in ast["pages"]}
        transformer = PreviewTransformer(ROOT)
        paths = set(before)
        for item in files:
            value = transformer.file(item.path, item.content, pages=pages, files=paths)
            assert value == transformer.file(item.path, item.content, pages=pages, files=paths)
        assert before == {f.path: digest(f.content) for f in files}

    asyncio.run(scenario())


@pytest.mark.parametrize("project_type", ["landing", "corporate", "portfolio"])
def test_real_bundle_runtime_reuses_canonical_validator_and_private_storage(tmp_path, project_type):
    async def scenario():
        _, message, job, _, _, _, _ = setup()
        candidate = await VersionedSyntheticArtifactCandidateSource(repository_root=ROOT).load(
            project_type=project_type
        )
        ast = enrich_generation_candidate(
            validate_generation_candidate(
                candidate, pinned_requirement_ids=_candidate_requirement_ids(candidate)
            )
        )
        files = await FixedNodeArtifactBuilder(repository_root=ROOT).build(ast)
        binding = job.binding
        artifact_job = ArtifactGenerationJob(
            job_id=uuid4(),
            account_id=binding.account_id,
            project_id=binding.project_id,
            correlation_id=uuid4(),
            artifact_id=binding.artifact_id,
            artifact_version_id=binding.artifact_version_id,
            version_no=binding.version_no,
            scope_version_id=uuid4(),
            scope_version_no=1,
            scope_version_hash="sha256:" + "1" * 64,
            project_type=project_type,
            checkpoint_ref=None,
            checkpoint_hash=None,
        )
        manifest = canonical_manifest_bytes(artifact_job, ArtifactBuild(ast, files))
        binding = replace(binding, source_hash=digest(manifest))
        job = replace(job, binding=binding)
        source = Storage({binding.source_ref: manifest})
        source.values.update(
            {source_prefix(binding) + "/files/" + f.path: f.content for f in files}
        )
        original = dict(source.values)
        destination = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)
        transformer = PreviewTransformer(ROOT)
        store = Store(job)
        runtime = PreviewPublicationRuntime(
            store=store,
            source=source,
            destination=destination,
            validator=FixedNodePreviewCanonicalValidator(repository_root=ROOT),
            transform=lambda p, v, pages, paths: transformer.file(p, v, pages=pages, files=paths),
            synthetic_sources=frozenset({(binding.artifact_version_id, binding.source_hash)}),
        )
        assert (await runtime.execute(message)).status == "succeeded"
        _, ref, manifest_hash = store.finalizations[0]
        persisted = await destination.read(ref)
        assert persisted is not None and digest(persisted) == manifest_hash
        assert source.values == original
        assert (await runtime.execute(message)).status == "already_completed"
        assert len(store.finalizations) == 1

    asyncio.run(scenario())
