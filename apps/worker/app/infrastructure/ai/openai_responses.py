from __future__ import annotations

from time import monotonic
from typing import Protocol, cast

import httpx2
import openai
from openai import AsyncOpenAI

from app.application.provider_adapter import (
    ProviderAdapterError,
    ProviderFailureUsage,
    ProviderRequest,
    ProviderResult,
)
from app.infrastructure.ai.common import (
    UnsupportedProviderAccountingError,
    decode_structured_output,
    encode_structured_input,
    non_negative_count,
    require_cached_subset,
    require_provider_request,
    required_non_negative_count,
)

OPENAI_PROVIDER = "openai"
OPENAI_EVALUATION_MODEL = "gpt-5.6-terra"


class _ResponsesResource(Protocol):
    async def create(self, **kwargs: object) -> object: ...


class _OpenAIClient(Protocol):
    responses: _ResponsesResource


def create_openai_client(api_key: str) -> AsyncOpenAI:
    if not api_key.strip():
        raise ValueError("openai_api_key_required")
    return AsyncOpenAI(
        api_key=api_key,
        timeout=httpx2.Timeout(60.0, connect=5.0, read=60.0, write=60.0, pool=60.0),
        max_retries=0,
    )


def create_openai_adapter(api_key: str) -> OpenAIResponsesAdapter:
    client = create_openai_client(api_key)
    return OpenAIResponsesAdapter(
        client=cast(_OpenAIClient, client), model=OPENAI_EVALUATION_MODEL
    )


class OpenAIResponsesAdapter:
    """Responses adapter for the approved synthetic-evaluation candidate only."""

    def __init__(self, *, client: _OpenAIClient, model: str) -> None:
        if model != OPENAI_EVALUATION_MODEL:
            raise ValueError("model is not the approved OpenAI evaluation candidate")
        self._client = client
        self._model = model

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        instructions, input_value, output_schema = require_provider_request(request)
        started_at = monotonic()
        try:
            response = await self._client.responses.create(
                model=self._model,
                instructions=instructions,
                input=encode_structured_input(input_value),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "aria_structured_output",
                        "schema": dict(output_schema),
                        "strict": True,
                    }
                },
                tools=[],
                parallel_tool_calls=False,
                store=False,
                prompt_cache_options={"mode": "explicit"},
            )
        except Exception as error:
            raise _map_openai_error(error) from error

        status = getattr(response, "status", None)
        if status != "completed":
            incomplete_details = getattr(response, "incomplete_details", None)
            if getattr(incomplete_details, "reason", None) == "content_filter":
                raise ProviderAdapterError("safety_block", retryable=False)
            raise ProviderAdapterError("invalid_response", retryable=False)
        usage = getattr(response, "usage", None)
        details = getattr(usage, "input_tokens_details", None)
        cache_write_tokens = required_non_negative_count(
            getattr(details, "cache_write_tokens", None)
        )
        if cache_write_tokens != 0:
            raise UnsupportedProviderAccountingError()

        input_tokens = required_non_negative_count(getattr(usage, "input_tokens", None))
        cached_input_tokens = non_negative_count(getattr(details, "cached_tokens", None))
        require_cached_subset(
            input_tokens=input_tokens, cached_input_tokens=cached_input_tokens
        )
        output_tokens = required_non_negative_count(
            getattr(usage, "output_tokens", None)
        )
        try:
            data = decode_structured_output(getattr(response, "output_text", None))
        except ProviderAdapterError as error:
            raise ProviderAdapterError(
                error.error_class,
                retryable=error.retryable,
                usage=ProviderFailureUsage(
                    provider_request_id=_optional_string(getattr(response, "id", None)),
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=(monotonic() - started_at) * 1000,
                ),
            ) from None
        return ProviderResult(
            data=data,
            provider=OPENAI_PROVIDER,
            model=self._model,
            provider_request_id=_optional_string(getattr(response, "id", None)),
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            latency_ms=(monotonic() - started_at) * 1000,
            status="success",
        )


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _map_openai_error(error: Exception) -> ProviderAdapterError:
    if isinstance(error, (openai.APITimeoutError, TimeoutError)):
        return ProviderAdapterError("timeout", retryable=True)
    if isinstance(error, openai.RateLimitError):
        return ProviderAdapterError("rate_limited", retryable=True)
    if isinstance(error, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ProviderAdapterError("auth_error", retryable=False)
    if isinstance(error, (openai.APIConnectionError, openai.InternalServerError)):
        return ProviderAdapterError("provider_unavailable", retryable=True)
    if isinstance(error, (openai.BadRequestError, openai.UnprocessableEntityError)):
        return ProviderAdapterError("invalid_response", retryable=False)
    return ProviderAdapterError("unknown_provider_error", retryable=False)
