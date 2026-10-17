from __future__ import annotations

import asyncio
from uuid import uuid4

from aria_backend_application.scope_content import SECTION_IDS, validate_scope_content

from app.infrastructure.ai.synthetic_scope_generation import SyntheticScopeGenerationAI


def test_fake_produces_valid_twelve_section_traceable_scope() -> None:
    context_id, requirement_id = uuid4(), uuid4()
    response = asyncio.run(
        SyntheticScopeGenerationAI().execute_structured(
            task_type="scope_generation",
            workflow_version="synthetic-ai-05-v1",
            prompt_version="synthetic-scope-prompt-v1",
            output_schema={"schema_version": "scope_content_schema_v1"},
            input_context={
                "context_items": [{"id": str(context_id), "content": "نمونه مصنوعی"}],
                "requirements": [
                    {"id": str(requirement_id), "title": "نیاز مصنوعی", "priority": "must"}
                ],
            },
            routing_policy={"synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
            metadata={},
        )
    )
    content = validate_scope_content(response.data)
    assert {item["section_id"] for item in content["sections"]} == set(SECTION_IDS)
    requirement_section = next(
        item for item in content["sections"] if item["section_id"] == "requirements"
    )
    assert requirement_section["trace"]["requirement_ids"] == [str(requirement_id)]
    assert response.provider == "synthetic"
    assert response.input_tokens == response.output_tokens == 0
