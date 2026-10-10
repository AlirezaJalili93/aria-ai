from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.application.provider_quality_evaluation import EvaluationContractError
from app.infrastructure.ai.provider_quality_fixtures import (
    load_versioned_synthetic_cases,
)
from app.runtime.provider_quality_evaluation import (
    compose_controlled_provider_evaluation,
)
from app.runtime.provider_quality_evaluation_command import (
    PAID_EVALUATION_CONFIRMATION,
    ControlledEvaluationCommandResult,
    ControlledEvaluationCommandSettings,
    _provision_synthetic_account,
    build_execution_metadata,
    evaluation_account_id,
    safe_command_result,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": "postgresql://owner:secret@127.0.0.1:5432/aria_0086_eval",
        "OPENAI_API_KEY": "openai-secret-not-used",
        "GEMINI_API_KEY": "gemini-secret-not-used",
        "ARIA_EVAL_RUN_ID": "eval-0086-command-test",
        "ARIA_EVAL_DATABASE_CONFIRMED": PAID_EVALUATION_CONFIRMATION,
    }
    values.update(overrides)
    return values


def test_command_settings_require_exact_confirmation_before_execution() -> None:
    with pytest.raises(EvaluationContractError, match="paid_evaluation_confirmation_required"):
        ControlledEvaluationCommandSettings.from_environment(
            _environment(ARIA_EVAL_DATABASE_CONFIRMED="provision-only")
        )


@pytest.mark.parametrize(
    ("field", "error"),
    (
        ("DATABASE_URL", "evaluation_database_url_required"),
        ("OPENAI_API_KEY", "openai_api_key_required"),
        ("GEMINI_API_KEY", "gemini_api_key_required"),
        ("ARIA_EVAL_RUN_ID", "eval_run_id_invalid"),
    ),
)
def test_command_settings_fail_closed_for_missing_runtime_inputs(
    field: str,
    error: str,
) -> None:
    with pytest.raises(EvaluationContractError, match=error):
        ControlledEvaluationCommandSettings.from_environment(_environment(**{field: ""}))


def test_settings_repr_never_exposes_credentials_or_database_url() -> None:
    settings = ControlledEvaluationCommandSettings.from_environment(_environment())

    rendered = repr(settings)

    assert "openai-secret-not-used" not in rendered
    assert "gemini-secret-not-used" not in rendered
    assert "owner:secret" not in rendered
    assert PAID_EVALUATION_CONFIRMATION not in rendered


def test_command_builds_deterministic_synthetic_metadata_for_exact_matrix() -> None:
    composition = compose_controlled_provider_evaluation(
        database_url="postgresql://owner:secret@127.0.0.1:1/unused",
        openai_api_key="openai-secret-not-used",
        gemini_api_key="gemini-secret-not-used",
    )
    try:
        cases = load_versioned_synthetic_cases(
            repository_root=_repository_root(),
            request_factory=composition.request_factory,
        )
        account_id = evaluation_account_id("eval-0086-command-test")

        first = build_execution_metadata(
            cases=cases,
            composition=composition,
            account_id=account_id,
            eval_run_id="eval-0086-command-test",
        )
        replay = build_execution_metadata(
            cases=cases,
            composition=composition,
            account_id=account_id,
            eval_run_id="eval-0086-command-test",
        )
    finally:
        asyncio.run(composition.dispose())

    assert len(first) == 120
    assert first == replay
    assert {value.account_id for value in first.values()} == {account_id}
    assert {value.project_id for value in first.values()} == {None}
    assert {value.job_id for value in first.values()} == {None}
    assert {value.repair_no for value in first.values()} == {0}
    assert {value.task_type for value in first.values()} == {
        "context_structuring",
        "requirement_generation",
        "gap_detection",
    }


def test_safe_command_result_contains_no_provider_output_or_credentials() -> None:
    result = ControlledEvaluationCommandResult(
        eval_run_id="eval-0086-command-test",
        execution_manifest_hash="a" * 64,
        invocation_count=120,
        actual_spend="1.00000000",
        stopped_reason=None,
        safe_report_path=Path(".local/safe.json"),
        review_bundle_path=Path(".local/normalized-outputs.json"),
    )

    safe = safe_command_result(result)

    assert safe["status"] == "completed"
    assert set(safe) == {
        "status",
        "eval_run_id",
        "execution_manifest_hash",
        "invocation_count",
        "actual_spend",
        "stopped_reason",
        "safe_report_path",
        "review_bundle_path",
    }
    assert "normalized_output" not in safe
    assert "credential" not in safe


@pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL command evidence",
)
def test_synthetic_account_provisioning_is_idempotent_and_exact() -> None:
    assert TEST_DATABASE_URL is not None

    async def exercise() -> None:
        account_id = evaluation_account_id("eval-0086-command-postgres-test")
        await _provision_synthetic_account(
            database_url=TEST_DATABASE_URL,
            account_id=account_id,
        )
        await _provision_synthetic_account(
            database_url=TEST_DATABASE_URL,
            account_id=account_id,
        )
        engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                rows = (
                    await connection.execute(
                        text(
                            "SELECT plan_id, status FROM accounts "
                            "WHERE id=:account_id"
                        ),
                        {"account_id": account_id},
                    )
                ).all()
            assert [tuple(row) for row in rows] == [("free", "active")]
        finally:
            await engine.dispose()

    asyncio.run(exercise())
