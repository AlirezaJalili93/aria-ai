from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from aria_backend_application.preview_delivery import PreviewError, canonical_json

from app.modules.identity.application.tenant_context import TenantContext


@dataclass(frozen=True, slots=True)
class PreviewPublishResult:
    publication_id: UUID
    job_id: UUID
    replayed: bool


@dataclass(frozen=True, slots=True)
class PreviewIssueResult:
    publication_id: UUID
    token: str | None = field(repr=False)
    replayed: bool

    @property
    def token_available(self) -> bool:
        return self.token is not None


class PreviewCommands(Protocol):
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
    ) -> PreviewPublishResult: ...
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
    ) -> PreviewIssueResult: ...
    async def revoke(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        publication_id: UUID,
        key: str,
        request_hash: str,
        now: datetime,
    ) -> None: ...


class PreviewPublicationService:
    def __init__(
        self,
        commands: PreviewCommands,
        *,
        synthetic_sources: frozenset[tuple[UUID, str]],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._commands = commands
        self._synthetic_sources = synthetic_sources
        self._clock = clock

    async def publish(
        self, context: TenantContext, *, project_id: UUID, artifact_version_id: UUID, key: str
    ) -> PreviewPublishResult:
        _authorize(context, key)
        return await self._commands.publish(
            context,
            project_id=project_id,
            artifact_version_id=artifact_version_id,
            key=key,
            request_hash=_fingerprint(context, project_id, "publish", str(artifact_version_id)),
            synthetic_sources=self._synthetic_sources,
            now=self._clock(),
        )

    async def issue(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        publication_id: UUID,
        key: str,
        expires_at: datetime,
    ) -> PreviewIssueResult:
        _authorize(context, key)
        now = self._clock()
        if expires_at.tzinfo is None:
            raise PreviewError("VALIDATION_FAILED")
        # Persisted replay is resolved by the repository before a current-time expiry check.
        return await self._commands.issue(
            context,
            project_id=project_id,
            publication_id=publication_id,
            key=key,
            request_hash=_fingerprint(
                context,
                project_id,
                "issue",
                str(publication_id),
                expires_at.astimezone(UTC).isoformat(),
            ),
            expires_at=expires_at,
            now=now,
        )

    async def revoke(
        self, context: TenantContext, *, project_id: UUID, publication_id: UUID, key: str
    ) -> None:
        _authorize(context, key)
        await self._commands.revoke(
            context,
            project_id=project_id,
            publication_id=publication_id,
            key=key,
            request_hash=_fingerprint(context, project_id, "revoke", str(publication_id)),
            now=self._clock(),
        )


def _authorize(context: TenantContext, key: str) -> None:
    if context.membership_status != "active" or context.role not in {"owner", "admin", "member"}:
        raise PreviewError("RESOURCE_NOT_FOUND")
    if not key.strip():
        raise PreviewError("VALIDATION_FAILED")


def _fingerprint(context: TenantContext, project: UUID, operation: str, *values: str) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "account": str(context.account_id),
                "actor": str(context.subject_id),
                "project": str(project),
                "operation": operation,
                "values": values,
            }
        )
    ).hexdigest()
