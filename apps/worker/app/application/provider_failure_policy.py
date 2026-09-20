from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from time import perf_counter
from typing import Protocol
from uuid import UUID, uuid4

from aria_observability import StructuredEventLogger

from app.application.ai_execution import AIErrorClass
from app.application.provider_adapter import (
    ProviderAdapterError,
    ProviderFailureUsage,
    ProviderRequest,
    ProviderResult,
)
from app.application.provider_execution import ProviderCandidate
from app.application.provider_pricing import (
    ProviderPriceCatalog,
    ProviderPriceVersion,
    UnpricedUsageRecord,
    price_usage_record,
)
from app.application.usage_ledger import UsageLedger, UsageRecord, UsageStatus

MAX_PRIMARY_ATTEMPTS = 2
MAX_FALLBACK_ATTEMPTS = 1
MAX_TOTAL_PROVIDER_INVOCATIONS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_CAP_DELAY_SECONDS = 4.0
RETRYABLE_ERROR_CLASSES: frozenset[AIErrorClass] = frozenset(
    {"timeout", "rate_limited", "provider_unavailable"}
)
FALLBACK_ELIGIBLE_ERROR_CLASSES: frozenset[AIErrorClass] = frozenset(
    {"timeout", "provider_unavailable"}
)


class RetrySleeper(Protocol):
    async def sleep(self, delay_seconds: float) -> None: ...


class RetryRandomSource(Protocol):
    def random(self) -> float: ...


@dataclass(frozen=True, slots=True)
class ProviderExecutionMetadata:
    account_id: UUID
    project_id: UUID | None
    job_id: UUID | None
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_no: int
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class FallbackAuthorizationRequest:
    account_id: UUID
    project_id: UUID | None
    job_id: UUID | None
    task_type: str
    failed_provider: str
    failed_model: str
    fallback_provider: str
    fallback_model: str
    error_class: AIErrorClass


@dataclass(frozen=True, slots=True)
class FallbackAuthorizationDecision:
    quality_allowed: bool
    budget_allowed: bool

    @property
    def allowed(self) -> bool:
        return self.quality_allowed and self.budget_allowed


class FallbackAuthorizationPort(Protocol):
    async def authorize(
        self, request: FallbackAuthorizationRequest
    ) -> FallbackAuthorizationDecision: ...


@dataclass(frozen=True, slots=True)
class FailureManagedProviderExecution:
    result: ProviderResult
    price: ProviderPriceVersion
    provider_attempt_id: UUID
    retry_no: int
    used_fallback: bool


@dataclass(frozen=True, slots=True)
class _FailedAttempt:
    error: ProviderAdapterError
    provider_attempt_id: UUID


class ProviderFailureCoordinator:
    """Run the frozen bounded retry/fallback policy and meter every real invocation."""

    def __init__(
        self,
        *,
        catalog: ProviderPriceCatalog,
        usage_ledger: UsageLedger,
        sleeper: RetrySleeper,
        random_source: RetryRandomSource,
        utc_clock: Callable[[], datetime],
        monotonic_clock: Callable[[], float] = perf_counter,
        attempt_id_factory: Callable[[], UUID] = uuid4,
        event_logger: StructuredEventLogger | None = None,
    ) -> None:
        self._catalog = catalog
        self._usage_ledger = usage_ledger
        self._sleeper = sleeper
        self._random_source = random_source
        self._utc_clock = utc_clock
        self._monotonic_clock = monotonic_clock
        self._attempt_id_factory = attempt_id_factory
        self._event_logger = event_logger

    async def execute(
        self,
        *,
        primary: ProviderCandidate,
        request: ProviderRequest,
        metadata: ProviderExecutionMetadata,
        fallback: ProviderCandidate | None = None,
        fallback_authorization: FallbackAuthorizationPort | None = None,
    ) -> FailureManagedProviderExecution:
        invocation_count = 0
        last_failure: _FailedAttempt | None = None

        for retry_no in range(MAX_PRIMARY_ATTEMPTS):
            invocation_count += 1
            outcome = await self._invoke(
                candidate=primary,
                request=request,
                metadata=metadata,
                retry_no=retry_no,
                global_attempt_no=invocation_count,
                used_fallback=False,
            )
            if isinstance(outcome, FailureManagedProviderExecution):
                return outcome
            last_failure = outcome
            if not self._is_retryable_failure(outcome.error):
                raise outcome.error
            if retry_no + 1 >= MAX_PRIMARY_ATTEMPTS:
                break
            delay_seconds = self._retry_delay_seconds(retry_no=retry_no + 1)
            self._emit(
                "ai.retry_scheduled",
                provider=primary.provider,
                model=primary.model,
                attempt=retry_no + 1,
                error_code=outcome.error.error_class,
                status="scheduled",
            )
            await self._sleeper.sleep(delay_seconds)

        assert last_failure is not None
        if not await self._fallback_allowed(
            failure=last_failure.error,
            primary=primary,
            fallback=fallback,
            authorization=fallback_authorization,
            metadata=metadata,
        ):
            raise last_failure.error
        assert fallback is not None

        invocation_count += 1
        if invocation_count > MAX_TOTAL_PROVIDER_INVOCATIONS:
            raise RuntimeError("provider_invocation_budget_exceeded")
        outcome = await self._invoke(
            candidate=fallback,
            request=request,
            metadata=metadata,
            retry_no=0,
            global_attempt_no=invocation_count,
            used_fallback=True,
        )
        if isinstance(outcome, _FailedAttempt):
            raise outcome.error
        return outcome

    async def _invoke(
        self,
        *,
        candidate: ProviderCandidate,
        request: ProviderRequest,
        metadata: ProviderExecutionMetadata,
        retry_no: int,
        global_attempt_no: int,
        used_fallback: bool,
    ) -> FailureManagedProviderExecution | _FailedAttempt:
        price = await self._catalog.resolve(
            provider=candidate.provider,
            model=candidate.model,
            provider_execution_at=self._utc_clock(),
        )
        provider_attempt_id = self._attempt_id_factory()
        started_at = self._monotonic_clock()
        self._emit(
            "ai.provider_attempt_started",
            provider=candidate.provider,
            model=candidate.model,
            attempt=global_attempt_no,
            status="started",
        )
        try:
            result = await candidate.adapter.execute(request)
        except ProviderAdapterError as error:
            latency_ms = Decimal(str((self._monotonic_clock() - started_at) * 1000))
            if error.usage is None:
                usage_record = _unavailable_usage_record(
                    metadata=metadata,
                    candidate=candidate,
                    price=price,
                    provider_attempt_id=provider_attempt_id,
                    retry_no=retry_no,
                    latency_ms=latency_ms,
                    error=error,
                )
            else:
                usage_record = _failed_complete_usage_record(
                    metadata=metadata,
                    candidate=candidate,
                    price=price,
                    provider_attempt_id=provider_attempt_id,
                    retry_no=retry_no,
                    usage=error.usage,
                    error=error,
                )
                latency_ms = usage_record.latency_ms
            await self._usage_ledger.append(usage_record)
            self._emit(
                "ai.provider_attempt_failed",
                level="ERROR",
                provider=candidate.provider,
                model=candidate.model,
                attempt=global_attempt_no,
                duration_ms=float(latency_ms),
                error_code=error.error_class,
                status="failed",
            )
            return _FailedAttempt(error=error, provider_attempt_id=provider_attempt_id)

        if (result.provider, result.model) != (candidate.provider, candidate.model):
            identity_error = ProviderAdapterError("invalid_response", retryable=False)
            latency_ms = Decimal(str(result.latency_ms))
            await self._usage_ledger.append(
                _complete_usage_record(
                    metadata=metadata,
                    result=result,
                    price=price,
                    provider_attempt_id=provider_attempt_id,
                    retry_no=retry_no,
                    status="failed",
                    error_code=identity_error.error_class,
                    provider=candidate.provider,
                    model=candidate.model,
                )
            )
            return _FailedAttempt(
                error=identity_error, provider_attempt_id=provider_attempt_id
            )

        await self._usage_ledger.append(
            _complete_usage_record(
                metadata=metadata,
                result=result,
                price=price,
                provider_attempt_id=provider_attempt_id,
                retry_no=retry_no,
                status=result.status,
                error_code=None if result.status == "success" else "provider_execution_failed",
            )
        )
        self._emit(
            "ai.provider_attempt_succeeded",
            provider=candidate.provider,
            model=candidate.model,
            attempt=global_attempt_no,
            duration_ms=result.latency_ms,
            status=result.status,
        )
        return FailureManagedProviderExecution(
            result=result,
            price=price,
            provider_attempt_id=provider_attempt_id,
            retry_no=retry_no,
            used_fallback=used_fallback,
        )

    def _is_retryable_failure(self, error: ProviderAdapterError) -> bool:
        return error.retryable and error.error_class in RETRYABLE_ERROR_CLASSES

    def _retry_delay_seconds(self, *, retry_no: int) -> float:
        fraction = self._random_source.random()
        if fraction < 0 or fraction > 1:
            raise ValueError("retry_random_fraction_out_of_range")
        ceiling = min(
            RETRY_CAP_DELAY_SECONDS,
            RETRY_BASE_DELAY_SECONDS * (2**retry_no),
        )
        return ceiling * fraction

    async def _fallback_allowed(
        self,
        *,
        failure: ProviderAdapterError,
        primary: ProviderCandidate,
        fallback: ProviderCandidate | None,
        authorization: FallbackAuthorizationPort | None,
        metadata: ProviderExecutionMetadata,
    ) -> bool:
        if (
            failure.error_class not in FALLBACK_ELIGIBLE_ERROR_CLASSES
            or fallback is None
            or authorization is None
        ):
            return False
        try:
            decision = await authorization.authorize(
                FallbackAuthorizationRequest(
                    account_id=metadata.account_id,
                    project_id=metadata.project_id,
                    job_id=metadata.job_id,
                    task_type=metadata.task_type,
                    failed_provider=primary.provider,
                    failed_model=primary.model,
                    fallback_provider=fallback.provider,
                    fallback_model=fallback.model,
                    error_class=failure.error_class,
                )
            )
        except Exception:
            self._emit(
                "ai.fallback_denied",
                level="ERROR",
                provider=primary.provider,
                model=primary.model,
                error_code="fallback_policy_unavailable",
                status="denied",
            )
            return False
        if not decision.allowed:
            self._emit(
                "ai.fallback_denied",
                provider=primary.provider,
                model=primary.model,
                error_code="fallback_not_authorized",
                status="denied",
            )
            return False
        self._emit(
            "ai.fallback_authorized",
            provider=fallback.provider,
            model=fallback.model,
            status="authorized",
        )
        return True

    def _emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        if self._event_logger is not None:
            self._event_logger.emit(event_name, level=level, **fields)


def _complete_usage_record(
    *,
    metadata: ProviderExecutionMetadata,
    result: ProviderResult,
    price: ProviderPriceVersion,
    provider_attempt_id: UUID,
    retry_no: int,
    status: UsageStatus,
    error_code: str | None,
    provider: str | None = None,
    model: str | None = None,
) -> UsageRecord:
    return price_usage_record(
        UnpricedUsageRecord(
            account_id=metadata.account_id,
            provider_attempt_id=provider_attempt_id,
            project_id=metadata.project_id,
            job_id=metadata.job_id,
            task_type=metadata.task_type,
            workflow_version=metadata.workflow_version,
            prompt_version=metadata.prompt_version,
            provider=provider or result.provider,
            model=model or result.model,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens,
            cached_input_tokens=result.cached_input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=Decimal(str(result.latency_ms)),
            status=status,
            error_code=error_code,
            retry_no=retry_no,
            repair_no=metadata.repair_no,
            correlation_id=metadata.correlation_id,
        ),
        price,
    )


def _failed_complete_usage_record(
    *,
    metadata: ProviderExecutionMetadata,
    candidate: ProviderCandidate,
    price: ProviderPriceVersion,
    provider_attempt_id: UUID,
    retry_no: int,
    usage: ProviderFailureUsage,
    error: ProviderAdapterError,
) -> UsageRecord:
    return price_usage_record(
        UnpricedUsageRecord(
            account_id=metadata.account_id,
            provider_attempt_id=provider_attempt_id,
            project_id=metadata.project_id,
            job_id=metadata.job_id,
            task_type=metadata.task_type,
            workflow_version=metadata.workflow_version,
            prompt_version=metadata.prompt_version,
            provider=candidate.provider,
            model=candidate.model,
            provider_request_id=usage.provider_request_id,
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=Decimal(str(usage.latency_ms)),
            status="failed",
            error_code=error.error_class,
            retry_no=retry_no,
            repair_no=metadata.repair_no,
            correlation_id=metadata.correlation_id,
        ),
        price,
    )


def _unavailable_usage_record(
    *,
    metadata: ProviderExecutionMetadata,
    candidate: ProviderCandidate,
    price: ProviderPriceVersion,
    provider_attempt_id: UUID,
    retry_no: int,
    latency_ms: Decimal,
    error: ProviderAdapterError,
) -> UsageRecord:
    return UsageRecord(
        account_id=metadata.account_id,
        provider_attempt_id=provider_attempt_id,
        project_id=metadata.project_id,
        job_id=metadata.job_id,
        task_type=metadata.task_type,
        workflow_version=metadata.workflow_version,
        prompt_version=metadata.prompt_version,
        provider=candidate.provider,
        model=candidate.model,
        provider_request_id=None,
        input_tokens=None,
        cached_input_tokens=None,
        output_tokens=None,
        latency_ms=latency_ms,
        status="failed",
        error_code=error.error_class,
        retry_no=retry_no,
        repair_no=metadata.repair_no,
        estimated_cost=None,
        pricing_version=price.pricing_version,
        correlation_id=metadata.correlation_id,
        accounting_status="unavailable",
        currency=price.currency,
    )
