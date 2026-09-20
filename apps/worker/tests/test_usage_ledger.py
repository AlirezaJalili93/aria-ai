from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.usage_ledger import UsageRecord


def test_usage_record_keeps_provider_and_model_as_recorded_data() -> None:
    record = UsageRecord(
        account_id=uuid4(),
        provider_attempt_id=uuid4(),
        project_id=None,
        job_id=None,
        task_type="opaque-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        provider="provider-as-data",
        model="model-as-data",
        provider_request_id=None,
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        latency_ms=Decimal("0.000"),
        status="partial",
        error_code=None,
        retry_no=0,
        repair_no=0,
        estimated_cost=Decimal("0.00000000"),
        pricing_version="pricing-v1",
        correlation_id=uuid4(),
    )

    assert record.provider == "provider-as-data"
    assert record.model == "model-as-data"
    assert record.currency == "USD"
    assert record.repair_no == 0


def test_usage_record_rejects_cached_tokens_above_total_input() -> None:
    with pytest.raises(ValueError, match="invalid_token_accounting"):
        UsageRecord(
            account_id=uuid4(),
            provider_attempt_id=uuid4(),
            project_id=None,
            job_id=None,
            task_type="opaque-task",
            workflow_version="workflow-v1",
            prompt_version="prompt-v1",
            provider="provider-as-data",
            model="model-as-data",
            provider_request_id=None,
            input_tokens=1,
            cached_input_tokens=2,
            output_tokens=0,
            latency_ms=Decimal("0.000"),
            status="success",
            error_code=None,
            retry_no=0,
            repair_no=0,
            estimated_cost=Decimal("0.00000000"),
            pricing_version="pricing-v1",
            correlation_id=uuid4(),
        )


def test_unavailable_usage_requires_failed_status_and_null_accounting() -> None:
    record = UsageRecord(
        account_id=uuid4(),
        provider_attempt_id=uuid4(),
        project_id=None,
        job_id=None,
        task_type="opaque-task",
        workflow_version="workflow-v1",
        prompt_version="prompt-v1",
        provider="provider-as-data",
        model="model-as-data",
        provider_request_id=None,
        input_tokens=None,
        cached_input_tokens=None,
        output_tokens=None,
        latency_ms=Decimal("1.000"),
        status="failed",
        error_code="timeout",
        retry_no=0,
        repair_no=0,
        estimated_cost=None,
        pricing_version="pricing-v1",
        correlation_id=uuid4(),
        accounting_status="unavailable",
    )

    assert record.estimated_cost is None


def test_unavailable_usage_rejects_fabricated_zeroes() -> None:
    with pytest.raises(
        ValueError, match="unavailable_accounting_requires_failed_null_usage"
    ):
        UsageRecord(
            account_id=uuid4(),
            provider_attempt_id=uuid4(),
            project_id=None,
            job_id=None,
            task_type="opaque-task",
            workflow_version="workflow-v1",
            prompt_version="prompt-v1",
            provider="provider-as-data",
            model="model-as-data",
            provider_request_id=None,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            latency_ms=Decimal("1.000"),
            status="failed",
            error_code="timeout",
            retry_no=0,
            repair_no=0,
            estimated_cost=Decimal("0"),
            pricing_version="pricing-v1",
            correlation_id=uuid4(),
            accounting_status="unavailable",
        )
