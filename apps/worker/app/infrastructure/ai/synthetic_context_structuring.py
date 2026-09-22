from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import AIExecutionError, StructuredAIResponse
from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    CandidateContextItem,
    CandidateSourceReference,
)


class SyntheticContextStructuringAI:
    """Deterministic AI-01 fake; it is never composed into a hosted runtime."""

    provider = "synthetic"
    model = "context-structuring-fake-v1"

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    async def execute_structured(
        self,
        task_type: str,
        workflow_version: str,
        prompt_version: str,
        output_schema: Mapping[str, object],
        input_context: Mapping[str, object],
        routing_policy: Mapping[str, object],
        cost_budget: Mapping[str, object],
        timeout_policy: Mapping[str, object],
        metadata: Mapping[str, object],
    ) -> StructuredAIResponse:
        del output_schema, routing_policy, cost_budget, timeout_policy, metadata
        if task_type != "context_structuring":
            raise AIExecutionError("invalid_response", retryable=False)
        sources = input_context.get("sources")
        if not isinstance(sources, tuple) or not sources:
            raise AIExecutionError("invalid_response", retryable=False)

        items: list[CandidateContextItem] = []
        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                raise AIExecutionError("invalid_response", retryable=False)
            try:
                source_id = UUID(str(source["source_id"]))
                source_version_id = UUID(str(source["source_version_id"]))
            except (KeyError, TypeError, ValueError):
                raise AIExecutionError("invalid_response", retryable=False) from None
            items.append(
                CandidateContextItem(
                    item_type="reference",
                    content=f"مرجع ساختاریافتهٔ مصنوعی {index}",
                    source_refs=(
                        CandidateSourceReference(
                            source_id=source_id,
                            source_version_id=source_version_id,
                        ),
                    ),
                    confidence=Decimal("1.0000"),
                )
            )

        return StructuredAIResponse(
            data=CandidateContextBatch(items=tuple(items)),
            provider_attempt_id=self._id_factory(),
            provider=self.provider,
            model=self.model,
            provider_request_id=None,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            latency_ms=0,
            retry_no=0,
            workflow_version=workflow_version,
            prompt_version=prompt_version,
            estimated_cost=0,
            status="success",
        )
