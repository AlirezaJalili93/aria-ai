from __future__ import annotations

from types import TracebackType
from typing import cast
from uuid import UUID

from aria_backend_application.scope_generation import ScopeDraftAlreadyExistsError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.identity.infrastructure import models as identity_models
from app.modules.jobs.application.ports import JobRepository, OutboxRepository
from app.modules.jobs.infrastructure.repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.modules.projects.infrastructure import models as project_models
from app.modules.scope.application.generation_jobs import (
    ScopeGenerationActiveJobConflict,
    ScopeGenerationContextRequired,
    ScopeGenerationInputRevision,
    ScopeGenerationJobUnitOfWork,
    ScopeGenerationPreflight,
    ScopeGenerationSchedulingError,
)
from app.modules.scope.domain.readiness import (
    ScopeReadinessGap,
    ScopeReadinessGapSeverity,
    ScopeReadinessGapStatus,
    ScopeReadinessPolicy,
)

_ACTIVE_JOB_CONSTRAINT = "uq_jobs_active_scope_generation_revision"

del identity_models
del project_models


class SqlAlchemyScopeGenerationPreflightReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve_exact(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> ScopeGenerationPreflight | None:
        try:
            async with self._session_factory() as session:
                current_version = await session.scalar(
                    text(
                        "SELECT current_context_version FROM public.projects "
                        "WHERE id=:project_id AND account_id=:account_id AND deleted_at IS NULL"
                    ),
                    {"account_id": account_id, "project_id": project_id},
                )
                if current_version != context_version or context_version < 1:
                    return None
                values = {
                    "account_id": account_id,
                    "project_id": project_id,
                    "context_version": context_version,
                }
                context_rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT id, updated_at FROM public.context_items "
                                "WHERE account_id=:account_id AND project_id=:project_id "
                                "AND context_version=:context_version "
                                "AND status IN ('proposed','confirmed') ORDER BY id"
                            ),
                            values,
                        )
                    )
                    .mappings()
                    .all()
                )
                requirement_rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT id, updated_at FROM public.requirements "
                                "WHERE account_id=:account_id AND project_id=:project_id "
                                "AND context_version=:context_version "
                                "AND status IN ('draft','confirmed') ORDER BY id"
                            ),
                            values,
                        )
                    )
                    .mappings()
                    .all()
                )
                gap_rows = (
                    (
                        await session.execute(
                            text(
                                "SELECT id, updated_at, status, severity FROM public.gaps "
                                "WHERE account_id=:account_id AND project_id=:project_id "
                                "AND context_version=:context_version ORDER BY id"
                            ),
                            values,
                        )
                    )
                    .mappings()
                    .all()
                )
                draft_id = await session.scalar(
                    text(
                        "SELECT id FROM public.scope_drafts WHERE account_id=:account_id "
                        "AND project_id=:project_id AND context_version=:context_version"
                    ),
                    values,
                )
            readiness = ScopeReadinessPolicy().evaluate(
                account_id=account_id,
                project_id=project_id,
                context_version=context_version,
                gaps=(
                    ScopeReadinessGap(
                        id=row["id"],
                        account_id=account_id,
                        project_id=project_id,
                        context_version=context_version,
                        status=cast(ScopeReadinessGapStatus, row["status"]),
                        severity=cast(ScopeReadinessGapSeverity, row["severity"]),
                    )
                    for row in gap_rows
                ),
            )
            return ScopeGenerationPreflight(
                context_item_revisions=tuple(
                    ScopeGenerationInputRevision(row["id"], row["updated_at"])
                    for row in context_rows
                ),
                requirement_revisions=tuple(
                    ScopeGenerationInputRevision(row["id"], row["updated_at"])
                    for row in requirement_rows
                ),
                gap_revisions=tuple(
                    ScopeGenerationInputRevision(row["id"], row["updated_at"]) for row in gap_rows
                ),
                ready_for_share=readiness.ready_for_share,
                draft_exists=draft_id is not None,
            )
        except SQLAlchemyError:
            raise ScopeGenerationSchedulingError("scope_preflight_unavailable") from None


class SqlAlchemyScopeGenerationJobUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._jobs: SqlAlchemyJobRepository | None = None
        self._outbox: SqlAlchemyOutboxRepository | None = None
        self._committed = False

    @property
    def jobs(self) -> JobRepository:
        if self._jobs is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._jobs

    @property
    def outbox(self) -> OutboxRepository:
        if self._outbox is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._outbox

    async def __aenter__(self) -> SqlAlchemyScopeGenerationJobUnitOfWork:
        self._session = self._session_factory()
        self._jobs = SqlAlchemyJobRepository(self._session)
        self._outbox = SqlAlchemyOutboxRepository(self._session)
        return self

    async def verify_draft_absent(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        current_version = await self._session.scalar(
            text(
                "SELECT current_context_version FROM public.projects "
                "WHERE id=:project_id AND account_id=:account_id AND deleted_at IS NULL "
                "FOR UPDATE"
            ),
            {"account_id": account_id, "project_id": project_id},
        )
        if current_version != context_version:
            raise ScopeGenerationContextRequired
        draft_id = await self._session.scalar(
            text(
                "SELECT id FROM public.scope_drafts WHERE account_id=:account_id "
                "AND project_id=:project_id AND context_version=:context_version"
            ),
            {
                "account_id": account_id,
                "project_id": project_id,
                "context_version": context_version,
            },
        )
        if draft_id is not None:
            raise ScopeDraftAlreadyExistsError

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
        if isinstance(exc, IntegrityError) and _ACTIVE_JOB_CONSTRAINT in str(exc.orig):
            raise ScopeGenerationActiveJobConflict from None
        if isinstance(exc, SQLAlchemyError):
            raise ScopeGenerationSchedulingError("scope_schedule_failed") from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        try:
            await self._session.commit()
        except IntegrityError as error:
            if _ACTIVE_JOB_CONSTRAINT in str(error.orig):
                raise ScopeGenerationActiveJobConflict from None
            raise ScopeGenerationSchedulingError("scope_schedule_failed") from None
        except SQLAlchemyError:
            raise ScopeGenerationSchedulingError("scope_schedule_failed") from None
        self._committed = True


class SqlAlchemyScopeGenerationJobUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ScopeGenerationJobUnitOfWork:
        return SqlAlchemyScopeGenerationJobUnitOfWork(self._session_factory)
