from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from aria_backend_application.gap_detection import CRITICAL_GAP_RULE_PACK_VERSION
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.application.provider_failure_policy import ProviderExecutionMetadata
from app.application.provider_quality_evaluation import (
    EVALUATION_HARNESS_VERSION,
    REASONING_CONFIGURATION_VERSION,
    EvaluationCase,
    EvaluationContractError,
    EvaluationPreflight,
)
from app.infrastructure.ai.provider_quality_evidence import (
    LocalReviewBundle,
    build_safe_execution_report,
)
from app.infrastructure.ai.provider_quality_fixtures import (
    load_versioned_synthetic_cases,
)
from app.infrastructure.ai.provider_quality_prompt_package import (
    COMPLETION_CHECKLIST_VERSION,
)
from app.runtime.provider_quality_evaluation import (
    ControlledEvaluationComposition,
    compose_controlled_provider_evaluation,
    normalize_async_database_url,
)

PAID_EVALUATION_CONFIRMATION = "execute-0086-controlled-paid-evaluation"


@dataclass(frozen=True, slots=True)
class ControlledEvaluationCommandSettings:
    database_url: str = field(repr=False)
    openai_api_key: str = field(repr=False)
    gemini_api_key: str = field(repr=False)
    eval_run_id: str
    database_confirmation: str = field(repr=False)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> ControlledEvaluationCommandSettings:
        values = os.environ if environ is None else environ
        settings = cls(
            database_url=values.get("DATABASE_URL", ""),
            openai_api_key=values.get("OPENAI_API_KEY", ""),
            gemini_api_key=values.get("GEMINI_API_KEY", ""),
            eval_run_id=values.get("ARIA_EVAL_RUN_ID", ""),
            database_confirmation=values.get("ARIA_EVAL_DATABASE_CONFIRMED", ""),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.database_confirmation != PAID_EVALUATION_CONFIRMATION:
            raise EvaluationContractError("paid_evaluation_confirmation_required")
        if not self.database_url.strip():
            raise EvaluationContractError("evaluation_database_url_required")
        if not self.openai_api_key.strip():
            raise EvaluationContractError("openai_api_key_required")
        if not self.gemini_api_key.strip():
            raise EvaluationContractError("gemini_api_key_required")
        if (
            not self.eval_run_id
            or any(value in self.eval_run_id for value in ("/", "\\", ".."))
        ):
            raise EvaluationContractError("eval_run_id_invalid")


@dataclass(frozen=True, slots=True)
class ControlledEvaluationCommandResult:
    eval_run_id: str
    execution_manifest_hash: str
    invocation_count: int
    actual_spend: str
    stopped_reason: str | None
    safe_report_path: Path
    review_bundle_path: Path


async def run_controlled_provider_evaluation(
    *,
    settings: ControlledEvaluationCommandSettings,
    repository_root: Path,
) -> ControlledEvaluationCommandResult:
    """Run the explicit 0086 matrix; callers must arrange human review and cleanup."""

    settings.validate()
    root = repository_root.resolve()
    review_bundle = LocalReviewBundle(
        repository_root=root,
        eval_run_id=settings.eval_run_id,
    )
    if review_bundle.path.exists():
        raise EvaluationContractError("review_bundle_already_exists")

    composition = compose_controlled_provider_evaluation(
        database_url=settings.database_url,
        openai_api_key=settings.openai_api_key,
        gemini_api_key=settings.gemini_api_key,
    )
    try:
        cases = load_versioned_synthetic_cases(
            repository_root=root,
            request_factory=composition.request_factory,
        )
        execution_at = datetime.now(UTC)
        preflight = await composition.evaluation.preflight(
            cases=cases,
            candidates=composition.candidates,
            execution_at=execution_at,
            paid_synthetic_evaluation_confirmed=True,
        )
        account_id = evaluation_account_id(settings.eval_run_id)
        await _provision_synthetic_account(
            database_url=settings.database_url,
            account_id=account_id,
        )
        run = await composition.evaluation.execute(
            preflight=preflight,
            metadata_by_case=build_execution_metadata(
                cases=cases,
                composition=composition,
                account_id=account_id,
                eval_run_id=settings.eval_run_id,
            ),
        )
        review_output = review_bundle.write(run)
        safe_report = build_safe_execution_report(
            eval_run_id=settings.eval_run_id,
            run=run,
            version_identity=build_version_identity(
                cases=cases,
                preflight=preflight,
            ),
        )
        safe_report_path = review_bundle.path / "safe-execution-report.json"
        safe_report_path.write_text(
            json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return ControlledEvaluationCommandResult(
            eval_run_id=settings.eval_run_id,
            execution_manifest_hash=run.execution_manifest_hash,
            invocation_count=run.invocation_count,
            actual_spend=str(run.actual_spend),
            stopped_reason=run.stopped_reason,
            safe_report_path=safe_report_path,
            review_bundle_path=review_output,
        )
    finally:
        await composition.dispose()


def evaluation_account_id(eval_run_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"aria-ai:0086:{eval_run_id}:account")


def build_execution_metadata(
    *,
    cases: tuple[EvaluationCase, ...],
    composition: ControlledEvaluationComposition,
    account_id: UUID,
    eval_run_id: str,
) -> dict[tuple[str, str, str], ProviderExecutionMetadata]:
    task_types = {
        "context_structuring_eval_v1": "context_structuring",
        "requirement_extraction_eval_v1": "requirement_generation",
        "gap_detection_eval_v1": "gap_detection",
    }
    values: dict[tuple[str, str, str], ProviderExecutionMetadata] = {}
    for candidate in composition.candidates:
        for case in cases:
            key = (candidate.provider, candidate.model, case.fixture_id)
            values[key] = ProviderExecutionMetadata(
                account_id=account_id,
                project_id=None,
                job_id=None,
                task_type=task_types[case.eval_suite_version],
                workflow_version=case.workflow_version,
                prompt_version=case.prompt_version,
                repair_no=0,
                correlation_id=uuid5(
                    NAMESPACE_URL,
                    ":".join(
                        (
                            "aria-ai",
                            "0086",
                            eval_run_id,
                            candidate.provider,
                            candidate.model,
                            case.fixture_id,
                        )
                    ),
                ),
            )
    return values


def build_version_identity(
    *,
    cases: tuple[EvaluationCase, ...],
    preflight: EvaluationPreflight,
) -> dict[str, str]:
    versions: dict[str, str] = {
        "harness_version": EVALUATION_HARNESS_VERSION,
        "reasoning_configuration_version": REASONING_CONFIGURATION_VERSION,
        "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
        "critical_gap_rule_pack_version": CRITICAL_GAP_RULE_PACK_VERSION,
        "candidate_price_versions": ",".join(
            f"{item.candidate.provider}/{item.candidate.model}/{item.price.pricing_version}"
            for item in preflight.candidates
        ),
    }
    for suite in sorted({case.eval_suite_version for case in cases}):
        suite_cases = tuple(case for case in cases if case.eval_suite_version == suite)
        for field_name in (
            "fixture_set_version",
            "workflow_version",
            "prompt_version",
            "schema_version",
            "evaluation_rule_version",
        ):
            values = {getattr(case, field_name) for case in suite_cases}
            if len(values) != 1:
                raise EvaluationContractError("evaluation_version_identity_inconsistent")
            versions[f"{suite}.{field_name}"] = values.pop()
    return versions


async def _provision_synthetic_account(*, database_url: str, account_id: UUID) -> None:
    engine = create_async_engine(
        normalize_async_database_url(database_url),
        poolclass=NullPool,
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL statement_timeout = '5s'"))
            await connection.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtextextended('aria:0086:synthetic-account', 0))"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO accounts (id, plan_id, status) "
                    "VALUES (:account_id, 'free', 'active') "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"account_id": account_id},
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT plan_id, status FROM accounts WHERE id=:account_id"
                    ),
                    {"account_id": account_id},
                )
            ).one_or_none()
            if row is None or tuple(row) != ("free", "active"):
                raise EvaluationContractError("evaluation_synthetic_account_conflict")
    finally:
        await engine.dispose()


def safe_command_result(result: ControlledEvaluationCommandResult) -> dict[str, object]:
    return {
        "status": "completed" if result.stopped_reason is None else "stopped",
        "eval_run_id": result.eval_run_id,
        "execution_manifest_hash": result.execution_manifest_hash,
        "invocation_count": result.invocation_count,
        "actual_spend": result.actual_spend,
        "stopped_reason": result.stopped_reason,
        "safe_report_path": str(result.safe_report_path),
        "review_bundle_path": str(result.review_bundle_path),
    }


def main() -> int:
    try:
        settings = ControlledEvaluationCommandSettings.from_environment()
        result = asyncio.run(
            run_controlled_provider_evaluation(
                settings=settings,
                repository_root=Path(__file__).resolve().parents[4],
            )
        )
    except EvaluationContractError as error:
        print(json.dumps({"status": "failed", "error_code": error.code}))
        return 1
    except (ValueError, RuntimeError, OSError, SQLAlchemyError):
        print(json.dumps({"status": "failed", "error_code": "evaluation_runtime_failed"}))
        return 1
    print(json.dumps(safe_command_result(result)))
    return 0 if result.stopped_reason is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
