from __future__ import annotations

import asyncio
from uuid import uuid4

from aria_backend_application.requirements_generation import RequirementGenerationResult

from app.application.requirements_generation import GenerateRequirementsTask


class SharedUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command):
        self.command = command
        return RequirementGenerationResult(
            requirement_ids=(uuid4(),),
            persisted_count=1,
            unsupported_count=0,
            duplicate_count=0,
            conflict_count=0,
        )


def test_worker_task_delegates_to_shared_requirement_generation_use_case() -> None:
    use_case = SharedUseCase()
    task = GenerateRequirementsTask(use_case)
    command = object()

    result = asyncio.run(task.execute(command))

    assert use_case.command is command
    assert result.persisted_count == 1
