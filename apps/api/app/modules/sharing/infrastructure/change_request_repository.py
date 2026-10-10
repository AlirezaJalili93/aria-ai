from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.scope.infrastructure.models import ScopeVersionModel
from app.modules.sharing.application.change_request_ports import (
    ScopeChangeRequestRepository,
    ScopeChangeRequestRepositoryError,
    ScopeChangeRequestTarget,
    ScopeChangeRequestUnitOfWork,
)
from app.modules.sharing.domain.scope_change_request import (
    NewScopeChangeRequest,
    ScopeChangeRequest,
    ScopeChangeRequestValidationError,
)
from app.modules.sharing.infrastructure.models import (
    ScopeChangeRequestModel,
    ScopeShareLinkModel,
)


class SqlAlchemyScopeChangeRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_target_for_update(
        self, *, token_hash: bytes, now: datetime
    ) -> ScopeChangeRequestTarget | None:
        row = (
            await self._session.execute(
                select(ScopeShareLinkModel, ScopeVersionModel)
                .join(
                    ScopeVersionModel,
                    (ScopeVersionModel.id == ScopeShareLinkModel.scope_version_id)
                    & (ScopeVersionModel.account_id == ScopeShareLinkModel.account_id)
                    & (ScopeVersionModel.project_id == ScopeShareLinkModel.project_id),
                )
                .join(
                    ProjectModel,
                    (ProjectModel.id == ScopeShareLinkModel.project_id)
                    & (ProjectModel.account_id == ScopeShareLinkModel.account_id),
                )
                .where(
                    ScopeShareLinkModel.token_hash == token_hash,
                    ScopeShareLinkModel.revoked_at.is_(None),
                    ScopeShareLinkModel.expires_at > now,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update(of=(ScopeShareLinkModel, ScopeVersionModel))
            )
        ).one_or_none()
        if row is None:
            return None
        link, version = row[0], row[1]
        return ScopeChangeRequestTarget(
            account_id=link.account_id,
            project_id=link.project_id,
            share_link_id=link.id,
            scope_version_id=version.id,
            version_no=version.version_no,
            version_hash=version.snapshot_hash,
            scope_status=version.status,
        )

    async def change_request_for_scope_version(
        self, scope_version_id: UUID
    ) -> ScopeChangeRequest | None:
        model = await self._session.scalar(
            select(ScopeChangeRequestModel).where(
                ScopeChangeRequestModel.scope_version_id == scope_version_id
            )
        )
        return _from_model(model) if model is not None else None

    async def add(self, change_request: NewScopeChangeRequest) -> ScopeChangeRequest:
        model = ScopeChangeRequestModel(
            id=change_request.id,
            account_id=change_request.account_id,
            project_id=change_request.project_id,
            scope_version_id=change_request.scope_version_id,
            share_link_id=change_request.share_link_id,
            version_no=change_request.version_no,
            version_hash=change_request.version_hash,
            guest_name=change_request.guest_name,
            comment=change_request.comment,
            idempotency_key=change_request.idempotency_key,
            request_hash=change_request.request_hash,
            requested_at=change_request.requested_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ScopeChangeRequestRepositoryError(
                "Scope Change Request constraint failure"
            ) from exc
        return _from_model(model)

    async def mark_scope_version_changes_requested(self, scope_version_id: UUID) -> None:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(ScopeVersionModel)
                .where(
                    ScopeVersionModel.id == scope_version_id,
                    ScopeVersionModel.status == "awaiting_approval",
                )
                .values(status="changes_requested")
            ),
        )
        if result.rowcount != 1:
            raise ScopeChangeRequestRepositoryError(
                "Scope Version Change Request transition failed"
            )
        await self._session.flush()


class SqlAlchemyScopeChangeRequestUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeChangeRequestRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeChangeRequestRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyScopeChangeRequestUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeChangeRequestRepository(self._session)
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
        self._session = None
        self._repository = None
        if isinstance(exc, SQLAlchemyError):
            raise ScopeChangeRequestRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            raise ScopeChangeRequestRepositoryError(
                "Scope Change Request commit failed"
            ) from exc
        self._committed = True


class SqlAlchemyScopeChangeRequestUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeChangeRequestUnitOfWork:
        return SqlAlchemyScopeChangeRequestUnitOfWork(self._session_factory)


def _from_model(model: ScopeChangeRequestModel) -> ScopeChangeRequest:
    try:
        return ScopeChangeRequest(
            id=model.id,
            account_id=model.account_id,
            project_id=model.project_id,
            scope_version_id=model.scope_version_id,
            share_link_id=model.share_link_id,
            version_no=model.version_no,
            version_hash=model.version_hash,
            guest_name=model.guest_name,
            comment=model.comment,
            idempotency_key=model.idempotency_key,
            request_hash=model.request_hash,
            requested_at=model.requested_at,
        )
    except ScopeChangeRequestValidationError:
        raise ScopeChangeRequestRepositoryError from None
