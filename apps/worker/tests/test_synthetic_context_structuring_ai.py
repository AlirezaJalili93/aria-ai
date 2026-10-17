from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from aria_backend_application.ai_execution import AIExecutionError
from aria_backend_application.context_structuring import CandidateContextBatch

from app.infrastructure.ai.synthetic_context_structuring import SyntheticContextStructuringAI


def _execute(task_type: str = "context_structuring"):
    return asyncio.run(
        SyntheticContextStructuringAI().execute_structured(
            task_type=task_type,
            workflow_version="synthetic-ai-01-v1",
            prompt_version="synthetic-prompt-v1",
            output_schema={},
            input_context={
                "sources": (
                    {
                        "source_id": str(uuid4()),
                        "source_version_id": str(uuid4()),
                        "canonical_text": "customer-like synthetic fixture",
                    },
                )
            },
            routing_policy={},
            cost_budget={},
            timeout_policy={},
            metadata={},
        )
    )


def test_synthetic_ai_returns_constant_non_echoed_zero_cost_batch() -> None:
    response = _execute()
    assert response.provider == "synthetic"
    assert response.estimated_cost == 0
    assert isinstance(response.data, CandidateContextBatch)
    assert "customer-like" not in response.data.items[0].content


def test_synthetic_ai_rejects_any_other_task_type() -> None:
    with pytest.raises(AIExecutionError) as raised:
        _execute("requirements")
    assert raised.value.error_class == "invalid_response"
