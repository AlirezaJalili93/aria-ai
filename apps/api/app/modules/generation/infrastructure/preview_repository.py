from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from aria_backend_application.preview_delivery import (
    DELIVERY_POLICY_VERSION,
    TRANSFORMER_VERSION,
    PreviewError,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.idempotency import SqlAlchemyIdempotencyRepository
from app.modules.generation.application.preview import PreviewIssueResult, PreviewPublishResult
from app.modules.generation.infrastructure.models import ArtifactVersionModel
from app.modules.generation.infrastructure.preview_models import (
    PreviewPublicationModel,
    PreviewRepresentationModel,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.jobs.domain.job import validate_job_status, validate_job_transition
from app.modules.jobs.infrastructure.models import JobModel, OutboxEventModel
from app.modules.projects.infrastructure.models import ProjectModel


class PostgresPreviewCommands:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def publish(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        artifact_version_id: UUID,
        key: str,
        request_hash: str,
        synthetic_sources: frozenset[tuple[UUID, str]],
        now: datetime,
    ) -> PreviewPublishResult:
        try:
            async with self._sessions.begin() as session:
                project = await session.scalar(
                    select(ProjectModel.id)
                    .where(
                        ProjectModel.id == project_id, ProjectModel.account_id == context.account_id
                    )
                    .with_for_update()
                )
                if project is None:
                    raise PreviewError("RESOURCE_NOT_FOUND")
                repo, route, replay = await _reserve(
                    session, context, project_id, "publish", key, request_hash, now
                )
                if replay is not None:
                    publication = await _publication(
                        session, context, project_id, UUID(str(replay["publication_id"]))
                    )
                    return PreviewPublishResult(publication.id, publication.publish_job_id, True)
                source = await session.scalar(
                    select(ArtifactVersionModel).where(
                        ArtifactVersionModel.id == artifact_version_id,
                        ArtifactVersionModel.account_id == context.account_id,
                        ArtifactVersionModel.project_id == project_id,
                    )
                )
                if source is None:
                    raise PreviewError("RESOURCE_NOT_FOUND")
                if source.status != "ready" or source.artifact_hash is None:
                    raise PreviewError("ARTIFACT_VERSION_NOT_READY")
                if (source.id, source.artifact_hash) not in synthetic_sources:
                    raise PreviewError("FEATURE_NOT_ENABLED")
                rep = await session.scalar(
                    select(PreviewRepresentationModel)
                    .where(
                        PreviewRepresentationModel.account_id == context.account_id,
                        PreviewRepresentationModel.artifact_version_id == source.id,
                        PreviewRepresentationModel.transformer_version == TRANSFORMER_VERSION,
                        PreviewRepresentationModel.delivery_policy_version
                        == DELIVERY_POLICY_VERSION,
                    )
                    .with_for_update()
                )
                if rep is None:
                    rep = PreviewRepresentationModel(
                        id=uuid4(),
                        account_id=context.account_id,
                        project_id=project_id,
                        artifact_id=source.artifact_id,
                        artifact_version_id=source.id,
                        source_hash=source.artifact_hash,
                        transformer_version=TRANSFORMER_VERSION,
                        delivery_policy_version=DELIVERY_POLICY_VERSION,
                        status="allocated",
                        created_by=context.subject_id,
                    )
                    session.add(rep)
                    await session.flush()
                active = await session.scalar(
                    select(JobModel.id).where(
                        JobModel.account_id == context.account_id,
                        JobModel.project_id == project_id,
                        JobModel.job_type == "preview_publication",
                        JobModel.status.in_(["queued", "running"]),
                        JobModel.payload_ref["representation_id"].astext == str(rep.id),
                    )
                )
                if active is not None:
                    raise PreviewError("PREVIEW_PUBLICATION_IN_PROGRESS")
                job_id, publication_id = uuid4(), uuid4()
                session.add(
                    JobModel(
                        id=job_id,
                        account_id=context.account_id,
                        project_id=project_id,
                        job_type="preview_publication",
                        status="queued",
                        payload_ref={
                            "publication_id": str(publication_id),
                            "representation_id": str(rep.id),
                            "artifact_version_id": str(source.id),
                        },
                        attempt_count=0,
                        max_attempts=1,
                        idempotency_key=key,
                        correlation_id=uuid4(),
                        available_at=now,
                    )
                )
                await session.flush()
                session.add(
                    PreviewPublicationModel(
                        id=publication_id,
                        account_id=context.account_id,
                        project_id=project_id,
                        artifact_version_id=source.id,
                        representation_id=rep.id,
                        publish_job_id=job_id,
                        status="allocated",
                        created_by=context.subject_id,
                    )
                )
                session.add(
                    OutboxEventModel(
                        id=uuid4(),
                        account_id=context.account_id,
                        aggregate_type="job",
                        aggregate_id=job_id,
                        event_type="preview.publication_requested.v1",
                        delivery_channel="job_queue",
                        payload={
                            "jobId": str(job_id),
                            "taskType": "preview_publication",
                            "payloadVersion": "1",
                        },
                        status="pending",
                        attempt_count=0,
                        available_at=now,
                    )
                )
                await repo.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route,
                    idempotency_key=key,
                    request_hash=request_hash,
                    response_status=202,
                    response_ref={"publication_id": str(publication_id)},
                )
                await session.flush()
                return PreviewPublishResult(publication_id, job_id, False)
        except SQLAlchemyError:
            raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None

    async def issue(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        publication_id: UUID,
        key: str,
        request_hash: str,
        expires_at: datetime,
        now: datetime,
    ) -> PreviewIssueResult:
        try:
            async with self._sessions.begin() as session:
                publication = await _publication(
                    session, context, project_id, publication_id, manage=True
                )
                repo, route, replay = await _reserve(
                    session, context, project_id, "issue", key, request_hash, now
                )
                if replay is not None:
                    if replay != {"publication_id": str(publication_id)}:
                        raise PreviewError("IDEMPOTENCY_CONFLICT")
                    return PreviewIssueResult(publication_id, None, True)
                if publication.status == "revoked":
                    raise PreviewError("PREVIEW_PUBLICATION_REVOKED")
                if publication.status != "ready":
                    raise PreviewError("ARTIFACT_VERSION_NOT_READY")
                if publication.token_hash is not None:
                    raise PreviewError("PREVIEW_CAPABILITY_ALREADY_ISSUED")
                if expires_at <= now:
                    raise PreviewError("VALIDATION_FAILED")
                token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
                publication.token_hash = hashlib.sha256(token.encode()).hexdigest()
                publication.expires_at, publication.issued_at = expires_at, now
                await repo.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route,
                    idempotency_key=key,
                    request_hash=request_hash,
                    response_status=201,
                    response_ref={"publication_id": str(publication_id)},
                )
                await session.flush()
            return PreviewIssueResult(publication_id, token, False)
        except SQLAlchemyError:
            raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None

    async def revoke(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        publication_id: UUID,
        key: str,
        request_hash: str,
        now: datetime,
    ) -> None:
        try:
            async with self._sessions.begin() as session:
                # Match Worker Job -> Publication lock order. Authorization is scoped in
                # the join before locking; no client-supplied Job identity is trusted.
                query = (
                    select(JobModel)
                    .join(
                        PreviewPublicationModel,
                        (PreviewPublicationModel.publish_job_id == JobModel.id)
                        & (PreviewPublicationModel.account_id == JobModel.account_id)
                        & (PreviewPublicationModel.project_id == JobModel.project_id),
                    )
                    .where(
                        PreviewPublicationModel.id == publication_id,
                        PreviewPublicationModel.account_id == context.account_id,
                        PreviewPublicationModel.project_id == project_id,
                        JobModel.account_id == context.account_id,
                        JobModel.project_id == project_id,
                        JobModel.job_type == "preview_publication",
                    )
                )
                if context.role == "member":
                    query = query.where(PreviewPublicationModel.created_by == context.subject_id)
                job = await session.scalar(query.with_for_update(of=JobModel))
                if job is None:
                    raise PreviewError("RESOURCE_NOT_FOUND")
                publication = await _publication(
                    session, context, project_id, publication_id, manage=True
                )
                if job.payload_ref != {
                    "publication_id": str(publication.id),
                    "representation_id": str(publication.representation_id),
                    "artifact_version_id": str(publication.artifact_version_id),
                }:
                    raise PreviewError("RESOURCE_NOT_FOUND")
                repo, route, replay = await _reserve(
                    session, context, project_id, "revoke", key, request_hash, now
                )
                if replay is not None:
                    if replay != {"publication_id": str(publication_id)}:
                        raise PreviewError("IDEMPOTENCY_CONFLICT")
                    return
                if publication.revoked_at is None:
                    if publication.status in {"allocated", "publishing"} and job.status in {
                        "queued",
                        "running",
                    }:
                        validate_job_transition(validate_job_status(job.status), "cancelled")
                        job.status, job.finished_at = "cancelled", now
                    publication.status, publication.revoked_at = "revoked", now
                await repo.complete(
                    account_id=context.account_id,
                    actor_id=context.subject_id,
                    route_key=route,
                    idempotency_key=key,
                    request_hash=request_hash,
                    response_status=204,
                    response_ref={"publication_id": str(publication_id)},
                )
        except SQLAlchemyError:
            raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None


async def _publication(
    session: AsyncSession,
    context: TenantContext,
    project: UUID,
    identity: UUID,
    *,
    manage: bool = False,
) -> PreviewPublicationModel:
    query = select(PreviewPublicationModel).where(
        PreviewPublicationModel.id == identity,
        PreviewPublicationModel.account_id == context.account_id,
        PreviewPublicationModel.project_id == project,
    )
    if manage and context.role == "member":
        query = query.where(PreviewPublicationModel.created_by == context.subject_id)
    value = await session.scalar(query.with_for_update())
    if value is None:
        raise PreviewError("RESOURCE_NOT_FOUND")
    return value


async def _reserve(
    session: AsyncSession,
    context: TenantContext,
    project: UUID,
    operation: str,
    key: str,
    request_hash: str,
    now: datetime,
) -> tuple[SqlAlchemyIdempotencyRepository, str, dict[str, object] | None]:
    repo = SqlAlchemyIdempotencyRepository(session)
    route = f"preview:{project}:{operation}"
    # Inherit the already frozen shared 24-hour policy from ADR-076; no Preview expiry default.
    reservation = await repo.reserve(
        record_id=uuid4(),
        account_id=context.account_id,
        actor_id=context.subject_id,
        route_key=route,
        idempotency_key=key,
        request_hash=request_hash,
        now=now,
        expires_at=now + timedelta(hours=24),
    )
    if reservation.acquired:
        return repo, route, None
    if reservation.request_hash != request_hash or reservation.response_ref is None:
        raise PreviewError("IDEMPOTENCY_CONFLICT")
    return repo, route, reservation.response_ref
