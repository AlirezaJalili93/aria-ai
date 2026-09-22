from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import create_event_logger

from app.application.provider_adapter import (
    ProviderAdapterError,
    ProviderFailureUsage,
    ProviderResult,
)
from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import (
    MAX_TOTAL_PROVIDER_INVOCATIONS,
    FallbackAuthorizationDecision,
    ProviderExecutionMetadata,
    ProviderFailureCoordinator,
)
from app.application.provider_pricing import ProviderPriceVersion
from app.application.usage_ledger import UsageRecord


class SequenceAdapter:
    def __init__(self, outcomes: Iterable[ProviderResult | ProviderAdapterError]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    async def execute(self, request: object) -> ProviderResult:
        del request
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, ProviderAdapterError):
            raise outcome
        return outcome


class FixedCatalog:
    async def resolve(
        self, *, provider: str, model: str, provider_execution_at: datetime
    ) -> ProviderPriceVersion:
        del provider_execution_at
        return ProviderPriceVersion(
            provider=provider,
            model=model,
            pricing_version=f"{provider}-price-v1",
            currency="USD",
            input_rate_per_1m=Decimal("1"),
            cached_input_rate_per_1m=Decimal("0.5"),
            output_rate_per_1m=Decimal("2"),
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        )


class RecordingLedger:
    def __init__(self) -> None:
        self.records: dict[UUID, UsageRecord] = {}

    async def append(self, record: UsageRecord) -> None:
        self.records.setdefault(record.provider_attempt_id, record)


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, delay_seconds: float) -> None:
        self.delays.append(delay_seconds)


class FixedRandom:
    def __init__(self, value: float = 0.5) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


class Authorization:
    def __init__(
        self, *, quality_allowed: bool, budget_allowed: bool, fails: bool = False
    ) -> None:
        self.decision = FallbackAuthorizationDecision(
            quality_allowed=quality_allowed,
            budget_allowed=budget_allowed,
        )
        self.fails = fails
        self.calls = 0

    async def authorize(self, request: object) -> FallbackAuthorizationDecision:
        del request
        self.calls += 1
        if self.fails:
            raise RuntimeError("sensitive-policy-detail")
        return self.decision


def _result(provider: str, model: str) -> ProviderResult:
    return ProviderResult(
        data={"items": []},
        provider=provider,
        model=model,
        provider_request_id=f"{provider}-request",
        input_tokens=100,
        cached_input_tokens=10,
        output_tokens=20,
        latency_ms=25.0,
        status="success",
    )


def _error(error_class: str, *, retryable: bool) -> ProviderAdapterError:
    return ProviderAdapterError(error_class, retryable=retryable)  # type: ignore[arg-type]


def _metadata() -> ProviderExecutionMetadata:
    return ProviderExecutionMetadata(
        account_id=uuid4(),
        project_id=uuid4(),
        job_id=uuid4(),
        task_type="synthetic-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        repair_no=0,
        correlation_id=uuid4(),
    )


def _coordinator(
    *,
    ledger: RecordingLedger,
    sleeper: RecordingSleeper | None = None,
    stream: StringIO | None = None,
) -> ProviderFailureCoordinator:
    return ProviderFailureCoordinator(
        catalog=FixedCatalog(),
        usage_ledger=ledger,
        sleeper=sleeper or RecordingSleeper(),
        random_source=FixedRandom(),
        utc_clock=lambda: datetime(2026, 9, 20, tzinfo=UTC),
        monotonic_clock=_monotonic_clock(),
        event_logger=(
            create_event_logger(
                service="worker",
                environment="test",
                app_version="test",
                release_commit_sha=None,
                level="INFO",
                stream=stream,
            )
            if stream is not None
            else None
        ),
    )


def _monotonic_clock():
    values = iter(range(100))
    return lambda: float(next(values))


def test_primary_success_stops_after_one_invocation() -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter([_result("primary", "primary-model")])

    execution = asyncio.run(
        _coordinator(ledger=ledger).execute(
            primary=ProviderCandidate("primary", "primary-model", primary_adapter),
            request={"sensitive": "fixture-content-must-not-log"},
            metadata=_metadata(),
        )
    )

    assert primary_adapter.calls == 1
    assert execution.used_fallback is False
    assert execution.retry_no == 0
    assert len(ledger.records) == 1


def test_timeout_retries_once_with_injected_full_jitter_then_succeeds() -> None:
    ledger = RecordingLedger()
    sleeper = RecordingSleeper()
    primary_adapter = SequenceAdapter(
        [_error("timeout", retryable=True), _result("primary", "primary-model")]
    )

    execution = asyncio.run(
        _coordinator(ledger=ledger, sleeper=sleeper).execute(
            primary=ProviderCandidate("primary", "primary-model", primary_adapter),
            request={},
            metadata=_metadata(),
        )
    )

    assert primary_adapter.calls == 2
    assert sleeper.delays == [1.0]
    assert execution.retry_no == 1
    records = list(ledger.records.values())
    assert len(records) == 2
    assert records[0].accounting_status == "unavailable"
    assert records[0].input_tokens is None
    assert records[0].estimated_cost is None
    assert records[1].accounting_status == "complete"


@pytest.mark.parametrize(
    "error_class",
    ["auth_error", "invalid_response", "safety_block", "quota_error", "unknown_provider_error"],
)
def test_permanent_failure_never_retries_or_falls_back(error_class: str) -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter([_error(error_class, retryable=False)])
    fallback_adapter = SequenceAdapter([_result("fallback", "fallback-model")])
    authorization = Authorization(quality_allowed=True, budget_allowed=True)

    with pytest.raises(ProviderAdapterError, match=error_class):
        asyncio.run(
            _coordinator(ledger=ledger).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                fallback=ProviderCandidate("fallback", "fallback-model", fallback_adapter),
                fallback_authorization=authorization,
                request={},
                metadata=_metadata(),
            )
        )

    assert primary_adapter.calls == 1
    assert fallback_adapter.calls == 0
    assert authorization.calls == 0
    assert len(ledger.records) == 1


def test_rate_limit_retries_once_but_never_triggers_fallback() -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter(
        [_error("rate_limited", retryable=True), _error("rate_limited", retryable=True)]
    )
    fallback_adapter = SequenceAdapter([_result("fallback", "fallback-model")])
    authorization = Authorization(quality_allowed=True, budget_allowed=True)

    with pytest.raises(ProviderAdapterError, match="rate_limited"):
        asyncio.run(
            _coordinator(ledger=ledger).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                fallback=ProviderCandidate("fallback", "fallback-model", fallback_adapter),
                fallback_authorization=authorization,
                request={},
                metadata=_metadata(),
            )
        )

    assert primary_adapter.calls == 2
    assert fallback_adapter.calls == 0
    assert authorization.calls == 0
    assert len(ledger.records) == 2


def test_invalid_json_with_valid_provider_usage_is_metered_completely_once() -> None:
    ledger = RecordingLedger()
    invalid = ProviderAdapterError(
        "invalid_response",
        retryable=False,
        usage=ProviderFailureUsage(
            provider_request_id="safe-request-id",
            input_tokens=10,
            cached_input_tokens=2,
            output_tokens=4,
            latency_ms=15.0,
        ),
    )
    primary_adapter = SequenceAdapter([invalid])

    with pytest.raises(ProviderAdapterError, match="invalid_response"):
        asyncio.run(
            _coordinator(ledger=ledger).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                request={},
                metadata=_metadata(),
            )
        )

    assert primary_adapter.calls == 1
    record = next(iter(ledger.records.values()))
    assert record.accounting_status == "complete"
    assert record.status == "failed"
    assert record.input_tokens == 10
    assert record.estimated_cost is not None


@pytest.mark.parametrize(
    ("authorization", "expected_authorization_calls"),
    [
        (None, 0),
        (Authorization(quality_allowed=False, budget_allowed=True), 1),
        (Authorization(quality_allowed=True, budget_allowed=False), 1),
        (Authorization(quality_allowed=True, budget_allowed=True, fails=True), 1),
    ],
)
def test_fallback_is_fail_closed_without_both_authorizations(
    authorization: Authorization | None, expected_authorization_calls: int
) -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter(
        [
            _error("provider_unavailable", retryable=True),
            _error("provider_unavailable", retryable=True),
        ]
    )
    fallback_adapter = SequenceAdapter([_result("fallback", "fallback-model")])

    with pytest.raises(ProviderAdapterError, match="provider_unavailable"):
        asyncio.run(
            _coordinator(ledger=ledger).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                fallback=ProviderCandidate("fallback", "fallback-model", fallback_adapter),
                fallback_authorization=authorization,
                request={},
                metadata=_metadata(),
            )
        )

    assert primary_adapter.calls == 2
    assert fallback_adapter.calls == 0
    assert expected_authorization_calls == (authorization.calls if authorization else 0)
    assert len(ledger.records) == 2


def test_maximum_total_provider_invocations_never_exceeds_3() -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter(
        [_error("timeout", retryable=True), _error("timeout", retryable=True)]
    )
    fallback_adapter = SequenceAdapter([_error("timeout", retryable=True)])

    with pytest.raises(ProviderAdapterError, match="timeout"):
        asyncio.run(
            _coordinator(ledger=ledger).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                fallback=ProviderCandidate("fallback", "fallback-model", fallback_adapter),
                fallback_authorization=Authorization(
                    quality_allowed=True, budget_allowed=True
                ),
                request={},
                metadata=_metadata(),
            )
        )

    assert primary_adapter.calls + fallback_adapter.calls == MAX_TOTAL_PROVIDER_INVOCATIONS
    assert primary_adapter.calls == 2
    assert fallback_adapter.calls == 1
    assert len(ledger.records) == 3
    assert len(set(ledger.records)) == 3


def test_allowed_fallback_succeeds_once_after_primary_exhaustion() -> None:
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter(
        [
            _error("provider_unavailable", retryable=True),
            _error("provider_unavailable", retryable=True),
        ]
    )
    fallback_adapter = SequenceAdapter([_result("fallback", "fallback-model")])

    execution = asyncio.run(
        _coordinator(ledger=ledger).execute(
            primary=ProviderCandidate("primary", "primary-model", primary_adapter),
            fallback=ProviderCandidate("fallback", "fallback-model", fallback_adapter),
            fallback_authorization=Authorization(
                quality_allowed=True, budget_allowed=True
            ),
            request={},
            metadata=_metadata(),
        )
    )

    assert execution.used_fallback is True
    assert execution.retry_no == 0
    assert len(ledger.records) == 3


def test_logs_never_include_request_or_policy_exception_content() -> None:
    stream = StringIO()
    sensitive_value = "customer-fixture-secret-text"
    ledger = RecordingLedger()
    primary_adapter = SequenceAdapter(
        [
            _error("provider_unavailable", retryable=True),
            _error("provider_unavailable", retryable=True),
        ]
    )

    with pytest.raises(ProviderAdapterError):
        asyncio.run(
            _coordinator(ledger=ledger, stream=stream).execute(
                primary=ProviderCandidate("primary", "primary-model", primary_adapter),
                fallback=ProviderCandidate(
                    "fallback", "fallback-model", SequenceAdapter([])
                ),
                fallback_authorization=Authorization(
                    quality_allowed=True, budget_allowed=True, fails=True
                ),
                request={"input": sensitive_value, "prompt": sensitive_value},
                metadata=_metadata(),
            )
        )

    output = stream.getvalue()
    assert sensitive_value not in output
    assert "sensitive-policy-detail" not in output
    assert "provider_unavailable" in output
