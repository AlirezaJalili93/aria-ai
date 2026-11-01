from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from aria_backend_application.generation_ast import (
    enrich_generation_candidate,
    validate_generation_candidate,
)
from aria_backend_application.preview_delivery import PreviewError

from app.application.artifact_generation_runtime import _candidate_requirement_ids
from app.infrastructure.preview_canonical_validator import FixedNodePreviewCanonicalValidator

ROOT = Path(__file__).parents[3]


@pytest.mark.parametrize(
    "value",
    [
        {"schema_version": "generation_ast_schema_v1", "pages": [{"path": "/"}]},
        {"schema_version": "generation_ast_candidate_v1", "pages": []},
        {"schema_version": "generation_ast_schema_v1", "token": "prohibited marker"},
    ],
)
def test_partial_candidate_or_extra_field_cannot_skip_existing_canonical_validation(value):
    with pytest.raises(PreviewError, match="PREVIEW_SOURCE_INVALID") as caught:
        asyncio.run(FixedNodePreviewCanonicalValidator(repository_root=ROOT).validate(value))
    assert "prohibited" not in str(caught.value)


@pytest.mark.parametrize("change", ["root", "page", "section", "content", "duplicate_id"])
def test_full_content_validation_rejects_unknown_properties_without_repair(change):
    candidate = json.loads(
        (
            ROOT / "evals/generation-output/fixtures/generation_ast_v1/fa_gen_landing_001.json"
        ).read_text(encoding="utf-8")
    )
    ast = enrich_generation_candidate(
        validate_generation_candidate(
            candidate, pinned_requirement_ids=_candidate_requirement_ids(candidate)
        )
    )
    page, section = ast["pages"][0], ast["pages"][0]["sections"][0]
    if change == "duplicate_id":
        section["section_id"] = page["page_id"]
    else:
        target = {"root": ast, "page": page, "section": section, "content": section["content"]}[
            change
        ]
        target["prohibited_extra"] = "not accepted"
    before = json.dumps(ast, sort_keys=True)
    with pytest.raises(PreviewError, match="PREVIEW_SOURCE_INVALID"):
        asyncio.run(FixedNodePreviewCanonicalValidator(repository_root=ROOT).validate(ast))
    assert json.dumps(ast, sort_keys=True) == before
