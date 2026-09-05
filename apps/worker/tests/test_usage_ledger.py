from decimal import Decimal
from uuid import uuid4

from app.application.usage_ledger import UsageRecord


def test_usage_record_keeps_provider_and_model_as_recorded_data() -> None:
    record = UsageRecord(
        account_id=uuid4(),
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
        estimated_cost=Decimal("0.00000000"),
        pricing_version="pricing-v1",
        correlation_id=uuid4(),
    )

    assert record.provider == "provider-as-data"
    assert record.model == "model-as-data"
    assert record.currency == "USD"

