from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from aria_backend_application.generation_ast import (
    GenerationAstValidationError,
    validate_generation_candidate,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "generation-output"
    / "fixtures"
    / "generation_ast_v1"
    / "fa_gen_landing_001.json"
)
CORPUS_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "generation-output"
    / "security"
    / "generated_runtime_security_v1"
    / "adversarial-corpus.json"
)


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pinned_requirement_ids(candidate: dict[str, object]) -> frozenset[UUID]:
    values: set[UUID] = set()
    for page in candidate["pages"]:  # type: ignore[index]
        for section in page["sections"]:  # type: ignore[index]
            values.update(
                UUID(value) for value in section["source_requirement_ids"]
            )
    return frozenset(values)


def _first_section(candidate: dict[str, object], component_type: str) -> dict[str, object]:
    for page in candidate["pages"]:  # type: ignore[index]
        for section in page["sections"]:  # type: ignore[index]
            if section["component_type"] == component_type:
                return section
    raise AssertionError(f"fixture is missing {component_type}")


def _mutate(candidate: dict[str, object], case: dict[str, object]) -> None:
    mutation = case["mutation"]
    if mutation == "hero_heading":
        _first_section(candidate, "Hero")["content"]["heading"] = case["value"]  # type: ignore[index]
    elif mutation == "component_type":
        _first_section(candidate, "Hero")["component_type"] = case["value"]
    elif mutation == "content_property":
        _first_section(candidate, "Hero")["content"][case["property"]] = case["value"]  # type: ignore[index]
    elif mutation == "target_path":
        _first_section(candidate, "Navbar")["content"]["links"][0]["target_path"] = case["value"]  # type: ignore[index]
    elif mutation == "asset_ref":
        candidate["assets"][0] = case["value"]  # type: ignore[index]
        _first_section(candidate, "Hero")["content"]["primary_media_asset_ref"] = case["value"]  # type: ignore[index]
    elif mutation == "page_path":
        candidate["pages"][0]["path"] = case["value"]  # type: ignore[index]
    elif mutation == "section_property":
        _first_section(candidate, "Hero")[case["property"]] = case["value"]
    else:  # pragma: no cover - corpus contract test protects this branch
        raise AssertionError(f"unknown mutation: {mutation}")


def test_0098_adversarial_corpus_is_versioned_and_complete() -> None:
    corpus = _load_json(CORPUS_PATH)
    assert corpus["suite_version"] == "generated_runtime_security_v1"
    assert corpus["fixture_version"] == "generation_ast_v1"
    assert {case["case_id"] for case in corpus["cases"]} == {
        "ast_text_markup_inert",
        "ast_unknown_component",
        "ast_unknown_property",
        "ast_javascript_navigation",
        "ast_remote_asset",
        "ast_data_asset",
        "ast_path_traversal",
        "ast_provider_owned_protection",
    }


def test_0098_markup_payload_remains_plain_application_data() -> None:
    candidate = _load_json(FIXTURE_PATH)
    case = next(
        case
        for case in _load_json(CORPUS_PATH)["cases"]
        if case["case_id"] == "ast_text_markup_inert"
    )
    _mutate(candidate, case)

    normalized = validate_generation_candidate(
        candidate,
        pinned_requirement_ids=_pinned_requirement_ids(candidate),
    )

    hero = _first_section(normalized, "Hero")
    assert hero["content"]["heading"] == case["value"]  # type: ignore[index]


@pytest.mark.parametrize(
    "case_id",
    [
        "ast_unknown_component",
        "ast_unknown_property",
        "ast_javascript_navigation",
        "ast_remote_asset",
        "ast_data_asset",
        "ast_path_traversal",
        "ast_provider_owned_protection",
    ],
)
def test_0098_adversarial_ast_mutations_fail_closed(case_id: str) -> None:
    candidate = _load_json(FIXTURE_PATH)
    case = next(
        case
        for case in _load_json(CORPUS_PATH)["cases"]
        if case["case_id"] == case_id
    )
    _mutate(candidate, case)

    with pytest.raises(GenerationAstValidationError) as captured:
        validate_generation_candidate(
            candidate,
            pinned_requirement_ids=_pinned_requirement_ids(candidate),
        )

    assert captured.value.code.startswith("GENERATION_")
    assert str(case["value"]) not in str(captured.value)
