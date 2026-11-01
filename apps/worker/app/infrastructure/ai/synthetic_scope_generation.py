from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import AIExecutionError, StructuredAIResponse
from aria_backend_application.scope_content import SCOPE_CONTENT_SCHEMA_VERSION, SECTION_IDS


class SyntheticScopeGenerationAI:
    """Deterministic AI-05 fake; not part of hosted Worker composition."""

    provider = "synthetic"
    model = "scope-generation-fake-v1"

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
        del routing_policy, timeout_policy, metadata
        if (
            task_type != "scope_generation"
            or cost_budget.get("paid_calls_allowed") is not False
            or output_schema.get("schema_version") != SCOPE_CONTENT_SCHEMA_VERSION
        ):
            raise AIExecutionError("invalid_response", retryable=False)
        context_items = input_context.get("context_items")
        requirements = input_context.get("requirements")
        if (
            not isinstance(context_items, list)
            or not context_items
            or not isinstance(requirements, list)
            or not requirements
        ):
            raise AIExecutionError("invalid_response", retryable=False)
        try:
            context_ids = sorted(str(UUID(str(item["id"]))) for item in context_items)
            requirement_ids = sorted(str(UUID(str(item["id"]))) for item in requirements)
            requirement_items = [
                {
                    "item_id": str(UUID(str(item["id"]))),
                    "text": str(item["title"]),
                    "priority": item["priority"],
                }
                for item in requirements
            ]
        except (KeyError, TypeError, ValueError):
            raise AIExecutionError("invalid_response", retryable=False) from None
        if any(
            not item["text"].strip() or item["priority"] not in {"must", "should", "could"}
            for item in requirement_items
        ):
            raise AIExecutionError("invalid_response", retryable=False)
        sections: list[dict[str, object]] = []
        for section_id in SECTION_IDS:
            trace: dict[str, list[str]] = {
                "context_item_ids": [], "requirement_ids": [], "gap_ids": []
            }
            if section_id == "summary":
                trace["context_item_ids"] = context_ids
                value: object = ""
            elif section_id == "requirements":
                trace["requirement_ids"] = requirement_ids
                value = requirement_items
            elif section_id == "visual_direction":
                value = ""
            else:
                value = []
            sections.append({"section_id": section_id, "value": value, "trace": trace})
        return StructuredAIResponse(
            data={"schema_version": SCOPE_CONTENT_SCHEMA_VERSION, "sections": sections},
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
