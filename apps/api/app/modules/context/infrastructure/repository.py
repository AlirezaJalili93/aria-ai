from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.application.ports import (
    ContextSourceRepository,
    ContextSourceRepositoryError,
    ContextSourceUnitOfWork,
)
from app.modules.context.domain.context_source import (
    CONTEXT_SOURCE_PARSE_STATUSES,
    CONTEXT_SOURCE_STATUSES,
    CONTEXT_SOURCE_TYPES,
    ContextSource,
    ContextSourceParseStatus,
    ContextSourceStatus,
    ContextSourceType,
    ContextSourceValidationError,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
)
from app.modules.context.infrastructure.models import (
    ContextSourceModel,
    ContextSourceVersionModel,
)


class SqlAlchemyContextSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_source(self, source: NewContextSource) -> ContextSource:
        model = ContextSourceModel(
            id=source.id,
            account_id=source.account_id,
            project_id=source.project_id,
            source_type=source.source_type,
            status=source.status,
            original_name=source.original_name,
            mime_type=source.mime_type,
            storage_ref=source.storage_ref,
            raw_text=source.raw_text,
            checksum=source.checksum,
            created_by=source.created_by,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _source_from_model(model)

    async def get_source(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSource | None:
        model = await self._session.scalar(
            select(ContextSourceModel).where(
                ContextSourceModel.id == source_id,
                ContextSourceModel.account_id == account_id,
                ContextSourceModel.project_id == project_id,
                ContextSourceModel.status != "deleted",
            )
        )
        return _source_from_model(model) if model is not None else None

    async def set_source_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        status: ContextSourceStatus,
    ) -> ContextSource | None:
        model = await self._session.scalar(
            update(ContextSourceModel)
            .where(
                ContextSourceModel.id == source_id,
                ContextSourceModel.account_id == account_id,
                ContextSourceModel.project_id == project_id,
                ContextSourceModel.status != "deleted",
            )
            .values(status=status)
            .returning(ContextSourceModel)
        )
        return _source_from_model(model) if model is not None else None

    async def add_version(self, version: NewContextSourceVersion) -> ContextSourceVersion:
        model = ContextSourceVersionModel(
            id=version.id,
            account_id=version.account_id,
            project_id=version.project_id,
            source_id=version.source_id,
            version_no=version.version_no,
            content_hash=version.content_hash,
            canonical_text=version.canonical_text,
            storage_ref=version.storage_ref,
            version_metadata=version.metadata,
            parse_status=version.parse_status,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _version_from_model(model)

    async def mark_version_ready(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
        content_hash: str | None,
        canonical_text: str | None,
        storage_ref: str | None,
        metadata: dict[str, object] | None,
    ) -> ContextSourceVersion | None:
        model = await self._session.scalar(
            update(ContextSourceVersionModel)
            .where(
                ContextSourceVersionModel.id == version_id,
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.source_id == source_id,
                ContextSourceVersionModel.parse_status != "ready",
            )
            .values(
                content_hash=content_hash,
                canonical_text=canonical_text,
                storage_ref=storage_ref,
                version_metadata=metadata,
                parse_status="ready",
            )
            .returning(ContextSourceVersionModel)
        )
        return _version_from_model(model) if model is not None else None

    async def mark_version_failed(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        version_id: UUID,
    ) -> ContextSourceVersion | None:
        model = await self._session.scalar(
            update(ContextSourceVersionModel)
            .where(
                ContextSourceVersionModel.id == version_id,
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.source_id == source_id,
                ContextSourceVersionModel.parse_status != "ready",
            )
            .values(parse_status="failed")
            .returning(ContextSourceVersionModel)
        )
        return _version_from_model(model) if model is not None else None

    async def get_current_ready_version(
        self, *, account_id: UUID, project_id: UUID, source_id: UUID
    ) -> ContextSourceVersion | None:
        model = await self._session.scalar(
            select(ContextSourceVersionModel)
            .join(
                ContextSourceModel,
                (ContextSourceModel.id == ContextSourceVersionModel.source_id)
                & (ContextSourceModel.account_id == ContextSourceVersionModel.account_id)
                & (ContextSourceModel.project_id == ContextSourceVersionModel.project_id),
            )
            .where(
                ContextSourceVersionModel.account_id == account_id,
                ContextSourceVersionModel.project_id == project_id,
                ContextSourceVersionModel.source_id == source_id,
                ContextSourceVersionModel.parse_status == "ready",
                ContextSourceModel.status != "deleted",
            )
            .order_by(ContextSourceVersionModel.version_no.desc())
            .limit(1)
        )
        return _version_from_model(model) if model is not None else None


class SqlAlchemyContextSourceUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyContextSourceRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ContextSourceRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyContextSourceUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyContextSourceRepository(self._session)
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
            raise ContextSourceRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyContextSourceUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ContextSourceUnitOfWork:
        return SqlAlchemyContextSourceUnitOfWork(self._session_factory)


def _source_from_model(model: ContextSourceModel) -> ContextSource:
    if model.source_type not in CONTEXT_SOURCE_TYPES or model.status not in CONTEXT_SOURCE_STATUSES:
        raise ContextSourceValidationError("Persisted Context Source vocabulary is invalid")
    return ContextSource(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        source_type=cast(ContextSourceType, model.source_type),
        status=cast(ContextSourceStatus, model.status),
        original_name=model.original_name,
        mime_type=model.mime_type,
        storage_ref=model.storage_ref,
        raw_text=model.raw_text,
        checksum=model.checksum,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _version_from_model(model: ContextSourceVersionModel) -> ContextSourceVersion:
    if model.parse_status not in CONTEXT_SOURCE_PARSE_STATUSES:
        raise ContextSourceValidationError("Persisted Context Source parse status is invalid")
    return ContextSourceVersion(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        source_id=model.source_id,
        version_no=model.version_no,
        content_hash=model.content_hash,
        canonical_text=model.canonical_text,
        storage_ref=model.storage_ref,
        metadata=model.version_metadata,
        parse_status=cast(ContextSourceParseStatus, model.parse_status),
        created_at=model.created_at,
    )
