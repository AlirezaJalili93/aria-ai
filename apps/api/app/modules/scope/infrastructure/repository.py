from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.context.infrastructure.models import ContextItemModel
from app.modules.gaps.infrastructure.models import GapModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.requirements.infrastructure.models import RequirementModel
from app.modules.scope.application.ports import (
    ScopeDraftEditTarget,
    ScopeDraftHistorical,
    ScopeDraftNotFound,
    ScopeDraftRepository,
    ScopeDraftRepositoryError,
    ScopeDraftUnitOfWork,
    ScopeDraftVersionConflict,
)
from app.modules.scope.domain.scope_draft import (
    NewScopeDraft,
    ScopeDraft,
    ScopeDraftActorType,
    ScopeDraftValidationError,
    validate_scope_content,
)
from app.modules.scope.infrastructure.models import ScopeDraftModel


class SqlAlchemyScopeDraftRepository(ScopeDraftRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _model(
        self, *, account_id: UUID, project_id: UUID, draft_id: UUID
    ) -> ScopeDraftModel | None:
        return (
            await self._session.scalars(
                select(ScopeDraftModel).where(
                    ScopeDraftModel.id == draft_id,
                    ScopeDraftModel.account_id == account_id,
                    ScopeDraftModel.project_id == project_id,
                )
            )
        ).one_or_none()

    async def get_by_id(
        self, *, account_id: UUID, project_id: UUID, draft_id: UUID
    ) -> ScopeDraft | None:
        model = await self._model(account_id=account_id, project_id=project_id, draft_id=draft_id)
        return _from_model(model) if model is not None else None

    async def get_by_context_version(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> ScopeDraft | None:
        model = (
            await self._session.scalars(
                select(ScopeDraftModel).where(
                    ScopeDraftModel.account_id == account_id,
                    ScopeDraftModel.project_id == project_id,
                    ScopeDraftModel.context_version == context_version,
                )
            )
        ).one_or_none()
        return _from_model(model) if model is not None else None

    async def get_current(self, *, account_id: UUID, project_id: UUID) -> ScopeDraft | None:
        model = (
            await self._session.scalars(
                select(ScopeDraftModel)
                .join(
                    ProjectModel,
                    (ProjectModel.id == ScopeDraftModel.project_id)
                    & (ProjectModel.account_id == ScopeDraftModel.account_id),
                )
                .where(
                    ScopeDraftModel.account_id == account_id,
                    ScopeDraftModel.project_id == project_id,
                    ScopeDraftModel.context_version == ProjectModel.current_context_version,
                    ProjectModel.current_context_version >= 1,
                    ProjectModel.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        return _from_model(model) if model is not None else None

    async def get_edit_target(
        self, *, account_id: UUID, project_id: UUID
    ) -> ScopeDraftEditTarget | None:
        project = (
            await self._session.scalars(
                select(ProjectModel)
                .where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).one_or_none()
        if project is None:
            return None
        model = (
            await self._session.scalars(
                select(ScopeDraftModel)
                .where(
                    ScopeDraftModel.account_id == account_id,
                    ScopeDraftModel.project_id == project_id,
                )
                .order_by(ScopeDraftModel.context_version.desc())
                .limit(1)
                .with_for_update()
            )
        ).one_or_none()
        return ScopeDraftEditTarget(
            project_current_context_version=project.current_context_version,
            draft=_from_model(model) if model is not None else None,
        )

    async def add(self, draft: NewScopeDraft) -> ScopeDraft:
        project = (
            await self._session.scalars(
                select(ProjectModel)
                .where(
                    ProjectModel.id == draft.project_id,
                    ProjectModel.account_id == draft.account_id,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).one_or_none()
        if project is None:
            raise ScopeDraftNotFound
        if draft.context_version > project.current_context_version:
            raise ScopeDraftValidationError("Scope Draft context version is ahead of the Project")
        content = validate_scope_content(draft.content)
        await self._validate_trace_targets(
            account_id=draft.account_id,
            project_id=draft.project_id,
            context_version=draft.context_version,
            content=content,
        )
        model = ScopeDraftModel(
            id=draft.id,
            account_id=draft.account_id,
            project_id=draft.project_id,
            context_version=draft.context_version,
            content=content,
            updated_by_type=draft.updated_by_type,
            updated_by=draft.updated_by,
        )
        self._session.add(model)
        try:
            await self._session.flush()
            await self._session.refresh(model)
        except IntegrityError as exc:
            raise ScopeDraftRepositoryError("Scope Draft uniqueness or constraint failure") from exc
        return _from_model(model)

    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        draft_id: UUID,
        expected_updated_at: datetime,
        content: dict[str, object],
        updated_by_type: str,
        updated_by: UUID | None,
    ) -> ScopeDraft:
        model = await self._model(account_id=account_id, project_id=project_id, draft_id=draft_id)
        if model is None:
            raise ScopeDraftNotFound
        project = (
            await self._session.scalars(
                select(ProjectModel)
                .where(
                    ProjectModel.id == project_id,
                    ProjectModel.account_id == account_id,
                    ProjectModel.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).one_or_none()
        if project is None:
            raise ScopeDraftNotFound
        if model.context_version < project.current_context_version:
            raise ScopeDraftHistorical
        if model.updated_at != expected_updated_at:
            raise ScopeDraftVersionConflict
        validated_content = validate_scope_content(content)
        await self._validate_trace_targets(
            account_id=account_id,
            project_id=project_id,
            context_version=model.context_version,
            content=validated_content,
        )
        model.content = validated_content
        model.updated_by_type = updated_by_type
        model.updated_by = updated_by
        await self._session.flush()
        await self._session.refresh(model)
        return _from_model(model)

    async def _validate_trace_targets(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        content: dict[str, object],
    ) -> None:
        sections = {
            item["section_id"]: item for item in cast(list[dict[str, Any]], content["sections"])
        }
        trace_ids = {
            key: {value for section in sections.values() for value in section["trace"][key]}
            for key in ("context_item_ids", "requirement_ids", "gap_ids")
        }
        if trace_ids["context_item_ids"]:
            found = set(
                await self._session.scalars(
                    select(ContextItemModel.id).where(
                        ContextItemModel.id.in_(
                            tuple(UUID(value) for value in trace_ids["context_item_ids"])
                        ),
                        ContextItemModel.account_id == account_id,
                        ContextItemModel.project_id == project_id,
                        ContextItemModel.context_version == context_version,
                    )
                )
            )
            if found != {UUID(value) for value in trace_ids["context_item_ids"]}:
                raise ScopeDraftValidationError(
                    "Scope Context trace is outside the tenant snapshot"
                )
        if trace_ids["requirement_ids"]:
            expected = {UUID(value) for value in trace_ids["requirement_ids"]}
            found = set(
                await self._session.scalars(
                    select(RequirementModel.id).where(
                        RequirementModel.id.in_(tuple(expected)),
                        RequirementModel.account_id == account_id,
                        RequirementModel.project_id == project_id,
                        RequirementModel.context_version == context_version,
                        RequirementModel.status.in_(("draft", "confirmed")),
                    )
                )
            )
            if found != expected:
                raise ScopeDraftValidationError("Scope Requirement trace is invalid")
        if trace_ids["gap_ids"]:
            expected = {UUID(value) for value in trace_ids["gap_ids"]}
            found = set(
                await self._session.scalars(
                    select(GapModel.id).where(
                        GapModel.id.in_(tuple(expected)),
                        GapModel.account_id == account_id,
                        GapModel.project_id == project_id,
                        GapModel.context_version == context_version,
                        GapModel.status.in_(("open", "resolved", "dismissed")),
                    )
                )
            )
            if found != expected:
                raise ScopeDraftValidationError("Scope Gap trace is invalid")
            resolved_ids = {UUID(value) for value in sections["resolved_gaps"]["trace"]["gap_ids"]}
            if resolved_ids:
                unresolved = set(
                    await self._session.scalars(
                        select(GapModel.id).where(
                            GapModel.id.in_(tuple(resolved_ids)),
                            GapModel.account_id == account_id,
                            GapModel.project_id == project_id,
                            GapModel.context_version == context_version,
                            GapModel.status != "resolved",
                        )
                    )
                )
                if unresolved:
                    raise ScopeDraftValidationError("resolved_gaps cannot trace an open Gap")


class SqlAlchemyScopeDraftUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyScopeDraftRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ScopeDraftRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyScopeDraftUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyScopeDraftRepository(self._session)
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
            raise ScopeDraftRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyScopeDraftUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeDraftUnitOfWork:
        return SqlAlchemyScopeDraftUnitOfWork(self._session_factory)


def _from_model(model: ScopeDraftModel) -> ScopeDraft:
    return ScopeDraft(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        context_version=model.context_version,
        content=cast(dict[str, object], model.content),
        updated_by_type=cast(ScopeDraftActorType, model.updated_by_type),
        updated_by=model.updated_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
