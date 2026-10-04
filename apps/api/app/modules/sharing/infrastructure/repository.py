from __future__ import annotations

from datetime import datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.scope.infrastructure.models import ScopeVersionModel
from app.modules.sharing.application.ports import (
    ResolvedPublicScope,
    ScopeShareLinkRepository,
    ScopeShareLinkRepositoryError,
    ScopeShareLinkUnitOfWork,
)
from app.modules.sharing.domain.scope_share_link import (
    NewScopeShareLink,
    ScopeShareLink,
    ScopeShareLinkValidationError,
)
from app.modules.sharing.infrastructure.models import ScopeShareLinkModel
from app.shared.idempotency import IdempotencyRepository, IdempotencyRepositoryError


class SqlAlchemyScopeShareLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def create_route_key(project_id: UUID) -> str:
        return f"POST:/api/v1/projects/{project_id}/scope/versions/share"

    @staticmethod
    def revoke_route_key(project_id: UUID) -> str:
        return f"POST:/api/v1/projects/{project_id}/scope-shares/revoke"

    async def scope_version_id(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> UUID | None:
        return await self._session.scalar(
            select(ScopeVersionModel.id)
            .join(
                ProjectModel,
                (ProjectModel.id == ScopeVersionModel.project_id)
                & (ProjectModel.account_id == ScopeVersionModel.account_id),
            )
            .where(
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
                ScopeVersionModel.version_no == version_no,
                ProjectModel.deleted_at.is_(None),
            )
        )

    async def scope_version_exists(
        self, *, account_id: UUID, project_id: UUID, scope_version_id: UUID
    ) -> bool:
        target = await self._session.scalar(
            select(ScopeVersionModel.id)
            .join(
                ProjectModel,
                (ProjectModel.id == ScopeVersionModel.project_id)
                & (ProjectModel.account_id == ScopeVersionModel.account_id),
            )
            .where(
                ScopeVersionModel.id == scope_version_id,
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        return target is not None

    async def add(self, link: NewScopeShareLink) -> ScopeShareLink:
        model = ScopeShareLinkModel(
            id=link.id,
            account_id=link.account_id,
            project_id=link.project_id,
            scope_version_id=link.scope_version_id,
            token_hash=link.token_hash,
            expires_at=link.expires_at,
            created_by=link.created_by,
            created_at=link.created_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as exc:
            raise ScopeShareLinkRepositoryError("Scope Share Link constraint failure") from exc
        return _from_model(model)

    async def get_for_update(
        self, *, account_id: UUID, project_id: UUID, share_link_id: UUID
    ) -> ScopeShareLink | None:
        model = await self._session.scalar(
            select(ScopeShareLinkModel)
            .join(
                ProjectModel,
                (ProjectModel.id == ScopeShareLinkModel.project_id)
                & (ProjectModel.account_id == ScopeShareLinkModel.account_id),
            )
            .where(
                ScopeShareLinkModel.id == share_link_id,
                ScopeShareLinkModel.account_id == account_id,
                ScopeShareLinkModel.project_id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return _from_model(model) if model is not None else None

    async def set_revoked(self, link: ScopeShareLink) -> ScopeShareLink:
        model = await self._session.get(ScopeShareLinkModel, link.id)
        if model is None:
            raise ScopeShareLinkRepositoryError("Scope Share Link disappeared while locked")
        model.revoked_at = link.revoked_at
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as exc:
            raise ScopeShareLinkRepositoryError("Scope Share Link revocation failed") from exc
        return _from_model(model)

    async def resolve_public(
        self, *, token_hash: bytes, now: datetime
    ) -> ResolvedPublicScope | None:
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
                .with_for_update(read=True, of=ScopeShareLinkModel)
            )
        ).one_or_none()
        if row is None:
            return None
        link, version = row[0], row[1]
        return ResolvedPublicScope(
            share_link_id=link.id,
            scope_version_id=version.id,
            version_no=version.version_no,
            snapshot_data=version.snapshot_data,
        )


class SqlAlchemyScopeShareLinkUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeShareLinkRepository | None = None
        self._idempotency: SqlAlchemyIdempotencyRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeShareLinkRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    @property
    def idempotency(self) -> IdempotencyRepository:
        if self._idempotency is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._idempotency

    async def __aenter__(self) -> SqlAlchemyScopeShareLinkUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeShareLinkRepository(self._session)
        self._idempotency = SqlAlchemyIdempotencyRepository(self._session)
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
        self._idempotency = None
        if isinstance(exc, (SQLAlchemyError, IdempotencyRepositoryError)):
            raise ScopeShareLinkRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyScopeShareLinkUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeShareLinkUnitOfWork:
        return SqlAlchemyScopeShareLinkUnitOfWork(self._session_factory)


def _from_model(model: ScopeShareLinkModel) -> ScopeShareLink:
    try:
        return ScopeShareLink(
            id=model.id,
            account_id=model.account_id,
            project_id=model.project_id,
            scope_version_id=model.scope_version_id,
            token_hash=bytes(model.token_hash),
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_by=model.created_by,
            created_at=model.created_at,
        )
    except ScopeShareLinkValidationError:
        raise ScopeShareLinkRepositoryError from None
