from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import cast
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.gaps.application.clarification_ports import (
    ClarificationRepository,
    ClarificationRepositoryError,
    ClarificationUnitOfWork,
    DuplicateClarificationRepositoryError,
)
from app.modules.gaps.domain.clarification import (
    CLARIFICATION_AUTHOR_TYPES,
    CLARIFICATION_CREATOR_TYPES,
    CLARIFICATION_RESOLUTION_TYPES,
    CLARIFICATION_STATUSES,
    Clarification,
    ClarificationAuthorType,
    ClarificationCreatorType,
    ClarificationResolution,
    ClarificationResolutionType,
    ClarificationStatus,
    ClarificationValidationError,
    NewClarification,
    NewClarificationResolution,
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
)
from app.modules.gaps.infrastructure.models import (
    ClarificationModel,
    ClarificationResolutionModel,
    GapModel,
)
from app.modules.projects.infrastructure.models import ProjectModel
from app.shared.idempotency import IdempotencyRepository, IdempotencyRepositoryError


class SqlAlchemyClarificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_gap_for_update(
        self, *, account_id: UUID, project_id: UUID, gap_id: UUID
    ) -> Gap | None:
        model = (
            await self._session.scalars(
                select(GapModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == GapModel.project_id)
                    & (ProjectModel.account_id == GapModel.account_id),
                )
                .where(
                    GapModel.id == gap_id,
                    GapModel.account_id == account_id,
                    GapModel.project_id == project_id,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update(of=GapModel)
            )
        ).one_or_none()
        return _gap_from_model(model) if model is not None else None

    async def add_question(self, question: NewClarification) -> Clarification:
        statement = (
            insert(ClarificationModel)
            .values(
                id=question.id,
                account_id=question.account_id,
                project_id=question.project_id,
                gap_id=question.gap_id,
                question_text=question.question_text,
                status=question.status,
                created_by_type=question.created_by_type,
                created_by=question.created_by,
            )
            .on_conflict_do_nothing(
                index_elements=["account_id", "project_id", "gap_id", "question_text"],
                index_where=ClarificationModel.status == "open",
            )
            .returning(ClarificationModel)
        )
        model = (await self._session.scalars(statement)).one_or_none()
        if model is None:
            raise DuplicateClarificationRepositoryError
        return _clarification_from_model(model)

    async def get_question_by_id(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
    ) -> Clarification | None:
        model = (
            await self._session.scalars(
                select(ClarificationModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == ClarificationModel.project_id)
                    & (ProjectModel.account_id == ClarificationModel.account_id),
                )
                .where(
                    ClarificationModel.id == clarification_id,
                    ClarificationModel.account_id == account_id,
                    ClarificationModel.project_id == project_id,
                    ClarificationModel.gap_id == gap_id,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        return _clarification_from_model(model) if model is not None else None

    async def get_question_for_update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
    ) -> Clarification | None:
        model = (
            await self._session.scalars(
                select(ClarificationModel)
                .where(
                    ClarificationModel.id == clarification_id,
                    ClarificationModel.account_id == account_id,
                    ClarificationModel.project_id == project_id,
                    ClarificationModel.gap_id == gap_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        return _clarification_from_model(model) if model is not None else None

    async def update_question_text(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        expected_updated_at: datetime,
        question_text: str,
    ) -> Clarification | None:
        try:
            model = (
                await self._session.scalars(
                    update(ClarificationModel)
                    .where(
                        ClarificationModel.id == clarification_id,
                        ClarificationModel.account_id == account_id,
                        ClarificationModel.project_id == project_id,
                        ClarificationModel.gap_id == gap_id,
                        ClarificationModel.status == "open",
                        ClarificationModel.updated_at == expected_updated_at,
                    )
                    .values(question_text=question_text)
                    .returning(ClarificationModel)
                )
            ).one_or_none()
        except IntegrityError:
            raise DuplicateClarificationRepositoryError from None
        return _clarification_from_model(model) if model is not None else None

    async def set_question_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        clarification_id: UUID,
        status: ClarificationStatus,
    ) -> Clarification:
        model = (
            await self._session.scalars(
                update(ClarificationModel)
                .where(
                    ClarificationModel.id == clarification_id,
                    ClarificationModel.account_id == account_id,
                    ClarificationModel.project_id == project_id,
                    ClarificationModel.gap_id == gap_id,
                    ClarificationModel.status == "open",
                )
                .values(status=status)
                .returning(ClarificationModel)
            )
        ).one_or_none()
        if model is None:
            raise ClarificationRepositoryError
        return _clarification_from_model(model)

    async def add_resolution(
        self, resolution: NewClarificationResolution
    ) -> ClarificationResolution:
        model = ClarificationResolutionModel(
            id=resolution.id,
            account_id=resolution.account_id,
            project_id=resolution.project_id,
            gap_id=resolution.gap_id,
            clarification_id=resolution.clarification_id,
            resolution_type=resolution.resolution_type,
            answer_text=resolution.answer_text,
            author_type=resolution.author_type,
            author_id=resolution.author_id,
            actor_id=resolution.actor_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _resolution_from_model(model)

    async def get_resolution_by_id(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        resolution_id: UUID,
    ) -> ClarificationResolution | None:
        model = (
            await self._session.scalars(
                select(ClarificationResolutionModel).where(
                    ClarificationResolutionModel.id == resolution_id,
                    ClarificationResolutionModel.account_id == account_id,
                    ClarificationResolutionModel.project_id == project_id,
                    ClarificationResolutionModel.gap_id == gap_id,
                )
            )
        ).one_or_none()
        return _resolution_from_model(model) if model is not None else None

    async def has_open_questions(
        self, *, account_id: UUID, project_id: UUID, gap_id: UUID
    ) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        ClarificationModel.account_id == account_id,
                        ClarificationModel.project_id == project_id,
                        ClarificationModel.gap_id == gap_id,
                        ClarificationModel.status == "open",
                    )
                )
            )
        )

    async def set_gap_status(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        gap_id: UUID,
        expected_updated_at: datetime,
        status: GapStatus,
        resolved_at: datetime | None,
    ) -> Gap | None:
        model = (
            await self._session.scalars(
                update(GapModel)
                .where(
                    GapModel.id == gap_id,
                    GapModel.account_id == account_id,
                    GapModel.project_id == project_id,
                    GapModel.status == "open",
                    GapModel.updated_at == expected_updated_at,
                )
                .values(status=status, resolved_at=resolved_at)
                .returning(GapModel)
            )
        ).one_or_none()
        return _gap_from_model(model) if model is not None else None


class SqlAlchemyClarificationUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyClarificationRepository | None = None
        self._idempotency: SqlAlchemyIdempotencyRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ClarificationRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    @property
    def idempotency(self) -> IdempotencyRepository:
        if self._idempotency is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._idempotency

    async def __aenter__(self) -> SqlAlchemyClarificationUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyClarificationRepository(self._session)
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
        if isinstance(exc, (SQLAlchemyError, IdempotencyRepositoryError)):
            raise ClarificationRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyClarificationUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ClarificationUnitOfWork:
        return SqlAlchemyClarificationUnitOfWork(self._session_factory)


def _clarification_from_model(model: ClarificationModel) -> Clarification:
    if (
        model.status not in CLARIFICATION_STATUSES
        or model.created_by_type not in CLARIFICATION_CREATOR_TYPES
    ):
        raise ClarificationValidationError("Persisted Clarification vocabulary is invalid")
    return Clarification(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        gap_id=model.gap_id,
        question_text=model.question_text,
        status=cast(ClarificationStatus, model.status),
        created_by_type=cast(ClarificationCreatorType, model.created_by_type),
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _resolution_from_model(model: ClarificationResolutionModel) -> ClarificationResolution:
    if (
        model.resolution_type not in CLARIFICATION_RESOLUTION_TYPES
        or model.author_type not in CLARIFICATION_AUTHOR_TYPES
    ):
        raise ClarificationValidationError("Persisted Resolution vocabulary is invalid")
    return ClarificationResolution(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        gap_id=model.gap_id,
        clarification_id=model.clarification_id,
        resolution_type=cast(ClarificationResolutionType, model.resolution_type),
        answer_text=model.answer_text,
        author_type=cast(ClarificationAuthorType, model.author_type),
        author_id=model.author_id,
        actor_id=model.actor_id,
        created_at=model.created_at,
    )


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
        source_refs=tuple(
            GapSourceReference(
                source_id=UUID(str(value["source_id"])),
                source_version_id=UUID(str(value["source_version_id"])),
                start_offset=cast(int | None, value.get("start_offset")),
                end_offset=cast(int | None, value.get("end_offset")),
            )
            for value in model.source_refs
        ),
        created_at=model.created_at,
        updated_at=model.updated_at,
        resolved_at=model.resolved_at,
    )
