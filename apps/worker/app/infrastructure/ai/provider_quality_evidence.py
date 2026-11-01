from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.application.provider_quality_evaluation import (
    EvaluationContractError,
    EvaluationRunResult,
)


def build_safe_execution_report(
    *,
    eval_run_id: str,
    run: EvaluationRunResult,
    version_identity: Mapping[str, str],
) -> dict[str, object]:
    if not eval_run_id:
        raise EvaluationContractError("eval_run_id_required")
    safe_cases = [
        {
            "fixture_id": result.fixture_id,
            "eval_suite_version": result.eval_suite_version,
            "provider": result.provider,
            "model": result.model,
            "status": result.status,
            "failure_class": result.failure_class,
            "estimated_cost": _decimal_text(result.estimated_cost),
            "input_tokens": result.input_tokens,
            "cached_input_tokens": result.cached_input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        }
        for result in run.cases
    ]
    return {
        "eval_run_id": eval_run_id,
        "execution_manifest_hash": run.execution_manifest_hash,
        "invocation_count": run.invocation_count,
        "actual_spend": _decimal_text(run.actual_spend),
        "stopped_reason": run.stopped_reason,
        "quality_gate": "awaiting_human_review",
        "versions": dict(version_identity),
        "cases": safe_cases,
    }


class LocalReviewBundle:
    """Temporary synthetic output bundle; the caller must delete it after review."""

    def __init__(self, *, repository_root: Path, eval_run_id: str) -> None:
        if not eval_run_id or any(value in eval_run_id for value in ("/", "\\", "..")):
            raise EvaluationContractError("eval_run_id_invalid")
        self._root = (
            repository_root / ".local" / "eval-review-bundles" / eval_run_id
        ).resolve()
        allowed_root = (repository_root / ".local" / "eval-review-bundles").resolve()
        if self._root.parent != allowed_root:
            raise EvaluationContractError("review_bundle_path_invalid")

    @property
    def path(self) -> Path:
        return self._root

    def write(self, run: EvaluationRunResult) -> Path:
        self._root.mkdir(parents=True, exist_ok=False)
        output = self._root / "normalized-outputs.json"
        payload = {
            "execution_manifest_hash": run.execution_manifest_hash,
            "cases": [asdict(result) for result in run.cases],
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )
        return output

    def delete(self) -> None:
        if not self._root.exists():
            return
        for child in self._root.iterdir():
            if child.is_file():
                child.unlink()
            else:
                raise EvaluationContractError("review_bundle_contains_unexpected_entry")
        self._root.rmdir()


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _json_default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported review bundle value: {type(value).__name__}")
