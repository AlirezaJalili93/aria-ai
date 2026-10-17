from __future__ import annotations

import asyncio

from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_VERSION,
    CandidateGapBatch,
    ChecklistItemRuleSignal,
)

from app.infrastructure.ai.synthetic_gap_detection import SyntheticGapDetectionAI


def test_synthetic_ai03_accepts_empty_requirements_and_returns_checklist_signals() -> None:
    response = asyncio.run(
        SyntheticGapDetectionAI().execute_structured(
            task_type="gap_detection",
            workflow_version="synthetic-ai-03-v1",
            prompt_version="synthetic-gap-prompt-v1",
            output_schema={},
            input_context={
                "project_type": "landing",
                "context_version": 1,
                "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
                "context_items": ({"context_item_id": "synthetic"},),
                "requirements": (),
            },
            routing_policy={},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={},
            metadata={},
        )
    )
    assert isinstance(response.data, CandidateGapBatch)
    assert response.data.items == ()
    assert len(response.data.rule_signals) == 5
    assert all(
        isinstance(signal, ChecklistItemRuleSignal) and signal.state == "missing"
        for signal in response.data.rule_signals
    )
    assert response.provider == "synthetic"
    assert response.input_tokens == response.output_tokens == 0


def test_synthetic_ai03_does_not_invent_a_missing_requirement_gap() -> None:
    response = asyncio.run(
        SyntheticGapDetectionAI().execute_structured(
            task_type="gap_detection",
            workflow_version="synthetic-ai-03-v1",
            prompt_version="synthetic-gap-prompt-v1",
            output_schema={},
            input_context={
                "project_type": "landing",
                "completion_checklist_version": COMPLETION_CHECKLIST_VERSION,
                "context_items": ({"context_item_id": "synthetic"},),
                "requirements": (),
            },
            routing_policy={},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={},
            metadata={},
        )
    )
    assert isinstance(response.data, CandidateGapBatch)
    assert response.data.items == ()
