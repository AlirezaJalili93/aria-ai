from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import AIExecutionError, StructuredAIResponse
from aria_backend_application.requirements_generation import (
    CandidateRequirement,
    CandidateRequirementBatch,
    RequirementSourceReference,
)


class SyntheticRequirementGenerationAI:
    """Deterministic AI-02 fake; never composed into the hosted Worker."""

    provider = "synthetic"
    model = "requirement-generation-fake-v1"

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
        del output_schema, routing_policy, timeout_policy, metadata
        if task_type != "requirement_generation" or cost_budget.get(
            "paid_calls_allowed"
        ) is not False:
            raise AIExecutionError("invalid_response", retryable=False)
        context_items = input_context.get("context_items")
        if not isinstance(context_items, tuple) or not context_items:
            raise AIExecutionError("invalid_response", retryable=False)
        first = context_items[0]
        if not isinstance(first, dict):
            raise AIExecutionError("invalid_response", retryable=False)
        references = first.get("source_refs")
        if not isinstance(references, tuple) or not references:
            raise AIExecutionError("invalid_response", retryable=False)
        reference = references[0]
        if not isinstance(reference, dict):
            raise AIExecutionError("invalid_response", retryable=False)
        try:
            source_ref = RequirementSourceReference(
                source_id=UUID(str(reference["source_id"])),
                source_version_id=UUID(str(reference["source_version_id"])),
                start_offset=reference.get("start_offset"),  # type: ignore[arg-type]
                end_offset=reference.get("end_offset"),  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError):
            raise AIExecutionError("invalid_response", retryable=False) from None
        batch = CandidateRequirementBatch(
            items=(
                CandidateRequirement(
                    title="نیازمندی مصنوعی کنترل‌شده",
                    description="این خروجی فقط برای آزمون مسیر داخلی AI-02 تولید شده است.",
                    category="functional",
                    priority="must",
                    source_refs=(source_ref,),
                    confidence=Decimal("1.0000"),
                    unsupported=False,
                ),
            )
        )
        return StructuredAIResponse(
            data=batch,
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
