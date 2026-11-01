from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.generation.application.ports import (
    AllocateArtifactCommand,
    ArtifactAllocationConflict,
    ArtifactAllocationResult,
    ArtifactFinalizationConflict,
    ArtifactFoundationRepository,
    ArtifactFoundationUnitOfWork,
    ArtifactRepositoryError,
    ArtifactScopeNotEligible,
    FinalizeArtifactVersionCommand,
    VerifiedArtifactManifest,
)
from app.modules.generation.domain.artifact import (
    ARTIFACT_SCHEMA_NAME,
    ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_TYPE,
    Artifact,
    ArtifactAllocation,
    ArtifactStatus,
    ArtifactTriggerType,
    ArtifactVersion,
    ArtifactVersionStatus,
)
from app.modules.generation.infrastructure.models import (
    ArtifactModel,
    ArtifactVersionModel,
)
from app.modules.jobs.infrastructure.models import JobModel
from app.modules.jobs.infrastructure.repository import (
    SqlAlchemyJobRepository,
    SqlAlchemyOutboxRepository,
)
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.scope.infrastructure.models import ScopeVersionModel


class SqlAlchemyArtifactFoundationRepository(ArtifactFoundationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._jobs = SqlAlchemyJobRepository(session)
        self._outbox = SqlAlchemyOutboxRepository(session)

    async def allocate(
        self, command: AllocateArtifactCommand
    ) -> ArtifactAllocationResult:
        self._validate_command_boundary(command)
        existing_version = await self._session.scalar(
            select(ArtifactVersionModel)
            .where(
                ArtifactVersionModel.generation_job_id == command.job.id,
                ArtifactVersionModel.account_id == command.account_id,
                ArtifactVersionModel.project_id == command.project_id,
            )
            .with_for_update()
        )
        if existing_version is not None:
            return await self._replay(command, existing_version)

        project = await self._session.scalar(
            select(ProjectModel)
            .where(
                ProjectModel.id == command.project_id,
                ProjectModel.account_id == command.account_id,
                ProjectModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if project is None:
            raise ArtifactScopeNotEligible
        scope = await self._session.scalar(
            select(ScopeVersionModel)
            .where(
                ScopeVersionModel.id == command.scope_version_id,
                ScopeVersionModel.account_id == command.account_id,
                ScopeVersionModel.project_id == command.project_id,
                ScopeVersionModel.status == "approved",
            )
            .with_for_update()
        )
        if scope is None:
            raise ArtifactScopeNotEligible

        artifact = await self._session.scalar(
            select(ArtifactModel)
            .where(
                ArtifactModel.account_id == command.account_id,
                ArtifactModel.project_id == command.project_id,
                ArtifactModel.artifact_type == ARTIFACT_TYPE,
            )
            .with_for_update()
        )
        if artifact is None:
            if command.trigger_type != "initial":
                raise ArtifactAllocationConflict
            artifact = ArtifactModel(
                id=command.artifact_id,
                account_id=command.account_id,
                project_id=command.project_id,
                artifact_type=ARTIFACT_TYPE,
                status="draft",
            )
            self._session.add(artifact)
            await self._session.flush()
            version_no = 1
            parent_version_id = None
        else:
            if artifact.id != command.artifact_id or command.trigger_type == "initial":
                raise ArtifactAllocationConflict
            latest_number = await self._session.scalar(
                select(func.max(ArtifactVersionModel.version_no)).where(
                    ArtifactVersionModel.artifact_id == artifact.id
                )
            )
            version_no = int(latest_number or 0) + 1
            parent_version_id = artifact.current_version_id
            if parent_version_id is None:
                raise ArtifactAllocationConflict

        version = ArtifactVersionModel(
            id=command.artifact_version_id,
            account_id=command.account_id,
            project_id=command.project_id,
            artifact_id=artifact.id,
            scope_version_id=command.scope_version_id,
            version_no=version_no,
            parent_version_id=parent_version_id,
            schema_name=ARTIFACT_SCHEMA_NAME,
            schema_version=ARTIFACT_SCHEMA_VERSION,
            trigger_type=command.trigger_type,
            status="queued",
            created_by=command.created_by,
            generation_job_id=command.job.id,
        )
        try:
            persisted_job = await self._jobs.add(command.job)
            self._session.add(version)
            await self._session.flush()
            persisted_event = await self._outbox.add(command.outbox_event)
            await self._session.refresh(artifact)
            await self._session.refresh(version)
        except IntegrityError as exc:
            raise ArtifactAllocationConflict from exc
        return ArtifactAllocationResult(
            allocation=ArtifactAllocation(
                artifact=_artifact_from_model(artifact),
                version=_version_from_model(version),
            ),
            job=persisted_job,
            outbox_event=persisted_event,
            replayed=False,
        )

    async def finalize(
        self,
        command: FinalizeArtifactVersionCommand,
        manifest: VerifiedArtifactManifest,
    ) -> ArtifactAllocation:
        version = await self._session.scalar(
            select(ArtifactVersionModel)
            .where(
                ArtifactVersionModel.id == command.artifact_version_id,
                ArtifactVersionModel.account_id == command.account_id,
                ArtifactVersionModel.project_id == command.project_id,
                ArtifactVersionModel.generation_job_id == command.generation_job_id,
            )
            .with_for_update()
        )
        if version is None:
            raise ArtifactFinalizationConflict
        artifact = await self._session.scalar(
            select(ArtifactModel)
            .where(
                ArtifactModel.id == version.artifact_id,
                ArtifactModel.account_id == command.account_id,
                ArtifactModel.project_id == command.project_id,
            )
            .with_for_update()
        )
        job = await self._session.scalar(
            select(JobModel)
            .where(
                JobModel.id == command.generation_job_id,
                JobModel.account_id == command.account_id,
                JobModel.project_id == command.project_id,
            )
            .with_for_update()
        )
        if artifact is None or job is None:
            raise ArtifactFinalizationConflict
        if version.status == "ready":
            if (
                version.storage_ref != manifest.storage_ref
                or version.artifact_hash != manifest.artifact_hash
                or artifact.current_version_id != version.id
                or job.status != "succeeded"
            ):
                raise ArtifactFinalizationConflict
            return ArtifactAllocation(
                artifact=_artifact_from_model(artifact),
                version=_version_from_model(version),
            )
        if version.status not in {"queued", "generating", "validating"}:
            raise ArtifactFinalizationConflict
        if job.status not in {"queued", "running"}:
            raise ArtifactFinalizationConflict

        version.storage_ref = manifest.storage_ref
        version.artifact_hash = manifest.artifact_hash
        version.status = "ready"
        await self._session.flush()

        artifact.current_version_id = version.id
        artifact.status = "ready"
        job.status = "succeeded"
        job.finished_at = datetime.now(UTC)
        job.error_code = None
        job.error_detail = None
        await self._session.flush()
        await self._session.refresh(artifact)
        await self._session.refresh(version)
        return ArtifactAllocation(
            artifact=_artifact_from_model(artifact),
            version=_version_from_model(version),
        )

    async def _replay(
        self,
        command: AllocateArtifactCommand,
        version: ArtifactVersionModel,
    ) -> ArtifactAllocationResult:
        if (
            version.id != command.artifact_version_id
            or version.artifact_id != command.artifact_id
            or version.scope_version_id != command.scope_version_id
            or version.created_by != command.created_by
            or version.trigger_type != command.trigger_type
        ):
            raise ArtifactAllocationConflict
        artifact = await self._session.scalar(
            select(ArtifactModel).where(
                ArtifactModel.id == version.artifact_id,
                ArtifactModel.account_id == command.account_id,
                ArtifactModel.project_id == command.project_id,
            )
        )
        job = await self._jobs.get(command.job.id)
        event = await self._outbox.get(command.outbox_event.id)
        if artifact is None or job is None or event is None:
            raise ArtifactAllocationConflict
        return ArtifactAllocationResult(
            allocation=ArtifactAllocation(
                artifact=_artifact_from_model(artifact),
                version=_version_from_model(version),
            ),
            job=job,
            outbox_event=event,
            replayed=True,
        )

    @staticmethod
    def _validate_command_boundary(command: AllocateArtifactCommand) -> None:
        if (
            command.job.account_id != command.account_id
            or command.job.project_id != command.project_id
            or command.job.job_type != "artifact_generation"
            or command.job.status != "queued"
            or command.job.payload_ref
            != {
                "artifact_version_id": str(command.artifact_version_id),
                "scope_version_id": str(command.scope_version_id),
            }
            or command.outbox_event.account_id != command.account_id
            or command.outbox_event.aggregate_type != "artifact_version"
            or command.outbox_event.aggregate_id != command.artifact_version_id
            or command.outbox_event.event_type
            != "artifact.generation_requested.v1"
            or command.outbox_event.delivery_channel != "job_queue"
            or command.outbox_event.payload
            != {
                "jobId": str(command.job.id),
                "taskType": "artifact_generation",
                "payloadVersion": "1",
            }
            or command.outbox_event.status != "pending"
        ):
            raise ArtifactAllocationConflict


class SqlAlchemyArtifactFoundationUnitOfWork(ArtifactFoundationUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._repository: SqlAlchemyArtifactFoundationRepository | None = None
        self._committed = False

    @property
    def repository(self) -> ArtifactFoundationRepository:
        if self._repository is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        return self._repository

    async def __aenter__(self) -> SqlAlchemyArtifactFoundationUnitOfWork:
        self._session = self._session_factory()
        self._repository = SqlAlchemyArtifactFoundationRepository(self._session)
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
            raise ArtifactRepositoryError from None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Unit of Work has not entered a transaction")
        await self._session.commit()
        self._committed = True


class SqlAlchemyArtifactFoundationUnitOfWorkFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> ArtifactFoundationUnitOfWork:
        return SqlAlchemyArtifactFoundationUnitOfWork(self._session_factory)


def _artifact_from_model(model: ArtifactModel) -> Artifact:
    return Artifact(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        artifact_type=model.artifact_type,
        current_version_id=model.current_version_id,
        status=cast(ArtifactStatus, model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _version_from_model(model: ArtifactVersionModel) -> ArtifactVersion:
    return ArtifactVersion(
        id=model.id,
        account_id=model.account_id,
        project_id=model.project_id,
        artifact_id=model.artifact_id,
        scope_version_id=model.scope_version_id,
        version_no=model.version_no,
        parent_version_id=model.parent_version_id,
        storage_ref=model.storage_ref,
        schema_name=model.schema_name,
        schema_version=model.schema_version,
        artifact_hash=model.artifact_hash,
        trigger_type=cast(ArtifactTriggerType, model.trigger_type),
        status=cast(ArtifactVersionStatus, model.status),
        created_by=model.created_by,
        generation_job_id=model.generation_job_id,
        created_at=model.created_at,
    )
