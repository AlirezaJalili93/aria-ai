from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from app.application.ai_execution import StructuredMapping, StructuredValue
from app.application.provider_adapter import ProviderAdapterError, ProviderRequest


class UnsupportedProviderAccountingError(ProviderAdapterError):
    """The provider returned usage that the frozen ledger cannot price safely."""

    code = "provider_accounting_unsupported"

    def __init__(self) -> None:
        super().__init__("invalid_response", retryable=False)


def require_provider_request(
    request: ProviderRequest,
) -> tuple[str, StructuredValue, StructuredMapping]:
    if set(request) != {"instructions", "input", "output_schema"}:
        raise ValueError("provider_request_contract_invalid")
    instructions = request["instructions"]
    output_schema = request["output_schema"]
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("provider_instructions_required")
    if not isinstance(output_schema, Mapping):
        raise ValueError("provider_output_schema_required")
    return instructions, request["input"], cast(StructuredMapping, output_schema)


def encode_structured_input(value: StructuredValue) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError("provider_input_must_be_json_serializable") from error


def decode_structured_output(value: object) -> StructuredValue:
    if not isinstance(value, str) or not value.strip():
        raise ProviderAdapterError("invalid_response", retryable=False)
    try:
        return cast(StructuredValue, json.loads(value))
    except (TypeError, ValueError) as error:
        raise ProviderAdapterError("invalid_response", retryable=False) from error


def non_negative_count(value: object) -> int:
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProviderAdapterError("invalid_response", retryable=False)
    return value


def required_non_negative_count(value: object) -> int:
    if value is None:
        raise ProviderAdapterError("invalid_response", retryable=False)
    return non_negative_count(value)


def require_cached_subset(*, input_tokens: int, cached_input_tokens: int) -> None:
    if cached_input_tokens > input_tokens:
        raise ProviderAdapterError("invalid_response", retryable=False)
