from __future__ import annotations

from app.modules.context.application.context_item_ports import (
    ContextItemRepository,
    ContextItemUnitOfWorkFactory,
)
from app.modules.context.domain.context_item import ContextItem, NewContextItem, SourceReference


class ContextItemProvenanceError(ValueError):
    """A Source Reference did not resolve to valid same-tenant ready provenance."""


class CreateContextItemUseCase:
    def __init__(self, unit_of_work_factory: ContextItemUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(self, item: NewContextItem) -> ContextItem:
        async with self._unit_of_work_factory() as unit_of_work:
            for source_ref in item.source_refs:
                await self._validate_reference(unit_of_work.repository, item, source_ref)
            persisted = await unit_of_work.repository.add(item)
            await unit_of_work.commit()
            return persisted

    @staticmethod
    async def _validate_reference(
        repository: ContextItemRepository,
        item: NewContextItem,
        source_ref: SourceReference,
    ) -> None:
        target = await repository.resolve_provenance(
            account_id=item.account_id,
            project_id=item.project_id,
            source_id=source_ref.source_id,
            source_version_id=source_ref.source_version_id,
        )
        if (
            target is None
            or target.account_id != item.account_id
            or target.project_id != item.project_id
            or target.source_id != source_ref.source_id
            or target.source_version_id != source_ref.source_version_id
        ):
            raise ContextItemProvenanceError("Source Reference is not valid ready provenance")
        if source_ref.end_offset is not None and (
            target.canonical_text_length is None
            or source_ref.end_offset > target.canonical_text_length
        ):
            raise ContextItemProvenanceError("Source Reference offsets exceed canonical text")
