from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

ExecutionStatus = Literal["success", "failed", "partial"]
AIErrorClass = Literal[
    "timeout",
    "rate_limited",
    "auth_error",
    "invalid_response",
    "safety_block",
    "provider_unavailable",
    "quota_error",
    "unknown_provider_error",
]

StructuredValue = object
StructuredMapping = Mapping[str, StructuredValue]


@dataclass(frozen=True, slots=True)
class StructuredAIResponse:
    """Provider-neutral response fields defined by the AI execution contract."""

    data: StructuredValue
    provider: str
    model: str
    provider_request_id: str | None
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: float
    retry_no: int
    workflow_version: str
    prompt_version: str
    estimated_cost: float
    status: ExecutionStatus


class AIExecutionError(RuntimeError):
    """Safe standardized provider failure; raw provider errors stay in Infrastructure."""

    def __init__(self, error_class: AIErrorClass, *, retryable: bool) -> None:
        super().__init__(error_class)
        self.error_class = error_class
        self.retryable = retryable


class AIExecutionPort(Protocol):
    """Provider-neutral asynchronous boundary for structured AI execution."""

    async def execute_structured(
        self,
        task_type: str,
        workflow_version: str,
        prompt_version: str,
        output_schema: StructuredMapping,
        input_context: StructuredMapping,
        routing_policy: StructuredMapping,
        cost_budget: StructuredMapping,
        timeout_policy: StructuredMapping,
        metadata: StructuredMapping,
    ) -> StructuredAIResponse: ...
