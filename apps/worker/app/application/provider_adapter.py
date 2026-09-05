from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.application.ai_execution import (
    AIErrorClass,
    ExecutionStatus,
    StructuredMapping,
    StructuredValue,
)

ProviderRequest = StructuredMapping


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Normalized result returned by any future provider adapter."""

    data: StructuredValue
    provider: str
    model: str
    provider_request_id: str | None
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: float
    status: ExecutionStatus


class ProviderAdapterError(RuntimeError):
    """Provider-neutral mapped error; raw SDK exceptions stay inside an adapter."""

    def __init__(self, error_class: AIErrorClass, *, retryable: bool) -> None:
        super().__init__(error_class)
        self.error_class = error_class
        self.retryable = retryable


class ProviderAdapter(Protocol):
    """Generic adapter port with no provider, SDK or transport assumptions."""

    async def execute(self, request: ProviderRequest) -> ProviderResult: ...
