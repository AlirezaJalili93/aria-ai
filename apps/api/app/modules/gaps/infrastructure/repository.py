from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.infrastructure.models import ContextSourceModel, ContextSourceVersionModel
from app.modules.gaps.application.ports import (
    GapProvenanceTarget,
    GapRepository,
    GapRepositoryError,
    GapUnitOfWork,
)
from app.modules.gaps.domain.gap import (
    GAP_SEVERITIES,
    GAP_STATUSES,
    GAP_TYPES,
    Gap,
    GapSeverity,
    GapSourceReference,
    GapStatus,
    GapType,
    GapValidationError,
    NewGap,
)
from app.modules.gaps.infrastructure.models import GapModel


class SqlAlchemyGapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> GapProvenanceTarget | None:
        row = (
            await self._session.execute(
                select(ContextSourceVersionModel.canonical_text)
                .join(
                    ContextSourceModel,
                    (ContextSourceModel.id == ContextSourceVersionModel.source_id)
                    & (ContextSourceModel.account_id == ContextSourceVersionModel.account_id)
                    & (ContextSourceModel.project_id == ContextSourceVersionModel.project_id),
                )
                .where(
                    ContextSourceVersionModel.id == source_version_id,
                    ContextSourceVersionModel.source_id == source_id,
                    ContextSourceVersionModel.account_id == account_id,
                    ContextSourceVersionModel.project_id == project_id,
                    ContextSourceVersionModel.parse_status == "ready",
                    ContextSourceModel.id == source_id,
                    ContextSourceModel.account_id == account_id,
                    ContextSourceModel.project_id == project_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        canonical_text = cast(str | None, row[0])
        return GapProvenanceTarget(
            account_id=account_id,
            project_id=project_id,
            source_id=source_id,
            source_version_id=source_version_id,
            canonical_text_length=len(canonical_text) if canonical_text is not None else None,
        )

    async def add(self, gap: NewGap) -> Gap:
        model = GapModel(
            id=gap.id,
            account_id=gap.account_id,
            project_id=gap.project_id,
            context_version=gap.context_version,
            gap_type=gap.gap_type,
            severity=gap.severity,
            status=gap.status,
            source_refs=[reference.to_dict() for reference in gap.source_refs],
            resolved_at=gap.resolved_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _gap_from_model(model)


class SqlAlchemyGapUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyGapRepository | None = None
        self._committed = False

    @property
    def repository(self) -> GapRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyGapUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyGapRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, traceback
        if self._session is None:
            return
        if not self._committed:
            await self._session.rollback()
        await self._session.close()
        if isinstance(exc, SQLAlchemyError):
            raise GapRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyGapUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> GapUnitOfWork:
        return SqlAlchemyGapUnitOfWork(self._session_factory)


def _gap_from_model(model: GapModel) -> Gap:
    if (
        model.gap_type not in GAP_TYPES
        or model.severity not in GAP_SEVERITIES
        or model.status not in GAP_STATUSES
    ):
        raise GapValidationError("Persisted Gap vocabulary is invalid")
    return Gap(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        gap_type=cast(GapType, model.gap_type),
        severity=cast(GapSeverity, model.severity),
        status=cast(GapStatus, model.status),
        source_refs=tuple(_source_reference_from_dict(value) for value in model.source_refs),
        created_at=model.created_at,
        updated_at=model.updated_at,
        resolved_at=model.resolved_at,
    )


def _source_reference_from_dict(value: dict[str, object]) -> GapSourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if set(value) - allowed or "source_id" not in value or "source_version_id" not in value:
        raise GapValidationError("Persisted Source Reference shape is invalid")
    try:
        return GapSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError) as error:
        raise GapValidationError("Persisted Source Reference shape is invalid") from error
