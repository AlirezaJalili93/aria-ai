from __future__ import annotations

from collections.abc import Callable, Mapping
from uuid import UUID, uuid4

from aria_backend_application.ai_execution import AIExecutionError, StructuredAIResponse
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_V1,
    COMPLETION_CHECKLIST_VERSION,
    CandidateGapBatch,
    ChecklistItemRuleSignal,
)


class SyntheticGapDetectionAI:
    """Deterministic AI-03 fake; never composed into the hosted Worker."""

    provider = "synthetic"
    model = "gap-detection-fake-v1"

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
        if task_type != "gap_detection" or cost_budget.get("paid_calls_allowed") is not False:
            raise AIExecutionError("invalid_response", retryable=False)
        context_items = input_context.get("context_items")
        requirements = input_context.get("requirements")
        project_type = input_context.get("project_type")
        checklist_version = input_context.get("completion_checklist_version")
        if (
            not isinstance(context_items, tuple)
            or not context_items
            or not isinstance(requirements, tuple)
            or not isinstance(project_type, str)
            or checklist_version != COMPLETION_CHECKLIST_VERSION
        ):
            raise AIExecutionError("invalid_response", retryable=False)
        checklist = COMPLETION_CHECKLIST_V1.items_for(project_type)
        if checklist is None:
            raise AIExecutionError("invalid_response", retryable=False)

        batch = CandidateGapBatch(
            items=(),
            rule_signals=tuple(
                ChecklistItemRuleSignal(
                    signal_type="checklist_item",
                    signal_origin="ai_candidate",
                    checklist_item_id=item.item_id,
                    state="missing",
                    supporting_context_item_ids=(),
                )
                for item in checklist
            ),
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
