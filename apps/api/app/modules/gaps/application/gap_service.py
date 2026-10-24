from __future__ import annotations

from time import perf_counter

from aria_observability import StructuredEventLogger, enrich_trace_context

from app.modules.gaps.application.ports import GapRepository, GapUnitOfWorkFactory
from app.modules.gaps.domain.gap import Gap, GapSourceReference, NewGap


class GapProvenanceError(ValueError):
    """A Gap Source Reference is not valid same-tenant ready provenance."""


class PersistGapUseCase:
    """Persist one already-constructed Gap without J02/J03 behavior."""

    def __init__(
        self,
        unit_of_work_factory: GapUnitOfWorkFactory,
        event_logger: StructuredEventLogger,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger

    async def execute(self, gap: NewGap) -> Gap:
        started_at = perf_counter()
        enrich_trace_context(account_id=str(gap.account_id), project_id=str(gap.project_id))
        async with self._unit_of_work_factory() as unit_of_work:
            for source_ref in gap.source_refs:
                await self._validate_reference(unit_of_work.repository, gap, source_ref)
            persisted = await unit_of_work.repository.add(gap)
            await unit_of_work.commit()

        self._event_logger.emit(
            "gap.created",
            gap_id=str(persisted.id),
            context_version=persisted.context_version,
            gap_type=persisted.gap_type,
            severity=persisted.severity,
            gap_status=persisted.status,
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return persisted

    @staticmethod
    async def _validate_reference(
        repository: GapRepository,
        gap: NewGap,
        source_ref: GapSourceReference,
    ) -> None:
        target = await repository.resolve_provenance(
            account_id=gap.account_id,
            project_id=gap.project_id,
            source_id=source_ref.source_id,
            source_version_id=source_ref.source_version_id,
        )
        if (
            target is None
            or target.account_id != gap.account_id
            or target.project_id != gap.project_id
            or target.source_id != source_ref.source_id
            or target.source_version_id != source_ref.source_version_id
        ):
            raise GapProvenanceError("Gap Source Reference is not valid ready provenance")
        if source_ref.end_offset is not None and (
            target.canonical_text_length is None
            or source_ref.end_offset > target.canonical_text_length
        ):
            raise GapProvenanceError("Gap Source Reference offsets exceed canonical text")
