from aria_backend_application.requirements_generation import (
    GenerateRequirementsCommand,
    GenerateRequirementsUseCaseProtocol,
    RequirementGenerationResult,
)


class GenerateRequirementsTask:
    """Worker-facing adapter over the shared provider-neutral Application use case."""

    def __init__(self, use_case: GenerateRequirementsUseCaseProtocol) -> None:
        self._use_case = use_case

    async def execute(
        self, command: GenerateRequirementsCommand
    ) -> RequirementGenerationResult:
        return await self._use_case.execute(command)
