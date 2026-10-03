from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from app.application.provider_quality_evaluation import EvaluationCase, EvaluationContractError
from app.infrastructure.ai.provider_quality_fixtures import load_versioned_synthetic_cases
from app.infrastructure.ai.provider_quality_prompt_package import (
    ApprovedPromptSchemaPackageV1,
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _cases() -> tuple[ApprovedPromptSchemaPackageV1, tuple[EvaluationCase, ...]]:
    package = ApprovedPromptSchemaPackageV1()
    return package, load_versioned_synthetic_cases(
        repository_root=_repository_root(), request_factory=package
    )


def _input(case: EvaluationCase) -> Mapping[str, object]:
    value = case.request["input"]
    assert isinstance(value, Mapping)
    return cast(Mapping[str, object], value)


def _mapping(value: object) -> Mapping[str, object]:
    assert isinstance(value, Mapping)
    return cast(Mapping[str, object], value)


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return cast(list[object], value)


def test_real_eval_requests_use_only_the_frozen_provider_visible_inputs() -> None:
    _, cases = _cases()
    expected = {
        "context_structuring_eval_v1": {"project_type", "sources"},
        "requirement_extraction_eval_v1": {
            "project_type",
            "context_version",
            "context_items",
        },
        "gap_detection_eval_v1": {
            "project_type",
            "context_items",
            "requirements",
            "completion_checklist_v1",
        },
    }
    forbidden = {
        "fixture_id",
        "gold",
        "expected_output",
        "expected_structured_output",
        "expected_count",
        "expected_labels",
        "evaluation_annotations",
        "provenance_expectations",
        "failure_expectations",
        "metadata",
        "scoring",
    }

    for case in cases:
        request = case.request
        assert set(request) == {"instructions", "input", "output_schema"}
        input_value = request["input"]
        assert isinstance(input_value, dict)
        assert set(input_value) == expected[case.eval_suite_version]
        assert forbidden.isdisjoint(input_value)
        serialized = json.dumps(request, ensure_ascii=False)
        assert '"gold"' not in serialized
        assert '"expected_output"' not in serialized
        assert '"evaluation_annotations"' not in serialized


def test_all_sixty_frozen_requests_fit_the_8000_utf8_byte_contract() -> None:
    _, cases = _cases()

    sizes = [
        len(
            json.dumps(
                case.request,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
        for case in cases
    ]

    assert len(cases) == 60
    assert max(sizes) <= 8_000


def test_gap_schema_prohibits_provider_critical_classification() -> None:
    _, cases = _cases()
    case = next(value for value in cases if value.eval_suite_version == "gap_detection_eval_v1")
    serialized = json.dumps(case.request["output_schema"], ensure_ascii=False)

    assert '"critical"' not in serialized
    assert '"rule_signals"' in serialized


def test_context_output_is_validated_and_receives_harness_candidate_ids() -> None:
    package, cases = _cases()
    case = next(value for value in cases if value.fixture_id == "fa_ctx_001")
    sources = _list(_input(case)["sources"])
    source = _mapping(sources[0])
    output = {
        "items": [
            {
                "item_type": "fact",
                "content": "کسب‌وکار کافه دانه است",
                "source_refs": [
                    {
                        "source_id": source["source_id"],
                        "source_version_id": source["source_version_id"],
                        "start_offset": None,
                        "end_offset": None,
                    }
                ],
                "confidence": 0.95,
                "rationale_short": None,
            }
        ]
    }

    normalized = asyncio.run(package.normalize(case=case, provider_output=output))

    normalized_root = _mapping(normalized)
    normalized_item = _mapping(_list(normalized_root["items"])[0])
    normalized_ref = _mapping(_list(normalized_item["source_refs"])[0])
    assert normalized_item["candidate_id"] == "fa_ctx_001_candidate_001"
    assert normalized_item["confidence"] == "0.95"
    assert normalized_ref["source_id"] == source["source_id"]
    assert normalized_ref["source_version_id"] == source["source_version_id"]


def test_requirement_output_rejects_supported_item_without_provenance() -> None:
    package, cases = _cases()
    case = next(value for value in cases if value.fixture_id == "fa_req_001")
    output = {
        "items": [
            {
                "title": "امکان رزرو میز",
                "description": "صفحه باید رزرو میز را ممکن کند.",
                "category": "functional",
                "priority": "must",
                "source_refs": [],
                "confidence": 0.9,
                "unsupported": False,
                "duplicate_group_key": None,
                "conflict_group_key": None,
            }
        ]
    }

    with pytest.raises(EvaluationContractError, match="supported_provenance_required"):
        asyncio.run(package.normalize(case=case, provider_output=output))


def test_domain_schema_failure_is_normalized_to_an_evaluation_failure() -> None:
    package, cases = _cases()
    case = next(value for value in cases if value.fixture_id == "fa_req_001")
    output = {
        "items": [
            {
                "title": "نیاز نامعتبر",
                "description": "دسته‌بندی خارج از قرارداد است.",
                "category": "invented",
                "priority": "must",
                "source_refs": [],
                "confidence": None,
                "unsupported": True,
                "duplicate_group_key": None,
                "conflict_group_key": None,
            }
        ]
    }

    with pytest.raises(EvaluationContractError, match="evaluation_output_invalid"):
        asyncio.run(package.normalize(case=case, provider_output=output))


def test_gap_critical_classification_is_owned_by_the_deterministic_rule_pack() -> None:
    package, cases = _cases()
    case = next(value for value in cases if value.fixture_id == "fa_gap_001")
    checklist = [_mapping(value) for value in _list(_input(case)["completion_checklist_v1"])]
    output = {
        "items": [],
        "rule_signals": [
            {
                "signal_type": "checklist_item",
                "signal_origin": "ai_candidate",
                "checklist_item_id": item["item_id"],
                "state": "missing",
                "supporting_context_item_ids": [],
                "candidate_index": None,
            }
            for item in checklist
        ],
    }

    normalized = asyncio.run(package.normalize(case=case, provider_output=output))

    normalized_root = _mapping(normalized)
    normalized_items = [_mapping(value) for value in _list(normalized_root["items"])]
    assert normalized_root["matched_critical_rule_ids"] == ["CGR-001"]
    assert normalized_items
    assert all(item["severity"] == "critical" for item in normalized_items)
    assert all(item["critical_rule_id"] == "CGR-001" for item in normalized_items)


def test_provider_critical_severity_fails_closed_even_if_adapter_schema_is_bypassed() -> None:
    package, cases = _cases()
    case = next(value for value in cases if value.fixture_id == "fa_gap_001")
    output = {
        "items": [
            {
                "gap_type": "missing_information",
                "severity": "critical",
                "explanation": "اطلاعات کافی نیست.",
                "source_refs": [],
                "affected_requirement_ids": [],
                "suggested_resolution_type": "provide_information",
            }
        ],
        "rule_signals": [],
    }

    with pytest.raises(
        EvaluationContractError,
        match="provider_critical_classification_prohibited",
    ):
        asyncio.run(package.normalize(case=case, provider_output=output))
