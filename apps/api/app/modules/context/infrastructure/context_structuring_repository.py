from __future__ import annotations

from types import TracebackType
from uuid import UUID

from aria_backend_application.context_structuring import (
    ContextStructuringRepository,
    ContextStructuringRepositoryError,
    ContextStructuringUnitOfWork,
    ContextVersionWrite,
    SourceSnapshot,
)
from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.infrastructure.models import (
    ContextItemModel,
    ContextSourceModel,
    ContextSourceVersionModel,
)
from app.modules.projects.infrastructure.models import ProjectModel


class SqlAlchemyContextSnapshotReader:
    """Resolve exactly one latest ready Version for every non-deleted project Source."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_latest_ready(
        self, *, account_id: UUID, project_id: UUID
    ) -> tuple[SourceSnapshot, ...]:
        rank = func.row_number().over(
            partition_by=ContextSourceVersionModel.source_id,
            order_by=ContextSourceVersionModel.version_no.desc(),
        ).label("ready_rank")
        ranked = (
            select(
                ContextSourceVersionModel.source_id.label("source_id"),
                ContextSourceVersionModel.id.label("source_version_id"),
                ContextSourceVersionModel.version_no.label("version_no"),
                ContextSourceVersionModel.canonical_text.label("canonical_text"),
                ContextSourceVersionModel.storage_ref.label("storage_ref"),
                rank,
            )
            .join(
                ContextSourceModel,
                (ContextSourceModel.id == ContextSourceVersionModel.source_id)
                & (ContextSourceModel.account_id == ContextSourceVersionModel.account_id)
                & (ContextSourceModel.project_id == ContextSourceVersionModel.project_id),
            )
            .where(
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.parse_status == "ready",
                ContextSourceModel.account_id == account_id,
                ContextSourceModel.project_id == project_id,
                ContextSourceModel.status != "deleted",
            )
            .subquery()
        )
        try:
            async with self._session_factory() as session:
                rows = (
                    await session.execute(
                        select(
                            ranked.c.source_id,
                            ranked.c.source_version_id,
                            ranked.c.version_no,
                            ranked.c.canonical_text,
                            ranked.c.storage_ref,
                        )
                        .where(ranked.c.ready_rank == 1)
                        .order_by(ranked.c.source_id)
                    )
                ).all()
        except SQLAlchemyError as error:
            raise ContextStructuringRepositoryError("source_snapshot_failed") from error
        return tuple(
            SourceSnapshot(
                source_id=row.source_id,
                source_version_id=row.source_version_id,
                version_no=row.version_no,
                canonical_text=row.canonical_text,
                storage_ref=row.storage_ref,
            )
            for row in rows
        )


class SqlAlchemyContextStructuringRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate_next_version(self, *, account_id: UUID, project_id: UUID) -> int:
        current_version = await self._session.scalar(
            select(ProjectModel.current_context_version)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if current_version is None:
            raise ContextStructuringRepositoryError("project_not_available")
        return current_version + 1

    async def add_batch(self, items: tuple[ContextVersionWrite, ...]) -> None:
        self._session.add_all(
            [
                ContextItemModel(
                    id=item.id,
                    account_id=item.account_id,
                    project_id=item.project_id,
                    context_version=item.context_version,
                    item_type=item.item_type,
                    content=item.content,
                    source_refs=[
                        {
                            "source_id": str(reference.source_id),
                            "source_version_id": str(reference.source_version_id),
                            **(
                                {
                                    "start_offset": reference.start_offset,
                                    "end_offset": reference.end_offset,
                                }
                                if reference.start_offset is not None
                                else {}
                            ),
                        }
                        for reference in item.source_refs
                    ],
                    confidence=item.confidence,
                    status=item.status,
                    created_by_type=item.created_by_type,
                    created_by=item.created_by,
                )
                for item in items
            ]
        )
        await self._session.flush()

    async def advance_project_version(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> None:
        updated_project_id = await self._session.scalar(
            update(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.current_context_version == context_version - 1,
                ProjectModel.deleted_at.is_(None),
            )
            .values(current_context_version=context_version)
            .returning(ProjectModel.id)
        )
        if updated_project_id is None:
            raise ContextStructuringRepositoryError("context_version_conflict")


class SqlAlchemyContextStructuringUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyContextStructuringRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ContextStructuringRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyContextStructuringUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyContextStructuringRepository(self._session)
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
            raise ContextStructuringRepositoryError("context_persistence_failed") from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyContextStructuringUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ContextStructuringUnitOfWork:
        return SqlAlchemyContextStructuringUnitOfWork(self._session_factory)
