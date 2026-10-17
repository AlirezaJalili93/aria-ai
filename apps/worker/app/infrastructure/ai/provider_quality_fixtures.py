from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, cast

from app.application.provider_quality_evaluation import (
    APPROVED_SUITE_COUNTS,
    EvaluationCase,
    EvaluationContractError,
)

EVAL_SUITE_PATHS = {
    "context_structuring_eval_v1": Path(
        "evals/context-structuring/context_structuring_eval_v1"
    ),
    "requirement_extraction_eval_v1": Path(
        "evals/requirement-extraction/requirement_extraction_eval_v1"
    ),
    "gap_detection_eval_v1": Path("evals/gap-detection/gap_detection_eval_v1"),
}


class VersionedEvaluationRequestFactory(Protocol):
    def materialize(
        self,
        *,
        eval_suite_version: str,
        fixture: Mapping[str, object],
        fixture_set_version: str,
        evaluation_rule_version: str,
    ) -> EvaluationCase: ...


def load_versioned_synthetic_cases(
    *,
    repository_root: Path,
    request_factory: VersionedEvaluationRequestFactory,
) -> tuple[EvaluationCase, ...]:
    cases: list[EvaluationCase] = []
    for suite, expected_count in APPROVED_SUITE_COUNTS.items():
        relative_root = EVAL_SUITE_PATHS[suite]
        suite_root = repository_root / relative_root
        manifest = _load_json(suite_root / "manifest.json")
        if manifest.get("eval_set_id") != suite:
            raise EvaluationContractError("evaluation_manifest_identity_invalid")
        if manifest.get("expected_fixture_count") != expected_count:
            raise EvaluationContractError("evaluation_manifest_count_invalid")
        manifest_ids = manifest.get("fixture_ids")
        if not isinstance(manifest_ids, list) or any(
            not isinstance(value, str) for value in manifest_ids
        ):
            raise EvaluationContractError("evaluation_manifest_fixture_ids_invalid")

        fixture_paths = sorted((suite_root / "fixtures").glob("*.json"))
        fixtures = tuple(_load_json(path) for path in fixture_paths)
        fixture_ids = [fixture.get("fixture_id") for fixture in fixtures]
        if fixture_ids != manifest_ids or len(fixtures) != expected_count:
            raise EvaluationContractError("evaluation_fixture_inventory_mismatch")

        fixture_set_version = _required_string(manifest, "version")
        evaluation_rule_version = _required_string(manifest, "metric_version")
        for fixture in fixtures:
            metadata = fixture.get("metadata")
            if not isinstance(metadata, dict) or metadata.get("synthetic") is not True:
                raise EvaluationContractError("customer_content_prohibited")
            if fixture.get("eval_set_id") != suite:
                raise EvaluationContractError("evaluation_fixture_suite_invalid")
            case = request_factory.materialize(
                eval_suite_version=suite,
                fixture=cast(Mapping[str, object], fixture),
                fixture_set_version=fixture_set_version,
                evaluation_rule_version=evaluation_rule_version,
            )
            if case.fixture_id != fixture.get("fixture_id") or not case.synthetic:
                raise EvaluationContractError("evaluation_materialization_identity_invalid")
            cases.append(case)
    return tuple(cases)


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationContractError("evaluation_fixture_read_failed") from error
    if not isinstance(value, dict):
        raise EvaluationContractError("evaluation_fixture_shape_invalid")
    return cast(dict[str, object], value)


def _required_string(value: Mapping[str, object], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise EvaluationContractError("evaluation_manifest_version_invalid")
    return result
