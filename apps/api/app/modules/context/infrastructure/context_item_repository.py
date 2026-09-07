from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.application.context_item_ports import (
    ContextItemRepository,
    ContextItemRepositoryError,
    ContextItemUnitOfWork,
    CurrentContextItems,
    ProvenanceTarget,
)
from app.modules.context.domain.context_item import (
    CONTEXT_ITEM_CREATOR_TYPES,
    CONTEXT_ITEM_STATUSES,
    CONTEXT_ITEM_TYPES,
    ContextItem,
    ContextItemCreatorType,
    ContextItemStatus,
    ContextItemType,
    ContextItemValidationError,
    NewContextItem,
    SourceReference,
)
from app.modules.context.infrastructure.models import (
    ContextItemModel,
    ContextSourceModel,
    ContextSourceVersionModel,
)
from app.modules.projects.infrastructure.models import ProjectModel


class SqlAlchemyContextItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> ProvenanceTarget | None:
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
        return ProvenanceTarget(
            account_id=account_id,
            project_id=project_id,
            source_id=source_id,
            source_version_id=source_version_id,
            canonical_text_length=len(canonical_text) if canonical_text is not None else None,
        )

    async def add(self, item: NewContextItem) -> ContextItem:
        model = ContextItemModel(
            id=item.id,
            account_id=item.account_id,
            project_id=item.project_id,
            context_version=item.context_version,
            item_type=item.item_type,
            content=item.content,
            source_refs=[source_ref.to_dict() for source_ref in item.source_refs],
            confidence=item.confidence,
            status=item.status,
            created_by_type=item.created_by_type,
            created_by=item.created_by,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _context_item_from_model(model)

    async def list_current(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        item_type: ContextItemType | None,
        status: ContextItemStatus | None,
        source_id: UUID | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> CurrentContextItems | None:
        current_version = (
            await self._session.execute(
                select(ProjectModel.current_context_version).where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if current_version is None:
            return None

        statement = select(ContextItemModel).where(
            ContextItemModel.account_id == account_id,
            ContextItemModel.project_id == project_id,
            ContextItemModel.context_version == current_version,
        )
        if item_type is not None:
            statement = statement.where(ContextItemModel.item_type == item_type)
        if status is not None:
            statement = statement.where(ContextItemModel.status == status)
        if source_id is not None:
            statement = statement.where(
                ContextItemModel.source_refs.contains([{"source_id": str(source_id)}])
            )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    ContextItemModel.created_at < cursor_created_at,
                    (ContextItemModel.created_at == cursor_created_at)
                    & (ContextItemModel.id < cursor_id),
                )
            )
        rows = (
            await self._session.scalars(
                statement.order_by(
                    ContextItemModel.created_at.desc(), ContextItemModel.id.desc()
                ).limit(limit)
            )
        ).all()
        return CurrentContextItems(
            context_version=current_version,
            items=tuple(_context_item_from_model(model) for model in rows),
        )

    async def get_current_for_update(
        self, *, account_id: UUID, project_id: UUID, item_id: UUID
    ) -> ContextItem | None:
        model = (
            await self._session.scalars(
                select(ContextItemModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == ContextItemModel.project_id)
                    & (ProjectModel.account_id == ContextItemModel.account_id),
                )
                .where(
                    ContextItemModel.id == item_id,
                    ContextItemModel.account_id == account_id,
                    ContextItemModel.project_id == project_id,
                    ContextItemModel.context_version == ProjectModel.current_context_version,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update(of=ContextItemModel)
            )
        ).one_or_none()
        return _context_item_from_model(model) if model is not None else None

    async def update_proposed(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        item_id: UUID,
        expected_updated_at: datetime,
        content: str,
        status: Literal["proposed", "confirmed", "rejected"],
    ) -> ContextItem | None:
        current_version = (
            select(ProjectModel.current_context_version)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .scalar_subquery()
        )
        model = (
            await self._session.scalars(
                update(ContextItemModel)
                .where(
                    ContextItemModel.id == item_id,
                    ContextItemModel.account_id == account_id,
                    ContextItemModel.project_id == project_id,
                    ContextItemModel.context_version == current_version,
                    ContextItemModel.status == "proposed",
                    ContextItemModel.updated_at == expected_updated_at,
                )
                .values(content=content, status=status)
                .returning(ContextItemModel)
            )
        ).one_or_none()
        return _context_item_from_model(model) if model is not None else None


class SqlAlchemyContextItemUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyContextItemRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ContextItemRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyContextItemUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyContextItemRepository(self._session)
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
            raise ContextItemRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyContextItemUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ContextItemUnitOfWork:
        return SqlAlchemyContextItemUnitOfWork(self._session_factory)


def _context_item_from_model(model: ContextItemModel) -> ContextItem:
    if (
        model.item_type not in CONTEXT_ITEM_TYPES
        or model.status not in CONTEXT_ITEM_STATUSES
        or model.created_by_type not in CONTEXT_ITEM_CREATOR_TYPES
    ):
        raise ContextItemValidationError("Persisted Context Item vocabulary is invalid")
    source_refs = tuple(_source_reference_from_dict(value) for value in model.source_refs)
    return ContextItem(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        item_type=cast(ContextItemType, model.item_type),
        content=model.content,
        source_refs=source_refs,
        confidence=model.confidence,
        status=cast(ContextItemStatus, model.status),
        created_by_type=cast(ContextItemCreatorType, model.created_by_type),
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _source_reference_from_dict(value: dict[str, object]) -> SourceReference:
    allowed = {"source_id", "source_version_id", "start_offset", "end_offset"}
    if set(value) - allowed or "source_id" not in value or "source_version_id" not in value:
        raise ContextItemValidationError("Persisted Source Reference shape is invalid")
    try:
        return SourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=cast(int | None, value.get("start_offset")),
            end_offset=cast(int | None, value.get("end_offset")),
        )
    except (TypeError, ValueError) as error:
        raise ContextItemValidationError("Persisted Source Reference shape is invalid") from error
