from __future__ import annotations

import asyncio
from uuid import uuid4

from aria_backend_application.requirements_generation import CandidateRequirementBatch

from app.infrastructure.ai.synthetic_requirement_generation import (
    SyntheticRequirementGenerationAI,
)


def test_synthetic_ai02_returns_deterministic_supported_candidate() -> None:
    source_id, version_id = uuid4(), uuid4()
    response = asyncio.run(
        SyntheticRequirementGenerationAI().execute_structured(
            task_type="requirement_generation",
            workflow_version="synthetic-ai-02-v1",
            prompt_version="synthetic-prompt-v1",
            output_schema={},
            input_context={
                "context_items": (
                    {
                        "source_refs": (
                            {
                                "source_id": str(source_id),
                                "source_version_id": str(version_id),
                            },
                        )
                    },
                )
            },
            routing_policy={},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={},
            metadata={},
        )
    )
    assert isinstance(response.data, CandidateRequirementBatch)
    assert response.provider == "synthetic"
    assert response.input_tokens == response.output_tokens == 0
    assert response.data.items[0].source_refs[0].source_id == source_id
