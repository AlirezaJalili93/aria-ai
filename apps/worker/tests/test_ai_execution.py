from __future__ import annotations

import inspect

import pytest

from app.application.ai_execution import (
    AIExecutionError,
    AIExecutionPort,
    StructuredAIResponse,
)


def test_structured_response_contains_only_the_approved_gateway_fields() -> None:
    response = StructuredAIResponse(
        data={"items": []},
        provider="provider-a",
        model="model-a",
        provider_request_id=None,
        input_tokens=10,
        cached_input_tokens=0,
        output_tokens=20,
        latency_ms=125.5,
        retry_no=0,
        workflow_version="wf-1",
        prompt_version="prompt-1",
        estimated_cost=0.01,
        status="success",
    )

    assert response.status == "success"
    assert response.workflow_version == "wf-1"
    assert response.prompt_version == "prompt-1"
    assert response.provider_request_id is None
    assert response.data == {"items": []}


def test_ai_execution_error_keeps_retryability_explicit() -> None:
    retryable = AIExecutionError("timeout", retryable=True)
    non_retryable = AIExecutionError("auth_error", retryable=False)

    assert retryable.error_class == "timeout"
    assert retryable.retryable is True
    assert non_retryable.error_class == "auth_error"
    assert non_retryable.retryable is False
    assert str(retryable) == "timeout"


def test_port_signature_is_provider_neutral_and_async() -> None:
    method = AIExecutionPort.execute_structured
    parameters = list(inspect.signature(method).parameters)

    assert parameters == [
        "self",
        "task_type",
        "workflow_version",
        "prompt_version",
        "output_schema",
        "input_context",
        "routing_policy",
        "cost_budget",
        "timeout_policy",
        "metadata",
    ]
    assert inspect.iscoroutinefunction(method)


@pytest.mark.parametrize(
    "error_class",
    [
        "timeout",
        "rate_limited",
        "auth_error",
        "invalid_response",
        "safety_block",
        "provider_unavailable",
        "quota_error",
        "unknown_provider_error",
    ],
)
def test_error_taxonomy_is_representable(error_class: str) -> None:
    error = AIExecutionError(error_class, retryable=False)  # type: ignore[arg-type]

    assert error.error_class == error_class
