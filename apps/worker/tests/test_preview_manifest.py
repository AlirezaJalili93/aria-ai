from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from aria_backend_application.preview_delivery import (
    PreviewBinding,
    PreviewError,
    canonical_json,
    digest,
    prepare_preview,
    verified_delivery_manifest,
)

from app.infrastructure.preview_transformer import PreviewTransformer

ROOT = Path(__file__).parents[3]


def fixture():
    transformer = PreviewTransformer(ROOT)
    content = (
        b'<html><head><link rel="stylesheet" href="/assets/styles.css"></head>'
        b"<body><main>synthetic</main></body></html>"
    )
    files = {
        "index.html": content,
        "assets/styles.css": transformer.source_css,
        "generation-fixtures/media.svg": transformer.source_svg,
    }
    artifact, version = uuid4(), uuid4()
    manifest = canonical_json(
        {
            "manifest_version": "artifact_manifest/v1",
            "artifact": {
                "artifact_id": str(artifact),
                "artifact_version_id": str(version),
                "version_no": 1,
            },
            "source": {
                "scope_version_id": str(uuid4()),
                "scope_version_no": 1,
                "scope_version_hash": "sha256:" + "1" * 64,
            },
            "contracts": {
                "generation_ast_schema": "generation_ast_schema/v1",
                "component_registry": "component_registry/v1",
                "responsive_rules": "responsive_rules/v1",
                "renderer_version": "0.1.0",
                "design_tokens_version": "0.1.0",
            },
            "canonical_ast": {
                "schema_version": "generation_ast_schema_v1",
                "pages": [{"path": "/"}],
            },
            "files": [
                {
                    "path": p,
                    "media_type": "text/html; charset=utf-8"
                    if p.endswith("html")
                    else "text/css; charset=utf-8"
                    if p.endswith("css")
                    else "image/svg+xml",
                    "size_bytes": len(v),
                    "sha256": digest(v),
                }
                for p, v in sorted(files.items())
            ],
        }
    )
    binding = PreviewBinding(
        account_id=uuid4(),
        project_id=uuid4(),
        artifact_id=artifact,
        artifact_version_id=version,
        version_no=1,
        representation_id=uuid4(),
        source_hash=digest(manifest),
        source_ref="private source reference",
    )
    return binding, manifest, files, transformer


def test_source_and_delivery_hashes_are_distinct_and_deterministic() -> None:
    binding, source, files, transformer = fixture()

    def transform(path, value, pages, paths):
        return transformer.file(path, value, pages=pages, files=paths)

    first = prepare_preview(binding, source, files, transform)
    assert first == prepare_preview(binding, source, files, transform)
    assert digest(first.manifest) != binding.source_hash
    metadata = verified_delivery_manifest(
        first.manifest, binding=binding, expected_hash=digest(first.manifest)
    )
    assert "canonical_ast" not in metadata
    assert "token" not in metadata and "host" not in metadata
    assert source not in repr(first).encode()
    assert digest(source) == binding.source_hash


@pytest.mark.parametrize("change", ["missing", "extra", "bytes", "metadata"])
def test_source_validation_finishes_before_any_transform(change: str) -> None:
    binding, source, files, _ = fixture()
    if change == "missing":
        files.pop("assets/styles.css")
    elif change == "extra":
        files["secret.json"] = b"synthetic marker"
    elif change == "bytes":
        files["index.html"] += b"corruption"
    else:
        source += b" "
    calls = []
    with pytest.raises(PreviewError):
        prepare_preview(binding, source, files, lambda *args: calls.append(args) or b"")
    assert calls == []


def test_manifest_cannot_be_rebound_to_another_tenant_or_version() -> None:
    binding, source, files, transformer = fixture()
    prepared = prepare_preview(
        binding,
        source,
        files,
        lambda p, v, pages, paths: transformer.file(p, v, pages=pages, files=paths),
    )
    for other in (
        replace(binding, account_id=uuid4()),
        replace(binding, artifact_version_id=uuid4()),
        replace(binding, representation_id=uuid4()),
    ):
        with pytest.raises(PreviewError, match="PREVIEW_DELIVERY_CONFLICT"):
            verified_delivery_manifest(
                prepared.manifest, binding=other, expected_hash=digest(prepared.manifest)
            )


def test_even_rehashed_extra_manifest_fields_are_rejected() -> None:
    binding, source, files, transformer = fixture()
    prepared = prepare_preview(
        binding,
        source,
        files,
        lambda p, v, pages, paths: transformer.file(p, v, pages=pages, files=paths),
    )
    value = json.loads(prepared.manifest)
    value["token"] = "synthetic prohibited marker"
    tampered = canonical_json(value)
    with pytest.raises(PreviewError, match="PREVIEW_DELIVERY_CONFLICT"):
        verified_delivery_manifest(tampered, binding=binding, expected_hash=digest(tampered))
