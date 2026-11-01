from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol

from app.application.provider_adapter import (
    ProviderAdapterError,
    ProviderRequest,
    ProviderResult,
)
from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import (
    EVALUATION_INVOCATION_POLICY,
    FailureManagedProviderExecution,
    ProviderExecutionMetadata,
    ProviderFailureCoordinator,
)
from app.application.provider_pricing import (
    ProviderPriceCatalog,
    ProviderPriceVersion,
    TokenUsage,
    calculate_estimated_cost,
)

FIXTURES_PER_SUITE = 20
FIXTURES_PER_CANDIDATE = 60
CANDIDATE_COUNT = 2
MAX_TOTAL_INVOCATIONS = 120
MAX_INVOCATIONS_PER_CASE = 1
MAX_SERIALIZED_INPUT_BYTES = 8_000
MAX_OUTPUT_TOKENS = 25_000
MAX_TOTAL_BUDGET = Decimal("25.00")
EVALUATION_HARNESS_VERSION = "controlled-real-provider-eval-v1"
REASONING_CONFIGURATION_VERSION = "reasoning-medium-v1"

APPROVED_CANDIDATES = frozenset(
    {
        ("openai", "gpt-5.6-terra"),
        ("google", "gemini-3.8-flash"),
    }
)
APPROVED_SUITE_COUNTS = {
    "context_structuring_eval_v1": FIXTURES_PER_SUITE,
    "requirement_extraction_eval_v1": FIXTURES_PER_SUITE,
    "gap_detection_eval_v1": FIXTURES_PER_SUITE,
}
EVALUATION_PRICE_EXPIRY = {
    (
        "google",
        "gemini-3.8-flash",
        "google-gemini-3.8-flash-standard-intro-2026-09-02",
    ): datetime(2027, 1, 1, tzinfo=UTC),
}


@dataclass(frozen=True, slots=True)
class EvaluationSafetyBoundary:
    technical_retry: int = 0
    semantic_repair: int = 0
    fallback: int = 0
    hosted_execution: bool = False
    automatic_promotion: bool = False
    customer_content: bool = False


FROZEN_SAFETY_BOUNDARY = EvaluationSafetyBoundary()


class EvaluationContractError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    eval_suite_version: str
    fixture_set_version: str
    fixture_id: str
    workflow_version: str
    prompt_version: str
    schema_version: str
    evaluation_rule_version: str
    request: ProviderRequest
    synthetic: bool = True


@dataclass(frozen=True, slots=True)
class CandidatePreflight:
    candidate: ProviderCandidate
    price: ProviderPriceVersion
    maximum_invocation_cost: Decimal


@dataclass(frozen=True, slots=True)
class EvaluationPreflight:
    execution_manifest_hash: str
    execution_at: datetime
    cases: tuple[EvaluationCase, ...]
    candidates: tuple[CandidatePreflight, ...]
    planned_invocations: int
    maximum_reserved_cost: Decimal


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    fixture_id: str
    eval_suite_version: str
    provider: str
    model: str
    status: str
    failure_class: str | None
    estimated_cost: Decimal | None
    input_tokens: int | None
    cached_input_tokens: int | None
    output_tokens: int | None
    latency_ms: float | None
    normalized_output: object | None


@dataclass(frozen=True, slots=True)
class EvaluationRunResult:
    execution_manifest_hash: str
    invocation_count: int
    actual_spend: Decimal
    stopped_reason: str | None
    cases: tuple[EvaluationCaseResult, ...]


class ProviderModelPreflightPort(Protocol):
    async def verify(self, *, provider: str, model: str) -> None: ...


class SingleInvocationPort(Protocol):
    async def execute(
        self,
        *,
        candidate: ProviderCandidate,
        request: ProviderRequest,
        metadata: ProviderExecutionMetadata,
        pinned_price: ProviderPriceVersion,
    ) -> FailureManagedProviderExecution: ...


class EvaluationOutputNormalizer(Protocol):
    async def normalize(
        self,
        *,
        case: EvaluationCase,
        provider_output: object,
    ) -> object: ...


class FailureCoordinatorSingleInvocation:
    """Expose the 0069 single-writer path with the no-retry 0086 policy."""

    def __init__(self, coordinator: ProviderFailureCoordinator) -> None:
        if coordinator.invocation_policy != EVALUATION_INVOCATION_POLICY:
            raise ValueError("evaluation_invocation_policy_required")
        self._coordinator = coordinator

    async def execute(
        self,
        *,
        candidate: ProviderCandidate,
        request: ProviderRequest,
        metadata: ProviderExecutionMetadata,
        pinned_price: ProviderPriceVersion,
    ) -> FailureManagedProviderExecution:
        return await self._coordinator.execute(
            primary=candidate,
            request=request,
            metadata=metadata,
            fallback=None,
            fallback_authorization=None,
            required_primary_price=pinned_price,
        )


class ControlledProviderQualityEvaluation:
    """Manual, synthetic-only 0086 evaluation coordinator.

    The injected invocation port is the existing single-writer Usage owner. This
    application service neither persists Usage itself nor exposes review content.
    """

    def __init__(
        self,
        *,
        price_catalog: ProviderPriceCatalog,
        model_preflight: ProviderModelPreflightPort,
        invocation: SingleInvocationPort,
        output_normalizer: EvaluationOutputNormalizer,
    ) -> None:
        self._price_catalog = price_catalog
        self._model_preflight = model_preflight
        self._invocation = invocation
        self._output_normalizer = output_normalizer

    async def preflight(
        self,
        *,
        cases: tuple[EvaluationCase, ...],
        candidates: tuple[ProviderCandidate, ...],
        execution_at: datetime,
        paid_synthetic_evaluation_confirmed: bool,
    ) -> EvaluationPreflight:
        if not paid_synthetic_evaluation_confirmed:
            raise EvaluationContractError("paid_evaluation_confirmation_required")
        if execution_at.tzinfo is None:
            raise EvaluationContractError("evaluation_time_must_be_timezone_aware")
        _validate_cases(cases)
        _validate_candidates(candidates)

        materialized_requests = tuple(_serialize_request(case.request) for case in cases)
        if any(len(value) > MAX_SERIALIZED_INPUT_BYTES for value in materialized_requests):
            raise EvaluationContractError("evaluation_input_too_large")

        candidate_preflights: list[CandidatePreflight] = []
        total_reservation = Decimal("0")
        for candidate in candidates:
            await self._model_preflight.verify(
                provider=candidate.provider,
                model=candidate.model,
            )
            price = await self._price_catalog.resolve(
                provider=candidate.provider,
                model=candidate.model,
                provider_execution_at=execution_at,
            )
            expires_at = EVALUATION_PRICE_EXPIRY.get(
                (candidate.provider, candidate.model, price.pricing_version)
            )
            if expires_at is not None and execution_at >= expires_at:
                raise EvaluationContractError("evaluation_price_version_expired")
            if price.currency != "USD":
                raise EvaluationContractError("evaluation_price_currency_unsupported")
            maximum_cost = _maximum_invocation_cost(price)
            total_reservation += maximum_cost * FIXTURES_PER_CANDIDATE
            candidate_preflights.append(
                CandidatePreflight(
                    candidate=candidate,
                    price=price,
                    maximum_invocation_cost=maximum_cost,
                )
            )

        planned_invocations = len(cases) * len(candidates)
        if planned_invocations != MAX_TOTAL_INVOCATIONS:
            raise EvaluationContractError("evaluation_matrix_incomplete")
        if total_reservation > MAX_TOTAL_BUDGET:
            raise EvaluationContractError("evaluation_budget_preflight_failed")

        return EvaluationPreflight(
            execution_manifest_hash=_manifest_hash(
                cases=cases,
                candidates=tuple(candidate_preflights),
            ),
            execution_at=execution_at,
            cases=cases,
            candidates=tuple(candidate_preflights),
            planned_invocations=planned_invocations,
            maximum_reserved_cost=total_reservation,
        )

    async def execute(
        self,
        *,
        preflight: EvaluationPreflight,
        metadata_by_case: dict[tuple[str, str, str], ProviderExecutionMetadata],
    ) -> EvaluationRunResult:
        if preflight.planned_invocations != MAX_TOTAL_INVOCATIONS:
            raise EvaluationContractError("evaluation_preflight_not_frozen")

        invocation_count = 0
        actual_spend = Decimal("0")
        results: list[EvaluationCaseResult] = []
        stopped_reason: str | None = None

        for pinned in preflight.candidates:
            for case in preflight.cases:
                if invocation_count >= MAX_TOTAL_INVOCATIONS:
                    stopped_reason = "evaluation_invocation_cap_reached"
                    break
                if actual_spend + pinned.maximum_invocation_cost > MAX_TOTAL_BUDGET:
                    stopped_reason = "evaluation_budget_cap_reached"
                    break
                metadata_key = (pinned.candidate.provider, pinned.candidate.model, case.fixture_id)
                metadata = metadata_by_case.get(metadata_key)
                if metadata is None:
                    raise EvaluationContractError("evaluation_metadata_missing")

                invocation_count += 1
                try:
                    execution = await self._invocation.execute(
                        candidate=pinned.candidate,
                        request=case.request,
                        metadata=metadata,
                        pinned_price=pinned.price,
                    )
                except ProviderAdapterError as error:
                    failure_cost = _failure_cost(error=error, price=pinned.price)
                    if failure_cost is not None:
                        actual_spend += failure_cost
                    results.append(
                        EvaluationCaseResult(
                            fixture_id=case.fixture_id,
                            eval_suite_version=case.eval_suite_version,
                            provider=pinned.candidate.provider,
                            model=pinned.candidate.model,
                            status="failed",
                            failure_class=error.error_class,
                            estimated_cost=failure_cost,
                            input_tokens=(error.usage.input_tokens if error.usage else None),
                            cached_input_tokens=(
                                error.usage.cached_input_tokens if error.usage else None
                            ),
                            output_tokens=(error.usage.output_tokens if error.usage else None),
                            latency_ms=(error.usage.latency_ms if error.usage else None),
                            normalized_output=None,
                        )
                    )
                    if error.usage is None:
                        stopped_reason = "evaluation_accounting_unavailable"
                        break
                    continue

                _verify_execution_price(execution.price, pinned.price)
                _verify_usage_within_caps(execution.result)
                invocation_cost = calculate_estimated_cost(
                    pinned.price,
                    TokenUsage(
                        execution.result.input_tokens,
                        execution.result.cached_input_tokens,
                        execution.result.output_tokens,
                    ),
                )
                actual_spend += invocation_cost
                try:
                    normalized_output = await self._output_normalizer.normalize(
                        case=case,
                        provider_output=execution.result.data,
                    )
                except EvaluationContractError:
                    results.append(
                        _invalid_output_result(
                            case=case,
                            candidate=pinned.candidate,
                            result=execution.result,
                            cost=invocation_cost,
                        )
                    )
                    continue
                results.append(
                    _successful_result(
                        case=case,
                        candidate=pinned.candidate,
                        result=execution.result,
                        cost=invocation_cost,
                        normalized_output=normalized_output,
                    )
                )
            if stopped_reason is not None:
                break

        return EvaluationRunResult(
            execution_manifest_hash=preflight.execution_manifest_hash,
            invocation_count=invocation_count,
            actual_spend=actual_spend,
            stopped_reason=stopped_reason,
            cases=tuple(results),
        )


def _validate_cases(cases: tuple[EvaluationCase, ...]) -> None:
    if len(cases) != FIXTURES_PER_CANDIDATE:
        raise EvaluationContractError("evaluation_fixture_count_invalid")
    fixture_ids = [case.fixture_id for case in cases]
    if len(set(fixture_ids)) != len(fixture_ids):
        raise EvaluationContractError("evaluation_fixture_id_duplicate")
    suite_counts = {
        suite: sum(case.eval_suite_version == suite for case in cases)
        for suite in APPROVED_SUITE_COUNTS
    }
    if suite_counts != APPROVED_SUITE_COUNTS:
        raise EvaluationContractError("evaluation_suite_inventory_invalid")
    if any(not case.synthetic for case in cases):
        raise EvaluationContractError("customer_content_prohibited")
    for case in cases:
        if not all(
            (
                case.fixture_set_version,
                case.workflow_version,
                case.prompt_version,
                case.schema_version,
                case.evaluation_rule_version,
            )
        ):
            raise EvaluationContractError("evaluation_version_identity_required")


def _validate_candidates(candidates: tuple[ProviderCandidate, ...]) -> None:
    identities = {(candidate.provider, candidate.model) for candidate in candidates}
    if len(candidates) != CANDIDATE_COUNT or identities != APPROVED_CANDIDATES:
        raise EvaluationContractError("evaluation_candidate_matrix_invalid")


def _serialize_request(request: ProviderRequest) -> bytes:
    try:
        return json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise EvaluationContractError("evaluation_request_not_serializable") from error


def _maximum_invocation_cost(price: ProviderPriceVersion) -> Decimal:
    return calculate_estimated_cost(
        price,
        TokenUsage(
            input_tokens=MAX_SERIALIZED_INPUT_BYTES,
            cached_input_tokens=0,
            output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )


def _manifest_hash(
    *,
    cases: tuple[EvaluationCase, ...],
    candidates: tuple[CandidatePreflight, ...],
) -> str:
    payload = {
        "harness_version": EVALUATION_HARNESS_VERSION,
        "reasoning_configuration_version": REASONING_CONFIGURATION_VERSION,
        "limits": {
            "max_total_invocations": MAX_TOTAL_INVOCATIONS,
            "max_serialized_input_bytes": MAX_SERIALIZED_INPUT_BYTES,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "max_total_budget": str(MAX_TOTAL_BUDGET),
        },
        "cases": [
            {
                "eval_suite_version": case.eval_suite_version,
                "fixture_set_version": case.fixture_set_version,
                "fixture_id": case.fixture_id,
                "workflow_version": case.workflow_version,
                "prompt_version": case.prompt_version,
                "schema_version": case.schema_version,
                "evaluation_rule_version": case.evaluation_rule_version,
                "request_hash": hashlib.sha256(_serialize_request(case.request)).hexdigest(),
            }
            for case in cases
        ],
        "candidates": [
            {
                "provider": candidate.candidate.provider,
                "model": candidate.candidate.model,
                "pricing_version": candidate.price.pricing_version,
            }
            for candidate in candidates
        ],
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _verify_execution_price(
    actual: ProviderPriceVersion,
    expected: ProviderPriceVersion,
) -> None:
    if (
        actual.provider,
        actual.model,
        actual.pricing_version,
        actual.currency,
    ) != (
        expected.provider,
        expected.model,
        expected.pricing_version,
        expected.currency,
    ):
        raise EvaluationContractError("evaluation_price_version_changed")


def _verify_usage_within_caps(result: ProviderResult) -> None:
    if result.input_tokens > MAX_SERIALIZED_INPUT_BYTES or result.output_tokens > MAX_OUTPUT_TOKENS:
        raise EvaluationContractError("evaluation_usage_cap_exceeded")


def _failure_cost(
    *,
    error: ProviderAdapterError,
    price: ProviderPriceVersion,
) -> Decimal | None:
    if error.usage is None:
        return None
    if (
        error.usage.input_tokens > MAX_SERIALIZED_INPUT_BYTES
        or error.usage.output_tokens > MAX_OUTPUT_TOKENS
    ):
        raise EvaluationContractError("evaluation_usage_cap_exceeded")
    return calculate_estimated_cost(
        price,
        TokenUsage(
            error.usage.input_tokens,
            error.usage.cached_input_tokens,
            error.usage.output_tokens,
        ),
    )


def _successful_result(
    *,
    case: EvaluationCase,
    candidate: ProviderCandidate,
    result: ProviderResult,
    cost: Decimal,
    normalized_output: object,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        fixture_id=case.fixture_id,
        eval_suite_version=case.eval_suite_version,
        provider=candidate.provider,
        model=candidate.model,
        status=result.status,
        failure_class=None,
        estimated_cost=cost,
        input_tokens=result.input_tokens,
        cached_input_tokens=result.cached_input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        normalized_output=normalized_output,
    )


def _invalid_output_result(
    *,
    case: EvaluationCase,
    candidate: ProviderCandidate,
    result: ProviderResult,
    cost: Decimal,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        fixture_id=case.fixture_id,
        eval_suite_version=case.eval_suite_version,
        provider=candidate.provider,
        model=candidate.model,
        status="failed",
        failure_class="invalid_response",
        estimated_cost=cost,
        input_tokens=result.input_tokens,
        cached_input_tokens=result.cached_input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        normalized_output=None,
    )


assert EVALUATION_INVOCATION_POLICY.max_primary_attempts == MAX_INVOCATIONS_PER_CASE
assert EVALUATION_INVOCATION_POLICY.max_fallback_attempts == 0
