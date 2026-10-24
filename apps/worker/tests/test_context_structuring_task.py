from __future__ import annotations

import asyncio

from aria_backend_application.context_structuring import ContextStructuringResult

from app.application.context_structuring import ContextStructuringTask


class SharedUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command):
        self.command = command
        return ContextStructuringResult(context_version=3, item_count=2)


def test_worker_task_invokes_shared_backend_application_use_case() -> None:
    use_case = SharedUseCase()
    task = ContextStructuringTask(use_case)
    command = object()
    result = asyncio.run(task.execute(command))
    assert use_case.command is command
    assert result == ContextStructuringResult(context_version=3, item_count=2)
