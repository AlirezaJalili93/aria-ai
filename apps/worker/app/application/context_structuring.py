from __future__ import annotations

from aria_backend_application.context_structuring import (
    ContextStructuringCommand,
    ContextStructuringResult,
    ContextStructuringUseCaseProtocol,
)


class ContextStructuringTask:
    """Worker transport wrapper; all Context rules remain in the shared use case."""

    def __init__(self, use_case: ContextStructuringUseCaseProtocol) -> None:
        self._use_case = use_case

    async def execute(self, command: ContextStructuringCommand) -> ContextStructuringResult:
        return await self._use_case.execute(command)
