from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.application.provider_adapter import ProviderAdapterError
from app.infrastructure.ai.openai_responses import OpenAIResponsesAdapter


class FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict[str, object] | None = None

    async def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: object) -> None:
        self.responses = FakeResponses(response)


def openai_response(*, cache_write_tokens: int = 0) -> object:
    return SimpleNamespace(
        id="resp-safe",
        status="completed",
        output_text='{"items": []}',
        usage=SimpleNamespace(
            input_tokens=11,
            input_tokens_details=SimpleNamespace(
                cached_tokens=3,
                cache_write_tokens=cache_write_tokens,
            ),
            output_tokens=7,
        ),
    )


def test_openai_adapter_enforces_structured_output_and_no_tools_or_implicit_cache() -> None:
    client = FakeOpenAIClient(openai_response())
    adapter = OpenAIResponsesAdapter(client=client, model="gpt-5.6-terra")

    result = asyncio.run(
        adapter.execute(
            {
                "instructions": "Return approved structured output.",
                "input": {"brief": "synthetic"},
                "output_schema": {
                    "type": "object",
                    "properties": {"items": {"type": "array", "items": {}}},
                    "required": ["items"],
                    "additionalProperties": False,
                },
            }
        )
    )

    assert result.data == {"items": []}
    assert result.provider == "openai"
    assert result.input_tokens == 11
    assert result.cached_input_tokens == 3
    assert result.output_tokens == 7
    assert client.responses.kwargs is not None
    assert client.responses.kwargs["tools"] == []
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["prompt_cache_options"] == {"mode": "explicit"}


def test_openai_adapter_fails_closed_on_nonzero_cache_write_tokens() -> None:
    adapter = OpenAIResponsesAdapter(
        client=FakeOpenAIClient(openai_response(cache_write_tokens=1)),
        model="gpt-5.6-terra",
    )

    with pytest.raises(ProviderAdapterError) as captured:
        asyncio.run(
            adapter.execute(
                {"instructions": "safe", "input": {}, "output_schema": {"type": "object"}}
            )
        )

    assert captured.value.error_class == "invalid_response"
    assert captured.value.retryable is False
    assert captured.value.code == "provider_accounting_unsupported"  # type: ignore[attr-defined]


def test_openai_adapter_fails_closed_when_cache_write_accounting_is_missing() -> None:
    response = openai_response()
    del response.usage.input_tokens_details.cache_write_tokens  # type: ignore[attr-defined]
    adapter = OpenAIResponsesAdapter(
        client=FakeOpenAIClient(response), model="gpt-5.6-terra"
    )

    with pytest.raises(ProviderAdapterError) as captured:
        asyncio.run(
            adapter.execute(
                {"instructions": "safe", "input": {}, "output_schema": {"type": "object"}}
            )
        )

    assert captured.value.error_class == "invalid_response"
    assert captured.value.retryable is False


def test_openai_adapter_rejects_unapproved_model_before_any_call() -> None:
    with pytest.raises(ValueError, match="approved OpenAI evaluation candidate"):
        OpenAIResponsesAdapter(
            client=FakeOpenAIClient(openai_response()), model="unapproved-model"
        )


def test_openai_adapter_maps_content_filter_to_non_retryable_safety_block() -> None:
    response = SimpleNamespace(
        id="resp-safe",
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="content_filter"),
    )
    adapter = OpenAIResponsesAdapter(
        client=FakeOpenAIClient(response), model="gpt-5.6-terra"
    )

    with pytest.raises(ProviderAdapterError) as captured:
        asyncio.run(
            adapter.execute(
                {"instructions": "safe", "input": {}, "output_schema": {"type": "object"}}
            )
        )

    assert captured.value.error_class == "safety_block"
    assert captured.value.retryable is False
