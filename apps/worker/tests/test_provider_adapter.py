from __future__ import annotations

import inspect

from app.application.provider_adapter import (
    ProviderAdapter,
    ProviderAdapterError,
    ProviderResult,
)


def test_provider_result_contains_only_the_normalized_adapter_fields() -> None:
    result = ProviderResult(
        data={"items": []},
        provider="provider-neutral",
        model="model-neutral",
        provider_request_id=None,
        input_tokens=1,
        cached_input_tokens=0,
        output_tokens=2,
        latency_ms=3.5,
        status="success",
    )

    assert result.data == {"items": []}
    assert result.provider_request_id is None
    assert result.status == "success"


def test_provider_adapter_port_is_async_and_has_one_opaque_request() -> None:
    method = ProviderAdapter.execute

    assert list(inspect.signature(method).parameters) == ["self", "request"]
    assert inspect.iscoroutinefunction(method)


def test_provider_adapter_error_preserves_standardized_mapping() -> None:
    error = ProviderAdapterError("provider_unavailable", retryable=True)

    assert error.error_class == "provider_unavailable"
    assert error.retryable is True
    assert str(error) == "provider_unavailable"
