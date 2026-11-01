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
from app.modules.sharing.application.approval_ports import (
    ScopeApprovalRepository,
    ScopeApprovalRepositoryError,
    ScopeApprovalTarget,
    ScopeApprovalUnitOfWork,
)
from app.modules.sharing.domain.scope_approval import (
    NewScopeApproval,
    ScopeApproval,
    ScopeApprovalValidationError,
)
from app.modules.sharing.infrastructure.models import ScopeApprovalModel, ScopeShareLinkModel


class SqlAlchemyScopeApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve_target_for_update(
        self, *, token_hash: bytes, now: datetime
    ) -> ScopeApprovalTarget | None:
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
        return ScopeApprovalTarget(
            account_id=link.account_id,
            project_id=link.project_id,
            share_link_id=link.id,
            scope_version_id=version.id,
            version_no=version.version_no,
            version_hash=version.snapshot_hash,
            scope_status=version.status,
        )

    async def approval_for_scope_version(self, scope_version_id: UUID) -> ScopeApproval | None:
        model = await self._session.scalar(
            select(ScopeApprovalModel).where(
                ScopeApprovalModel.scope_version_id == scope_version_id
            )
        )
        return _from_model(model) if model is not None else None

    async def add(self, approval: NewScopeApproval) -> ScopeApproval:
        model = ScopeApprovalModel(
            id=approval.id,
            account_id=approval.account_id,
            project_id=approval.project_id,
            scope_version_id=approval.scope_version_id,
            share_link_id=approval.share_link_id,
            version_no=approval.version_no,
            version_hash=approval.version_hash,
            guest_name=approval.guest_name,
            explicit_consent=approval.explicit_consent,
            idempotency_key=approval.idempotency_key,
            request_hash=approval.request_hash,
            approved_at=approval.approved_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ScopeApprovalRepositoryError("Scope Approval constraint failure") from exc
        return _from_model(model)

    async def mark_scope_version_approved(self, scope_version_id: UUID) -> None:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(ScopeVersionModel)
                .where(
                    ScopeVersionModel.id == scope_version_id,
                    ScopeVersionModel.status == "awaiting_approval",
                )
                .values(status="approved")
            ),
        )
        if result.rowcount != 1:
            raise ScopeApprovalRepositoryError("Scope Version approval transition failed")
        await self._session.flush()


class SqlAlchemyScopeApprovalUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeApprovalRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeApprovalRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyScopeApprovalUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeApprovalRepository(self._session)
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
            raise ScopeApprovalRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            raise ScopeApprovalRepositoryError("Scope Approval commit failed") from exc
        self._committed = True


class SqlAlchemyScopeApprovalUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeApprovalUnitOfWork:
        return SqlAlchemyScopeApprovalUnitOfWork(self._session_factory)


def _from_model(model: ScopeApprovalModel) -> ScopeApproval:
    try:
        return ScopeApproval(
            id=model.id,
            account_id=model.account_id,
            project_id=model.project_id,
            scope_version_id=model.scope_version_id,
            share_link_id=model.share_link_id,
            version_no=model.version_no,
            version_hash=model.version_hash,
            guest_name=model.guest_name,
            explicit_consent=model.explicit_consent,
            idempotency_key=model.idempotency_key,
            request_hash=model.request_hash,
            approved_at=model.approved_at,
        )
    except ScopeApprovalValidationError:
        raise ScopeApprovalRepositoryError from None
