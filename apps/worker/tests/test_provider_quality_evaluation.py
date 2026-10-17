from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.provider_adapter import ProviderAdapterError, ProviderResult
from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import (
    EVALUATION_INVOCATION_POLICY,
    FailureManagedProviderExecution,
    ProviderExecutionMetadata,
    ProviderFailureCoordinator,
)
from app.application.provider_pricing import ProviderPriceMismatchError, ProviderPriceVersion
from app.application.provider_quality_evaluation import (
    MAX_TOTAL_INVOCATIONS,
    ControlledProviderQualityEvaluation,
    EvaluationCase,
    EvaluationContractError,
    FailureCoordinatorSingleInvocation,
)


class UnusedAdapter:
    async def execute(self, request: object) -> ProviderResult:
        del request
        raise AssertionError("adapter must be invoked only by the metered invocation port")


class CountingAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, request: object) -> ProviderResult:
        del request
        self.calls += 1
        raise AssertionError("changed price must fail before Provider invocation")


class FixedCatalog:
    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion:
        del provider_execution_at
        if provider == "openai":
            input_rate, cached_rate, output_rate = "2", "0.2", "12"
        else:
            input_rate, cached_rate, output_rate = "0.75", "0.075", "3.75"
        return ProviderPriceVersion(
            provider=provider,
            model=model,
            pricing_version=f"{provider}-2026-09-30",
            currency="USD",
            input_rate_per_1m=Decimal(input_rate),
            cached_input_rate_per_1m=Decimal(cached_rate),
            output_rate_per_1m=Decimal(output_rate),
            effective_from=datetime(2026, 9, 30, tzinfo=UTC),
        )


class RecordingModelPreflight:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def verify(self, *, provider: str, model: str) -> None:
        self.calls.append((provider, model))


class RecordingInvocation:
    def __init__(self, catalog: FixedCatalog) -> None:
        self.catalog = catalog
        self.calls: list[tuple[str, str, str]] = []

    async def execute(
        self,
        *,
        candidate: ProviderCandidate,
        request: object,
        metadata: ProviderExecutionMetadata,
        pinned_price: ProviderPriceVersion,
    ) -> FailureManagedProviderExecution:
        del request
        self.calls.append((candidate.provider, candidate.model, metadata.task_type))
        price = await self.catalog.resolve(
            provider=candidate.provider,
            model=candidate.model,
            provider_execution_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
        assert price == pinned_price
        return FailureManagedProviderExecution(
            result=ProviderResult(
                data={"items": []},
                provider=candidate.provider,
                model=candidate.model,
                provider_request_id="safe-id",
                input_tokens=100,
                cached_input_tokens=0,
                output_tokens=100,
                latency_ms=10,
                status="success",
            ),
            price=price,
            provider_attempt_id=uuid4(),
            retry_no=0,
            used_fallback=False,
        )


class UnavailableInvocation(RecordingInvocation):
    async def execute(
        self,
        *,
        candidate: ProviderCandidate,
        request: object,
        metadata: ProviderExecutionMetadata,
        pinned_price: ProviderPriceVersion,
    ) -> FailureManagedProviderExecution:
        del candidate, request, metadata, pinned_price
        self.calls.append(("openai", "gpt-5.6-terra", "context_structuring"))
        raise ProviderAdapterError("timeout", retryable=True)


class RecordingLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class NoSleep:
    async def sleep(self, delay_seconds: float) -> None:
        raise AssertionError(f"evaluation must not sleep for retry: {delay_seconds}")


class FixedRandom:
    def random(self) -> float:
        return 0.5


class PassThroughNormalizer:
    async def normalize(self, *, case: EvaluationCase, provider_output: object) -> object:
        del case
        return provider_output


def _candidates() -> tuple[ProviderCandidate, ...]:
    return (
        ProviderCandidate("openai", "gpt-5.6-terra", UnusedAdapter()),
        ProviderCandidate("google", "gemini-3.8-flash", UnusedAdapter()),
    )


def _cases() -> tuple[EvaluationCase, ...]:
    definitions = (
        ("context_structuring_eval_v1", "fa_ctx", "ai-01-v1"),
        ("requirement_extraction_eval_v1", "fa_req", "ai-02-v1"),
        ("gap_detection_eval_v1", "fa_gap", "ai-03-v1"),
    )
    return tuple(
        EvaluationCase(
            eval_suite_version=suite,
            fixture_set_version="1",
            fixture_id=f"{prefix}_{index:03d}",
            workflow_version=workflow,
            prompt_version=f"{workflow}-prompt-v1",
            schema_version=f"{workflow}-schema-v1",
            evaluation_rule_version="1",
            request={
                "instructions": "Synthetic Persian evaluation only.",
                "input": {"fixture_id": f"{prefix}_{index:03d}"},
                "output_schema": {"type": "object", "additionalProperties": True},
            },
        )
        for suite, prefix, workflow in definitions
        for index in range(1, 21)
    )


def _metadata(
    cases: tuple[EvaluationCase, ...],
) -> dict[tuple[str, str, str], ProviderExecutionMetadata]:
    values: dict[tuple[str, str, str], ProviderExecutionMetadata] = {}
    for candidate in _candidates():
        for case in cases:
            values[(candidate.provider, candidate.model, case.fixture_id)] = (
                ProviderExecutionMetadata(
                    account_id=uuid4(),
                    project_id=uuid4(),
                    job_id=uuid4(),
                    task_type=case.eval_suite_version,
                    workflow_version=case.workflow_version,
                    prompt_version=case.prompt_version,
                    repair_no=0,
                    correlation_id=uuid4(),
                )
            )
    return values


def test_preflight_freezes_exact_matrix_and_24945_reservation() -> None:
    catalog = FixedCatalog()
    verifier = RecordingModelPreflight()
    invocation = RecordingInvocation(catalog)
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=verifier,
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )

    preflight = asyncio.run(
        harness.preflight(
            cases=_cases(),
            candidates=_candidates(),
            execution_at=datetime(2026, 9, 30, tzinfo=UTC),
            paid_synthetic_evaluation_confirmed=True,
        )
    )

    assert preflight.planned_invocations == 120
    assert preflight.maximum_reserved_cost == Decimal("24.94500000")
    assert len(preflight.execution_manifest_hash) == 64
    assert verifier.calls == [
        ("openai", "gpt-5.6-terra"),
        ("google", "gemini-3.8-flash"),
    ]
    assert invocation.calls == []


def test_expired_introductory_price_fails_before_provider_invocation() -> None:
    class FrozenIntroCatalog(FixedCatalog):
        async def resolve(
            self,
            *,
            provider: str,
            model: str,
            provider_execution_at: datetime,
        ) -> ProviderPriceVersion:
            price = await super().resolve(
                provider=provider,
                model=model,
                provider_execution_at=provider_execution_at,
            )
            if provider != "google":
                return price
            return ProviderPriceVersion(
                provider=price.provider,
                model=price.model,
                pricing_version=(
                    "google-gemini-3.8-flash-standard-intro-2026-09-02"
                ),
                currency=price.currency,
                input_rate_per_1m=price.input_rate_per_1m,
                cached_input_rate_per_1m=price.cached_input_rate_per_1m,
                output_rate_per_1m=price.output_rate_per_1m,
                effective_from=datetime(2026, 9, 2, tzinfo=UTC),
            )

    catalog = FrozenIntroCatalog()
    invocation = RecordingInvocation(catalog)
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=RecordingModelPreflight(),
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )

    with pytest.raises(EvaluationContractError, match="evaluation_price_version_expired"):
        asyncio.run(
            harness.preflight(
                cases=_cases(),
                candidates=_candidates(),
                execution_at=datetime(2027, 1, 1, tzinfo=UTC),
                paid_synthetic_evaluation_confirmed=True,
            )
        )

    assert invocation.calls == []


def test_missing_manual_confirmation_fails_before_model_or_provider_call() -> None:
    catalog = FixedCatalog()
    verifier = RecordingModelPreflight()
    invocation = RecordingInvocation(catalog)
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=verifier,
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )

    with pytest.raises(EvaluationContractError, match="paid_evaluation_confirmation_required"):
        asyncio.run(
            harness.preflight(
                cases=_cases(),
                candidates=_candidates(),
                execution_at=datetime(2026, 9, 30, tzinfo=UTC),
                paid_synthetic_evaluation_confirmed=False,
            )
        )

    assert verifier.calls == []
    assert invocation.calls == []


def test_oversize_request_fails_before_remote_model_preflight() -> None:
    catalog = FixedCatalog()
    verifier = RecordingModelPreflight()
    invocation = RecordingInvocation(catalog)
    cases = list(_cases())
    first = cases[0]
    cases[0] = EvaluationCase(
        eval_suite_version=first.eval_suite_version,
        fixture_set_version=first.fixture_set_version,
        fixture_id=first.fixture_id,
        workflow_version=first.workflow_version,
        prompt_version=first.prompt_version,
        schema_version=first.schema_version,
        evaluation_rule_version=first.evaluation_rule_version,
        request={
            "instructions": "x" * 8_001,
            "input": {},
            "output_schema": {"type": "object"},
        },
    )
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=verifier,
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )

    with pytest.raises(EvaluationContractError, match="evaluation_input_too_large"):
        asyncio.run(
            harness.preflight(
                cases=tuple(cases),
                candidates=_candidates(),
                execution_at=datetime(2026, 9, 30, tzinfo=UTC),
                paid_synthetic_evaluation_confirmed=True,
            )
        )

    assert verifier.calls == []
    assert invocation.calls == []


def test_execution_attempts_each_case_once_and_never_exceeds_120_calls() -> None:
    cases = _cases()
    catalog = FixedCatalog()
    invocation = RecordingInvocation(catalog)
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=RecordingModelPreflight(),
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )
    preflight = asyncio.run(
        harness.preflight(
            cases=cases,
            candidates=_candidates(),
            execution_at=datetime(2026, 9, 30, tzinfo=UTC),
            paid_synthetic_evaluation_confirmed=True,
        )
    )

    result = asyncio.run(
        harness.execute(preflight=preflight, metadata_by_case=_metadata(cases))
    )

    assert result.invocation_count == MAX_TOTAL_INVOCATIONS
    assert len(invocation.calls) == MAX_TOTAL_INVOCATIONS
    assert len(result.cases) == MAX_TOTAL_INVOCATIONS
    assert result.stopped_reason is None
    assert result.actual_spend < Decimal("25")


def test_unknown_timeout_accounting_stops_without_retrying() -> None:
    cases = _cases()
    catalog = FixedCatalog()
    invocation = UnavailableInvocation(catalog)
    harness = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=RecordingModelPreflight(),
        invocation=invocation,
        output_normalizer=PassThroughNormalizer(),
    )
    preflight = asyncio.run(
        harness.preflight(
            cases=cases,
            candidates=_candidates(),
            execution_at=datetime(2026, 9, 30, tzinfo=UTC),
            paid_synthetic_evaluation_confirmed=True,
        )
    )

    result = asyncio.run(
        harness.execute(preflight=preflight, metadata_by_case=_metadata(cases))
    )

    assert result.invocation_count == 1
    assert len(invocation.calls) == 1
    assert result.stopped_reason == "evaluation_accounting_unavailable"
    assert result.cases[0].failure_class == "timeout"


def test_changed_price_version_fails_before_paid_provider_invocation() -> None:
    catalog = FixedCatalog()
    adapter = CountingAdapter()
    candidate = ProviderCandidate("openai", "gpt-5.6-terra", adapter)
    ledger = RecordingLedger()
    coordinator = ProviderFailureCoordinator(
        catalog=catalog,
        usage_ledger=ledger,  # type: ignore[arg-type]
        sleeper=NoSleep(),
        random_source=FixedRandom(),
        utc_clock=lambda: datetime(2026, 9, 30, tzinfo=UTC),
        policy=EVALUATION_INVOCATION_POLICY,
    )
    invocation = FailureCoordinatorSingleInvocation(coordinator)
    stale_price = asyncio.run(
        catalog.resolve(
            provider="openai",
            model="gpt-5.6-terra",
            provider_execution_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
    )
    stale_price = ProviderPriceVersion(
        provider=stale_price.provider,
        model=stale_price.model,
        pricing_version="older-price",
        currency=stale_price.currency,
        input_rate_per_1m=stale_price.input_rate_per_1m,
        cached_input_rate_per_1m=stale_price.cached_input_rate_per_1m,
        output_rate_per_1m=stale_price.output_rate_per_1m,
        effective_from=stale_price.effective_from,
    )

    with pytest.raises(ProviderPriceMismatchError, match="provider_price_version_changed"):
        asyncio.run(
            invocation.execute(
                candidate=candidate,
                request={"instructions": "safe", "input": {}, "output_schema": {}},
                metadata=_metadata(_cases())[("openai", "gpt-5.6-terra", "fa_ctx_001")],
                pinned_price=stale_price,
            )
        )

    assert adapter.calls == 0
    assert ledger.records == []
