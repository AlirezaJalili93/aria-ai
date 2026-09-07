from __future__ import annotations

from time import perf_counter

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.requirements.application.ports import (
    RequirementRepository,
    RequirementUnitOfWorkFactory,
)
from app.modules.requirements.domain.requirement import (
    NewRequirement,
    Requirement,
    RequirementSourceReference,
)


class RequirementContextVersionError(ValueError):
    """The Requirement does not reference an available Project Context Version."""


class RequirementProvenanceError(ValueError):
    """A Requirement Source Reference is not valid same-tenant ready provenance."""


class PersistRequirementUseCase:
    """Persist one already-constructed Requirement without exposing transport or AI behavior."""

    def __init__(
        self,
        unit_of_work_factory: RequirementUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger

    async def execute(self, requirement: NewRequirement) -> Requirement:
        started_at = perf_counter()
        async with self._unit_of_work_factory() as unit_of_work:
            current_context_version = (
                await unit_of_work.repository.get_project_current_context_version(
                    account_id=requirement.account_id,
                    project_id=requirement.project_id,
                )
            )
            if (
                current_context_version is None
                or requirement.context_version > current_context_version
            ):
                raise RequirementContextVersionError(
                    "Requirement context_version is not available for the Project"
                )
            enrich_trace_context(
                account_id=str(requirement.account_id),
                project_id=str(requirement.project_id),
            )
            for source_ref in requirement.source_refs:
                await self._validate_reference(
                    unit_of_work.repository, requirement, source_ref
                )
            persisted = await unit_of_work.repository.add(requirement)
            await unit_of_work.commit()

        self._event_logger.emit(
            "requirement.created",
            requirement_id=str(persisted.id),
            context_version=persisted.context_version,
            priority=persisted.priority,
            created_by_type=persisted.created_by_type,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    @staticmethod
    async def _validate_reference(
        repository: RequirementRepository,
        requirement: NewRequirement,
        source_ref: RequirementSourceReference,
    ) -> None:
        target = await repository.resolve_provenance(
            account_id=requirement.account_id,
            project_id=requirement.project_id,
            source_id=source_ref.source_id,
            source_version_id=source_ref.source_version_id,
        )
        if (
            target is None
            or target.account_id != requirement.account_id
            or target.project_id != requirement.project_id
            or target.source_id != source_ref.source_id
            or target.source_version_id != source_ref.source_version_id
        ):
            raise RequirementProvenanceError(
                "Requirement Source Reference is not valid ready provenance"
            )
        if source_ref.end_offset is not None and (
            target.canonical_text_length is None
            or source_ref.end_offset > target.canonical_text_length
        ):
            raise RequirementProvenanceError(
                "Requirement Source Reference offsets exceed canonical text"
            )
