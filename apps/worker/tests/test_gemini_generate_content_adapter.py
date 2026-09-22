from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.application.provider_adapter import ProviderAdapterError
from app.infrastructure.ai.gemini_generate_content import GeminiGenerateContentAdapter


class FakeGeminiModels:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] | None = None

    async def generate_content(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            response_id="gemini-safe",
            text='{"items": []}',
            usage_metadata=SimpleNamespace(
                prompt_token_count=13,
                cached_content_token_count=2,
                candidates_token_count=5,
                thoughts_token_count=7,
            ),
        )


class FakeGeminiAsyncClient:
    def __init__(self) -> None:
        self.models = FakeGeminiModels()


def test_gemini_adapter_maps_billable_thinking_tokens_and_disables_tools() -> None:
    client = FakeGeminiAsyncClient()
    adapter = GeminiGenerateContentAdapter(client=client, model="gemini-3.8-flash")

    result = asyncio.run(
        adapter.execute(
            {
                "instructions": "Return approved structured output.",
                "input": {"brief": "synthetic"},
                "output_schema": {
                    "type": "object",
                    "properties": {"items": {"type": "array", "items": {}}},
                    "required": ["items"],
                },
            }
        )
    )

    assert result.provider == "google"
    assert result.input_tokens == 13
    assert result.cached_input_tokens == 2
    assert result.output_tokens == 12
    assert result.data == {"items": []}
    assert client.models.kwargs is not None
    assert "cached_content" not in client.models.kwargs
    config = client.models.kwargs["config"]
    assert getattr(config, "tools", None) is None


def test_gemini_adapter_rejects_unapproved_model_before_any_call() -> None:
    with pytest.raises(ValueError, match="approved Gemini evaluation candidate"):
        GeminiGenerateContentAdapter(client=FakeGeminiAsyncClient(), model="unapproved-model")


def test_gemini_invalid_json_preserves_only_safe_numeric_usage() -> None:
    client = FakeGeminiAsyncClient()

    async def invalid_response(**kwargs: object) -> object:
        client.models.kwargs = kwargs
        return SimpleNamespace(
            response_id="gemini-safe",
            text="not-json",
            usage_metadata=SimpleNamespace(
                prompt_token_count=13,
                cached_content_token_count=2,
                candidates_token_count=5,
                thoughts_token_count=7,
            ),
        )

    client.models.generate_content = invalid_response  # type: ignore[method-assign]
    adapter = GeminiGenerateContentAdapter(client=client, model="gemini-3.8-flash")

    with pytest.raises(ProviderAdapterError) as captured:
        asyncio.run(
            adapter.execute(
                {"instructions": "safe", "input": {}, "output_schema": {"type": "object"}}
            )
        )

    assert captured.value.error_class == "invalid_response"
    assert captured.value.retryable is False
    assert captured.value.usage is not None
    assert captured.value.usage.input_tokens == 13
    assert captured.value.usage.output_tokens == 12


def test_gemini_adapter_maps_safety_finish_reason_without_exposing_content() -> None:
    client = FakeGeminiAsyncClient()

    async def safety_response(**kwargs: object) -> object:
        client.models.kwargs = kwargs
        return SimpleNamespace(
            response_id="gemini-safe",
            text=None,
            candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value="SAFETY"))],
            usage_metadata=None,
        )

    client.models.generate_content = safety_response  # type: ignore[method-assign]
    adapter = GeminiGenerateContentAdapter(client=client, model="gemini-3.8-flash")

    with pytest.raises(ProviderAdapterError) as captured:
        asyncio.run(
            adapter.execute(
                {"instructions": "safe", "input": {}, "output_schema": {"type": "object"}}
            )
        )

    assert captured.value.error_class == "safety_block"
    assert captured.value.retryable is False
