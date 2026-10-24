from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.gaps.infrastructure.models import GapModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.scope.application.scope_revision_ports import (
    ScopeRevisionRepository,
    ScopeRevisionRepositoryError,
    ScopeRevisionReservation,
    ScopeRevisionTarget,
    ScopeRevisionUnitOfWork,
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
from app.modules.sharing.infrastructure.models import ScopeChangeRequestModel
from app.shared.idempotency import IdempotencyRepositoryError


class SqlAlchemyScopeRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._idempotency = SqlAlchemyIdempotencyRepository(session)

    @staticmethod
    def _route_key(project_id: UUID, target_version_no: int) -> str:
        return (
            f"POST:/api/v1/projects/{project_id}/scope/versions/"
            f"{target_version_no}/revisions"
        )

    async def lock_visible_target(
        self, *, account_id: UUID, project_id: UUID, version_no: int
    ) -> ScopeVersion | None:
        project = await self._session.scalar(
            select(ProjectModel)
            .where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if project is None:
            return None
        model = await self._session.scalar(
            select(ScopeVersionModel).where(
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
                ScopeVersionModel.version_no == version_no,
            )
        )
        return _version_from_model(model) if model is not None else None

    async def reserve_revision(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        target_version_no: int,
        idempotency_key: str,
        request_hash: str,
        scope_version_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> ScopeRevisionReservation:
        try:
            reservation = await self._idempotency.reserve(
                record_id=scope_version_id,
                account_id=account_id,
                actor_id=actor_id,
                route_key=self._route_key(project_id, target_version_no),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                now=now,
                expires_at=expires_at,
            )
        except IdempotencyRepositoryError:
            raise ScopeRevisionRepositoryError from None
        response: ScopeVersion | None = None
        reserved_id = scope_version_id
        if reservation.response_ref is not None:
            try:
                reserved_id = UUID(str(reservation.response_ref["scope_version_id"]))
            except (KeyError, TypeError, ValueError):
                raise ScopeRevisionRepositoryError from None
            model = await self._session.scalar(
                select(ScopeVersionModel).where(
                    ScopeVersionModel.id == reserved_id,
                    ScopeVersionModel.account_id == account_id,
                    ScopeVersionModel.project_id == project_id,
                )
            )
            if model is None:
                raise ScopeRevisionRepositoryError
            response = _version_from_model(model)
        return ScopeRevisionReservation(
            acquired=reservation.acquired,
            request_hash=reservation.request_hash,
            scope_version_id=reserved_id,
            response=response,
        )

    async def get_revision_target(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        target_version_no: int,
        change_request_id: UUID,
    ) -> ScopeRevisionTarget | None:
        project = await self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.account_id == account_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        if project is None:
            return None
        latest = await self._session.scalar(
            select(ScopeVersionModel)
            .where(
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
            )
            .order_by(ScopeVersionModel.version_no.desc())
            .limit(1)
            .with_for_update()
        )
        target = await self._session.scalar(
            select(ScopeVersionModel)
            .where(
                ScopeVersionModel.account_id == account_id,
                ScopeVersionModel.project_id == project_id,
                ScopeVersionModel.version_no == target_version_no,
            )
            .with_for_update()
        )
        if latest is None or target is None:
            return None
        change_request = await self._session.scalar(
            select(ScopeChangeRequestModel)
            .where(
                ScopeChangeRequestModel.id == change_request_id,
                ScopeChangeRequestModel.account_id == account_id,
                ScopeChangeRequestModel.project_id == project_id,
            )
            .with_for_update()
        )
        if change_request is None:
            return None
        draft = await self._session.scalar(
            select(ScopeDraftModel)
            .where(
                ScopeDraftModel.account_id == account_id,
                ScopeDraftModel.project_id == project_id,
                ScopeDraftModel.context_version == project.current_context_version,
            )
            .with_for_update()
        )
        gaps = (
            await self._session.scalars(
                select(GapModel).where(
                    GapModel.account_id == account_id,
                    GapModel.project_id == project_id,
                    GapModel.context_version == project.current_context_version,
                )
            )
        ).all()
        consumed = (
            await self._session.scalar(
                select(ScopeVersionModel.id).where(
                    ScopeVersionModel.account_id == account_id,
                    ScopeVersionModel.project_id == project_id,
                    ScopeVersionModel.change_request_id == change_request_id,
                )
            )
        ) is not None
        return ScopeRevisionTarget(
            project_current_context_version=project.current_context_version,
            target=_version_from_model(target),
            latest_scope_version_id=latest.id,
            change_request_scope_version_id=change_request.scope_version_id,
            change_request_consumed=consumed,
            draft=_draft_from_model(draft) if draft is not None else None,
            gaps=tuple(
                ScopeReadinessGap(
                    id=model.id,
                    account_id=model.account_id,
                    project_id=model.project_id,
                    context_version=model.context_version,
                    severity=cast(ScopeReadinessGapSeverity, model.severity),
                    status=cast(ScopeReadinessGapStatus, model.status),
                )
                for model in gaps
            ),
        )

    async def add_revision(self, version: NewScopeVersion) -> ScopeVersion:
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
            revision_of_scope_version_id=version.revision_of_scope_version_id,
            change_request_id=version.change_request_id,
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as exc:
            raise ScopeRevisionRepositoryError("Scope Revision constraint failure") from exc
        return _version_from_model(model)

    async def supersede_target(self, *, target_scope_version_id: UUID) -> None:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(ScopeVersionModel)
                .where(
                    ScopeVersionModel.id == target_scope_version_id,
                    ScopeVersionModel.status == "changes_requested",
                )
                .values(status="superseded")
            ),
        )
        if result.rowcount != 1:
            raise ScopeRevisionRepositoryError("Scope Revision target transition failed")
        await self._session.flush()

    async def complete_revision_reservation(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        project_id: UUID,
        target_version_no: int,
        idempotency_key: str,
        request_hash: str,
        version: ScopeVersion,
    ) -> None:
        try:
            await self._idempotency.complete(
                account_id=account_id,
                actor_id=actor_id,
                route_key=self._route_key(project_id, target_version_no),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=201,
                response_ref={"scope_version_id": str(version.id)},
            )
        except IdempotencyRepositoryError:
            raise ScopeRevisionRepositoryError from None


class SqlAlchemyScopeRevisionUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeRevisionRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeRevisionRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyScopeRevisionUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeRevisionRepository(self._session)
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
            raise ScopeRevisionRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except (IntegrityError, SQLAlchemyError) as exc:
            raise ScopeRevisionRepositoryError("Scope Revision commit failed") from exc
        self._committed = True


class SqlAlchemyScopeRevisionUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeRevisionUnitOfWork:
        return SqlAlchemyScopeRevisionUnitOfWork(self._session_factory)


def _version_from_model(model: ScopeVersionModel) -> ScopeVersion:
    try:
        return ScopeVersion(
            id=model.id,
            account_id=model.account_id,
            project_id=model.project_id,
            version_no=model.version_no,
            context_version=model.context_version,
            status=cast(ScopeVersionStatus, model.status),
            snapshot_data=dict(model.snapshot_data),
            snapshot_hash=model.snapshot_hash,
            created_by=model.created_by,
            created_at=model.created_at,
            revision_of_scope_version_id=model.revision_of_scope_version_id,
            change_request_id=model.change_request_id,
        )
    except ScopeVersionValidationError:
        raise ScopeRevisionRepositoryError from None


def _draft_from_model(model: ScopeDraftModel) -> ScopeDraft:
    return ScopeDraft(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        content=dict(model.content),
        updated_by_type=cast(ScopeDraftActorType, model.updated_by_type),
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
