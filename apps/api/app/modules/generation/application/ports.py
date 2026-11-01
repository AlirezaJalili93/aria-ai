from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.generation.domain.artifact import (
    ArtifactAllocation,
    ArtifactTriggerType,
)
from app.modules.jobs.domain.job import Job, NewJob, NewOutboxEvent, OutboxEvent


class ArtifactRepositoryError(Exception):
    """A declared Artifact persistence failure."""


class ArtifactScopeNotEligible(Exception):
    """The exact tenant-scoped Scope Version is not approved."""


class ArtifactAllocationConflict(Exception):
    """An allocation identity conflicts with persisted Artifact state."""


class ArtifactFinalizationConflict(Exception):
    """The same Artifact Version cannot be finalized with the supplied Manifest."""


class ArtifactManifestInvalid(Exception):
    """The private immutable Manifest is absent, incomplete or hash-invalid."""


@dataclass(frozen=True, slots=True, kw_only=True)
class AllocateArtifactCommand:
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    created_by: UUID
    trigger_type: ArtifactTriggerType
    job: NewJob
    outbox_event: NewOutboxEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactAllocationResult:
    allocation: ArtifactAllocation
    job: Job
    outbox_event: OutboxEvent
    replayed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class FinalizeArtifactVersionCommand:
    account_id: UUID
    project_id: UUID
    artifact_version_id: UUID
    generation_job_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifiedArtifactManifest:
    storage_ref: str
    artifact_hash: str


class PrivateArtifactManifestResolver(Protocol):
    async def resolve_verified(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        artifact_version_id: UUID,
    ) -> VerifiedArtifactManifest | None: ...


class ArtifactFoundationRepository(Protocol):
    async def allocate(
        self, command: AllocateArtifactCommand
    ) -> ArtifactAllocationResult: ...

    async def finalize(
        self,
        command: FinalizeArtifactVersionCommand,
        manifest: VerifiedArtifactManifest,
    ) -> ArtifactAllocation: ...


class ArtifactFoundationUnitOfWork(Protocol):
    @property
    def repository(self) -> ArtifactFoundationRepository: ...

    async def __aenter__(self) -> ArtifactFoundationUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ArtifactFoundationUnitOfWorkFactory(Protocol):
    def __call__(self) -> ArtifactFoundationUnitOfWork: ...
