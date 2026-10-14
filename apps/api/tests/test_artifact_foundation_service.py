from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest

from app.modules.generation.application.ports import (
    AllocateArtifactCommand,
    ArtifactAllocationResult,
    ArtifactManifestInvalid,
    FinalizeArtifactVersionCommand,
    VerifiedArtifactManifest,
)
from app.modules.generation.application.service import ArtifactFoundationService
from app.modules.generation.domain.artifact import Artifact, ArtifactAllocation, ArtifactVersion


def _allocation() -> ArtifactAllocation:
    now = datetime.now(UTC)
    account_id, project_id, artifact_id, version_id, job_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    return ArtifactAllocation(
        artifact=Artifact(
            id=artifact_id,
            account_id=account_id,
            project_id=project_id,
            artifact_type="website",
            current_version_id=version_id,
            status="ready",
            created_at=now,
            updated_at=now,
        ),
        version=ArtifactVersion(
            id=version_id,
            account_id=account_id,
            project_id=project_id,
            artifact_id=artifact_id,
            scope_version_id=uuid4(),
            version_no=1,
            parent_version_id=None,
            storage_ref="private manifest reference",
            schema_name="generation_ast_schema",
            schema_version="v1",
            artifact_hash="sha256:" + "b" * 64,
            trigger_type="initial",
            status="ready",
            created_by=uuid4(),
            generation_job_id=job_id,
            created_at=now,
        ),
    )


class FakeRepository:
    def __init__(self, allocation: ArtifactAllocation) -> None:
        self.allocation = allocation
        self.finalized: list[FinalizeArtifactVersionCommand] = []

    async def allocate(self, command: AllocateArtifactCommand) -> ArtifactAllocationResult:
        del command
        raise AssertionError("not used")

    async def finalize(
        self,
        command: FinalizeArtifactVersionCommand,
        manifest: VerifiedArtifactManifest,
    ) -> ArtifactAllocation:
        assert manifest.storage_ref == "private manifest reference"
        assert manifest.artifact_hash == "sha256:" + "b" * 64
        self.finalized.append(command)
        return self.allocation


class FakeUnitOfWork:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.committed = True


class FakeFactory:
    def __init__(self, unit_of_work: FakeUnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def __call__(self) -> FakeUnitOfWork:
        return self.unit_of_work


class FakeVerifier:
    def __init__(self, valid: bool) -> None:
        self.valid = valid
        self.calls: list[tuple[UUID, str, str]] = []

    async def resolve_verified(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        artifact_version_id: UUID,
    ) -> VerifiedArtifactManifest | None:
        del account_id, project_id
        storage_ref = "private manifest reference"
        artifact_hash = "sha256:" + "b" * 64
        self.calls.append((artifact_version_id, storage_ref, artifact_hash))
        if not self.valid:
            return None
        return VerifiedArtifactManifest(
            storage_ref=storage_ref,
            artifact_hash=artifact_hash,
        )


def test_invalid_manifest_fails_before_database_finalization() -> None:
    allocation = _allocation()
    repository = FakeRepository(allocation)
    unit_of_work = FakeUnitOfWork(repository)
    verifier = FakeVerifier(False)
    service = ArtifactFoundationService(FakeFactory(unit_of_work), verifier)  # type: ignore[arg-type]
    command = FinalizeArtifactVersionCommand(
        account_id=allocation.artifact.account_id,
        project_id=allocation.artifact.project_id,
        artifact_version_id=allocation.version.id,
        generation_job_id=allocation.version.generation_job_id,
    )
    with pytest.raises(ArtifactManifestInvalid):
        asyncio.run(service.finalize(command))
    assert repository.finalized == []
    assert unit_of_work.committed is False


def test_verified_manifest_uses_atomic_finalization_port_once() -> None:
    allocation = _allocation()
    repository = FakeRepository(allocation)
    unit_of_work = FakeUnitOfWork(repository)
    verifier = FakeVerifier(True)
    service = ArtifactFoundationService(FakeFactory(unit_of_work), verifier)  # type: ignore[arg-type]
    command = FinalizeArtifactVersionCommand(
        account_id=allocation.artifact.account_id,
        project_id=allocation.artifact.project_id,
        artifact_version_id=allocation.version.id,
        generation_job_id=allocation.version.generation_job_id,
    )
    assert asyncio.run(service.finalize(command)) == allocation
    assert repository.finalized == [command]
    assert unit_of_work.committed is True
