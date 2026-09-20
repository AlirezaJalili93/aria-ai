from __future__ import annotations

from time import monotonic
from typing import Protocol, cast

import httpx
from google import genai
from google.genai import errors, types

from app.application.provider_adapter import (
    ProviderAdapterError,
    ProviderRequest,
    ProviderResult,
)
from app.infrastructure.ai.common import (
    decode_structured_output,
    encode_structured_input,
    non_negative_count,
    require_cached_subset,
    require_provider_request,
    required_non_negative_count,
)

GEMINI_PROVIDER = "google"
GEMINI_EVALUATION_MODEL = "gemini-3.8-flash"


class _GeminiModels(Protocol):
    async def generate_content(self, **kwargs: object) -> object: ...


class _GeminiAsyncClient(Protocol):
    models: _GeminiModels


def create_gemini_client(api_key: str) -> genai.Client:
    if not api_key.strip():
        raise ValueError("gemini_api_key_required")
    timeout = httpx.Timeout(60.0, connect=5.0, read=60.0, write=60.0, pool=60.0)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=60_000,
            async_client_args={"timeout": timeout},
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def create_gemini_adapter(api_key: str) -> GeminiGenerateContentAdapter:
    client = create_gemini_client(api_key)
    return GeminiGenerateContentAdapter(
        client=cast(_GeminiAsyncClient, client.aio), model=GEMINI_EVALUATION_MODEL
    )


class GeminiGenerateContentAdapter:
    """GenerateContent adapter for the approved synthetic-evaluation candidate only."""

    def __init__(self, *, client: _GeminiAsyncClient, model: str) -> None:
        if model != GEMINI_EVALUATION_MODEL:
            raise ValueError("model is not the approved Gemini evaluation candidate")
        self._client = client
        self._model = model

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        instructions, input_value, output_schema = require_provider_request(request)
        started_at = monotonic()
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            response_mime_type="application/json",
            response_json_schema=dict(output_schema),
            tools=None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = await self._client.models.generate_content(
                model=self._model,
                contents=encode_structured_input(input_value),
                config=config,
            )
        except Exception as error:
            raise _map_gemini_error(error) from error

        if _is_safety_block(response):
            raise ProviderAdapterError("safety_block", retryable=False)
        usage = getattr(response, "usage_metadata", None)
        input_tokens = required_non_negative_count(
            getattr(usage, "prompt_token_count", None)
        )
        cached_input_tokens = non_negative_count(
            getattr(usage, "cached_content_token_count", None)
        )
        require_cached_subset(
            input_tokens=input_tokens, cached_input_tokens=cached_input_tokens
        )
        candidates = required_non_negative_count(
            getattr(usage, "candidates_token_count", None)
        )
        thoughts = non_negative_count(getattr(usage, "thoughts_token_count", None))
        return ProviderResult(
            data=decode_structured_output(getattr(response, "text", None)),
            provider=GEMINI_PROVIDER,
            model=self._model,
            provider_request_id=_optional_string(getattr(response, "response_id", None)),
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=candidates + thoughts,
            latency_ms=(monotonic() - started_at) * 1000,
            status="success",
        )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _is_safety_block(response: object) -> bool:
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, list):
        return False
    blocked_reasons = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
    for candidate in candidates:
        finish_reason = getattr(candidate, "finish_reason", None)
        value = getattr(finish_reason, "value", finish_reason)
        if isinstance(value, str) and value.upper() in blocked_reasons:
            return True
    return False


def _map_gemini_error(error: Exception) -> ProviderAdapterError:
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return ProviderAdapterError("timeout", retryable=True)
    if isinstance(error, errors.APIError):
        code = getattr(error, "code", None)
        if code == 429:
            return ProviderAdapterError("rate_limited", retryable=True)
        if code in {401, 403}:
            return ProviderAdapterError("auth_error", retryable=False)
        if isinstance(code, int) and code >= 500:
            return ProviderAdapterError("provider_unavailable", retryable=True)
        if code in {400, 404, 409, 422}:
            return ProviderAdapterError("invalid_response", retryable=False)
    return ProviderAdapterError("unknown_provider_error", retryable=False)
