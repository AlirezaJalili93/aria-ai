from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from app.application.provider_quality_evaluation import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationRunResult,
)
from app.infrastructure.ai.provider_quality_evidence import (
    LocalReviewBundle,
    build_safe_execution_report,
)
from app.infrastructure.ai.provider_quality_fixtures import (
    load_versioned_synthetic_cases,
)


class RequestFactory:
    def materialize(
        self,
        *,
        eval_suite_version: str,
        fixture: Mapping[str, object],
        fixture_set_version: str,
        evaluation_rule_version: str,
    ) -> EvaluationCase:
        fixture_id = fixture["fixture_id"]
        assert isinstance(fixture_id, str)
        return EvaluationCase(
            eval_suite_version=eval_suite_version,
            fixture_set_version=fixture_set_version,
            fixture_id=fixture_id,
            workflow_version="approved-workflow-v1",
            prompt_version="approved-prompt-v1",
            schema_version="approved-schema-v1",
            evaluation_rule_version=evaluation_rule_version,
            request={
                "instructions": "Synthetic evaluation.",
                "input": fixture["input"],
                "output_schema": {"type": "object"},
            },
        )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_with_sensitive_synthetic_output() -> EvaluationRunResult:
    return EvaluationRunResult(
        execution_manifest_hash="a" * 64,
        invocation_count=1,
        actual_spend=Decimal("0.01"),
        stopped_reason=None,
        cases=(
            EvaluationCaseResult(
                fixture_id="fa_ctx_001",
                eval_suite_version="context_structuring_eval_v1",
                provider="openai",
                model="gpt-5.6-terra",
                status="success",
                failure_class=None,
                estimated_cost=Decimal("0.01"),
                input_tokens=10,
                cached_input_tokens=0,
                output_tokens=10,
                latency_ms=5,
                normalized_output={"content": "متن مصنوعی حساس برای بازبینی"},
            ),
        ),
    )


def test_loader_uses_the_exact_three_versioned_synthetic_manifests() -> None:
    cases = load_versioned_synthetic_cases(
        repository_root=_repository_root(),
        request_factory=RequestFactory(),
    )

    assert len(cases) == 60
    assert len({case.fixture_id for case in cases}) == 60
    assert all(case.synthetic for case in cases)
    assert {case.eval_suite_version for case in cases} == {
        "context_structuring_eval_v1",
        "requirement_extraction_eval_v1",
        "gap_detection_eval_v1",
    }


def test_safe_report_excludes_normalized_fixture_output() -> None:
    report = build_safe_execution_report(
        eval_run_id="eval-safe-001",
        run=_run_with_sensitive_synthetic_output(),
        version_identity={"harness_version": "v1"},
    )
    serialized = json.dumps(report, ensure_ascii=False)

    assert "متن مصنوعی حساس برای بازبینی" not in serialized
    assert "normalized_output" not in serialized
    assert report["quality_gate"] == "awaiting_human_review"


def test_review_bundle_is_local_temporary_and_deletable(tmp_path: Path) -> None:
    bundle = LocalReviewBundle(repository_root=tmp_path, eval_run_id="eval-safe-001")

    output = bundle.write(_run_with_sensitive_synthetic_output())

    assert output.is_file()
    assert "متن مصنوعی حساس برای بازبینی" in output.read_text(encoding="utf-8")
    bundle.delete()
    assert not bundle.path.exists()
