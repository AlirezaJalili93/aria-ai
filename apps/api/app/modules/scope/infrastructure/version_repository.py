from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.gaps.infrastructure.models import GapModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.scope.application.version_ports import (
    ScopeVersionCreateReservation,
    ScopeVersionFreezeTarget,
    ScopeVersionRepository,
    ScopeVersionRepositoryError,
    ScopeVersionUnitOfWork,
)
from app.modules.scope.domain.readiness import (
    ScopeReadinessGap,
    ScopeReadinessGapSeverity,
    ScopeReadinessGapStatus,
)
from app.modules.scope.domain.scope_draft import ScopeDraft, ScopeDraftActorType
from app.modules.scope.domain.scope_version import (
    NewScopeVersion,
    ScopeVersion,
    ScopeVersionStatus,
    ScopeVersionValidationError,
)
from app.modules.scope.infrastructure.models import ScopeDraftModel, ScopeVersionModel
from app.shared.idempotency import IdempotencyRepositoryError


class SqlAlchemyScopeVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._idempotency = SqlAlchemyIdempotencyRepository(session)

    @staticmethod
    def _route_key(project_id: UUID) -> str:
        return f"POST:/api/v1/projects/{project_id}/scope/versions"

    async def reserve_create(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        scope_version_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> ScopeVersionCreateReservation:
        try:
            reservation = await self._idempotency.reserve(
                record_id=scope_version_id,
                account_id=account_id,
                actor_id=actor_id,
                route_key=self._route_key(project_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                now=now,
                expires_at=expires_at,
            )
        except IdempotencyRepositoryError:
            raise ScopeVersionRepositoryError from None
        response: ScopeVersion | None = None
        reserved_id = scope_version_id
        if reservation.response_ref is not None:
            try:
                reserved_id = UUID(str(reservation.response_ref["scope_version_id"]))
            except (KeyError, TypeError, ValueError):
                raise ScopeVersionRepositoryError from None
            model = await self._session.scalar(
                select(ScopeVersionModel).where(
                    ScopeVersionModel.id == reserved_id,
                    ScopeVersionModel.account_id == account_id,
                    ScopeVersionModel.project_id == project_id,
                )
            )
            if model is None:
                raise ScopeVersionRepositoryError
            response = _from_model(model)
        return ScopeVersionCreateReservation(
            acquired=reservation.acquired,
            request_hash=reservation.request_hash,
            scope_version_id=reserved_id,
            response=response,
        )

    async def get_freeze_target(
        self, *, account_id: UUID, project_id: UUID
    ) -> ScopeVersionFreezeTarget | None:
        project = await self._session.scalar(
            select(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
                ProjectModel.current_context_version >= 1,
            )
            .with_for_update()
        )
        if project is None:
            return None
        draft_model = await self._session.scalar(
            select(ScopeDraftModel)
            .where(
                ScopeDraftModel.account_id == account_id,
                ScopeDraftModel.project_id == project_id,
                ScopeDraftModel.context_version == project.current_context_version,
            )
            .with_for_update()
        )
        gap_models = (
            await self._session.scalars(
                select(GapModel).where(
                    GapModel.account_id == account_id,
                    GapModel.project_id == project_id,
                    GapModel.context_version == project.current_context_version,
                )
            )
        ).all()
        latest = await self._session.scalar(
            select(ScopeVersionModel)
            .where(
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
            )
            .order_by(ScopeVersionModel.version_no.desc())
            .limit(1)
        )
        return ScopeVersionFreezeTarget(
            project_current_context_version=project.current_context_version,
            draft=_draft_from_model(draft_model) if draft_model is not None else None,
            gaps=tuple(
                ScopeReadinessGap(
                    id=model.id,
                    account_id=model.account_id,
                    project_id=model.project_id,
                    context_version=model.context_version,
                    severity=cast(ScopeReadinessGapSeverity, model.severity),
                    status=cast(ScopeReadinessGapStatus, model.status),
                )
                for model in gap_models
            ),
            latest_snapshot_hash=latest.snapshot_hash if latest is not None else None,
            next_version_no=(latest.version_no + 1) if latest is not None else 1,
        )

    async def add(self, version: NewScopeVersion) -> ScopeVersion:
        model = ScopeVersionModel(
            id=version.id,
            account_id=version.account_id,
            project_id=version.project_id,
            version_no=version.version_no,
            context_version=version.context_version,
            status=version.status,
            snapshot_data=version.snapshot_data,
            snapshot_hash=version.snapshot_hash,
            created_by=version.created_by,
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as exc:
            raise ScopeVersionRepositoryError("Scope Version constraint failure") from exc
        return _from_model(model)

    async def complete_create_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        idempotency_key: str,
        request_hash: str,
        version: ScopeVersion,
    ) -> None:
        try:
            await self._idempotency.complete(
                account_id=account_id,
                actor_id=actor_id,
                route_key=self._route_key(project_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=201,
                response_ref={"scope_version_id": str(version.id)},
            )
        except IdempotencyRepositoryError:
            raise ScopeVersionRepositoryError from None

    async def get(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> ScopeVersion | None:
        model = await self._session.scalar(
            select(ScopeVersionModel)
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
        return _from_model(model) if model is not None else None

    async def list(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        limit: int,
        before_version_no: int | None,
    ) -> tuple[ScopeVersion, ...] | None:
        exists = await self._session.scalar(
            select(ProjectModel.id).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        if exists is None:
            return None
        filters = [
            ScopeVersionModel.account_id == account_id,
            ScopeVersionModel.project_id == project_id,
        ]
        if before_version_no is not None:
            filters.append(ScopeVersionModel.version_no < before_version_no)
        models = (
            await self._session.scalars(
                select(ScopeVersionModel)
                .where(*filters)
                .order_by(ScopeVersionModel.version_no.desc())
                .limit(limit)
            )
        ).all()
        return tuple(_from_model(model) for model in models)


class SqlAlchemyScopeVersionUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeVersionRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeVersionRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyScopeVersionUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeVersionRepository(self._session)
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
            raise ScopeVersionRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyScopeVersionUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeVersionUnitOfWork:
        return SqlAlchemyScopeVersionUnitOfWork(self._session_factory)


def _from_model(model: ScopeVersionModel) -> ScopeVersion:
    try:
        return ScopeVersion(
            id=model.id,
            account_id=model.account_id,
            project_id=model.project_id,
            version_no=model.version_no,
            context_version=model.context_version,
            status=cast(ScopeVersionStatus, model.status),
            snapshot_data=model.snapshot_data,
            snapshot_hash=model.snapshot_hash,
            created_by=model.created_by,
            created_at=model.created_at,
        )
    except ScopeVersionValidationError:
        raise ScopeVersionRepositoryError from None


def _draft_from_model(model: ScopeDraftModel) -> ScopeDraft:
    return ScopeDraft(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        content=model.content,
        updated_by_type=cast(ScopeDraftActorType, model.updated_by_type),
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
