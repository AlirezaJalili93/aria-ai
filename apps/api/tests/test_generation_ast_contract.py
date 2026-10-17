from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from aria_backend_application.generation_ast import (
    AssetAuthorization,
    FinalizeGenerationOutputCommand,
    GenerationAstValidationError,
    GenerationOutputService,
    enrich_generation_candidate,
    validate_generation_candidate,
)

ROOT = Path(__file__).parents[3]
FIXTURE_DIRECTORY = ROOT / "evals" / "generation-output" / "fixtures" / "generation_ast_v1"
ACCOUNT_ID = UUID("30000000-0000-4000-8000-000000000001")
PROJECT_ID = UUID("30000000-0000-4000-8000-000000000002")
JOB_ID = UUID("30000000-0000-4000-8000-000000000003")


class AllowAssets:
    def __init__(self, *, denied: frozenset[UUID] = frozenset()) -> None:
        self.denied = denied
        self.calls: list[tuple[UUID, UUID, tuple[UUID, ...]]] = []

    async def authorize_for_generation(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        asset_refs: tuple[UUID, ...],
    ) -> tuple[AssetAuthorization, ...]:
        self.calls.append((account_id, project_id, asset_refs))
        return tuple(
            AssetAuthorization(asset_ref, asset_ref not in self.denied)
            for asset_ref in asset_refs
        )


class AtomicFinalizer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.persisted: list[dict[str, object]] = []

    async def finalize_validated_output(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        generation_ast: Mapping[str, object],
    ) -> None:
        staged = {
            "account_id": account_id,
            "project_id": project_id,
            "job_id": job_id,
            "generation_ast": deepcopy(generation_ast),
        }
        if self.fail:
            raise RuntimeError("synthetic_atomic_failure")
        self.persisted.append(staged)


def _fixtures() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURE_DIRECTORY.glob("*.json"))
    ]


def _fixture(project_type: str) -> dict[str, Any]:
    return next(item for item in _fixtures() if item["project_type"] == project_type)


def _requirements(candidate: object) -> frozenset[UUID]:
    found: set[UUID] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "source_requirement_ids" and isinstance(child, list):
                    found.update(UUID(item) for item in child)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(candidate)
    return frozenset(found)


def _ids() -> Iterator[UUID]:
    number = 1000
    while True:
        yield UUID(int=number)
        number += 1


def _section(candidate: dict[str, Any], component_type: str) -> dict[str, Any]:
    return next(
        section
        for page in candidate["pages"]
        for section in page["sections"]
        if section["component_type"] == component_type
    )


@pytest.mark.parametrize("candidate", _fixtures())
def test_three_synthetic_project_types_validate_and_finalize_atomically(
    candidate: dict[str, Any],
) -> None:
    registry = AllowAssets()
    finalizer = AtomicFinalizer()
    ids = _ids()
    result = asyncio.run(
        GenerationOutputService(
            asset_registry=registry,
            finalizer=finalizer,
            id_factory=lambda: next(ids),
        ).execute(
            FinalizeGenerationOutputCommand(
                account_id=ACCOUNT_ID,
                project_id=PROJECT_ID,
                job_id=JOB_ID,
                candidate=candidate,
                pinned_requirement_ids=_requirements(candidate),
            )
        )
    )

    assert result["schema_version"] == "generation_ast_schema_v1"
    assert len(finalizer.persisted) == 1
    assert registry.calls[0][:2] == (ACCOUNT_ID, PROJECT_ID)
    seen: set[str] = set()
    for page in result["pages"]:
        assert page["page_id"] not in seen
        seen.add(page["page_id"])
        for section in page["sections"]:
            assert section["section_id"] not in seen
            seen.add(section["section_id"])
            assert section["protected_state"] == "unprotected"


def test_provider_identity_and_protection_are_rejected() -> None:
    candidate = _fixtures()[0]
    section = candidate["pages"][0]["sections"][0]
    section["section_id"] = "40000000-0000-4000-8000-000000000001"

    with pytest.raises(GenerationAstValidationError) as raised:
        validate_generation_candidate(candidate, pinned_requirement_ids=_requirements(candidate))

    assert raised.value.code == "GENERATION_APPLICATION_FIELD_FORBIDDEN"


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("layout", "GENERATION_LAYOUT_RESPONSIVE_MISMATCH"),
        ("media", "GENERATION_COMPONENT_CONTENT_INVALID"),
        ("asset_pair", "GENERATION_COMPONENT_CONTENT_INVALID"),
        ("navigation", "GENERATION_NAVIGATION_TARGET_INVALID"),
        ("remote_url", "GENERATION_SCHEMA_INVALID"),
    ],
)
def test_structural_and_security_mismatches_fail_closed(
    mutation: str, error_code: str
) -> None:
    candidate = _fixture("landing")
    hero = _section(candidate, "Hero")
    if mutation == "layout":
        hero["responsive_rule_ref"] = "responsive.grid_4_v1"
    elif mutation == "media":
        del hero["content"]["primary_media_asset_ref"]
        del hero["content"]["primary_media_alt_text"]
    elif mutation == "asset_pair":
        del hero["content"]["primary_media_alt_text"]
    elif mutation == "navigation":
        navbar = _section(candidate, "Navbar")
        navbar["content"]["links"][0]["target_path"] = "/missing"
    else:
        hero["content"]["remote_url"] = "https://example.invalid/image.png"

    with pytest.raises(GenerationAstValidationError) as raised:
        validate_generation_candidate(candidate, pinned_requirement_ids=_requirements(candidate))

    assert raised.value.code == error_code
    assert "example.invalid" not in str(raised.value)


def test_multiline_lf_is_preserved_while_single_line_lf_and_tab_are_rejected() -> None:
    candidate = _fixture("landing")
    hero = _section(candidate, "Hero")
    hero["content"]["body"] = "خط اول\r\nخط دوم"
    validated = validate_generation_candidate(
        candidate, pinned_requirement_ids=_requirements(candidate)
    )
    assert _section(validated, "Hero")["content"]["body"] == "خط اول\nخط دوم"

    invalid_heading = deepcopy(candidate)
    _section(invalid_heading, "Hero")["content"]["heading"] = "خط\nدوم"
    with pytest.raises(GenerationAstValidationError):
        validate_generation_candidate(
            invalid_heading, pinned_requirement_ids=_requirements(invalid_heading)
        )

    invalid_tab = deepcopy(candidate)
    _section(invalid_tab, "Hero")["content"]["body"] = "متن\tنامعتبر"
    with pytest.raises(GenerationAstValidationError):
        validate_generation_candidate(
            invalid_tab, pinned_requirement_ids=_requirements(invalid_tab)
        )


def test_simple_form_has_no_network_action_and_requires_unique_bounded_fields() -> None:
    candidate = _fixture("landing")
    form = _section(candidate, "SimpleForm")["content"]
    form["action"] = "https://example.invalid/submit"
    with pytest.raises(GenerationAstValidationError) as raised:
        validate_generation_candidate(candidate, pinned_requirement_ids=_requirements(candidate))
    assert raised.value.code == "GENERATION_SCHEMA_INVALID"

    duplicate = _fixture("landing")
    fields = _section(duplicate, "SimpleForm")["content"]["fields"]
    fields[1]["key"] = fields[0]["key"]
    with pytest.raises(GenerationAstValidationError) as raised:
        validate_generation_candidate(duplicate, pinned_requirement_ids=_requirements(duplicate))
    assert raised.value.code == "GENERATION_COMPONENT_CONTENT_INVALID"


def test_asset_authorization_failure_prevents_finalizer() -> None:
    candidate = _fixtures()[0]
    denied = UUID(candidate["assets"][0])
    finalizer = AtomicFinalizer()
    service = GenerationOutputService(
        asset_registry=AllowAssets(denied=frozenset({denied})),
        finalizer=finalizer,
    )

    with pytest.raises(GenerationAstValidationError) as raised:
        asyncio.run(
            service.execute(
                FinalizeGenerationOutputCommand(
                    account_id=ACCOUNT_ID,
                    project_id=PROJECT_ID,
                    job_id=JOB_ID,
                    candidate=candidate,
                    pinned_requirement_ids=_requirements(candidate),
                )
            )
        )

    assert raised.value.code == "GENERATION_ASSET_NOT_AUTHORIZED"
    assert finalizer.persisted == []


def test_persistence_failure_exposes_no_partial_valid_artifact() -> None:
    candidate = _fixtures()[0]
    finalizer = AtomicFinalizer(fail=True)
    service = GenerationOutputService(
        asset_registry=AllowAssets(),
        finalizer=finalizer,
    )

    with pytest.raises(RuntimeError, match="synthetic_atomic_failure"):
        asyncio.run(
            service.execute(
                FinalizeGenerationOutputCommand(
                    account_id=ACCOUNT_ID,
                    project_id=PROJECT_ID,
                    job_id=JOB_ID,
                    candidate=candidate,
                    pinned_requirement_ids=_requirements(candidate),
                )
            )
        )

    assert finalizer.persisted == []


def test_requirement_reference_must_belong_to_pinned_snapshot() -> None:
    candidate = _fixtures()[0]
    with pytest.raises(GenerationAstValidationError) as raised:
        validate_generation_candidate(candidate, pinned_requirement_ids=frozenset())
    assert raised.value.code == "GENERATION_REQUIREMENT_REFERENCE_INVALID"


def test_enrichment_does_not_mutate_provider_candidate() -> None:
    candidate = _fixtures()[0]
    validated = validate_generation_candidate(
        candidate, pinned_requirement_ids=_requirements(candidate)
    )
    original = deepcopy(validated)
    ids = _ids()
    canonical = enrich_generation_candidate(validated, id_factory=lambda: next(ids))

    assert validated == original
    assert canonical["schema_version"] == "generation_ast_schema_v1"
    assert "page_id" not in validated["pages"][0]
