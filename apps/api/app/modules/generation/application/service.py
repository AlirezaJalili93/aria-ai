from __future__ import annotations

from app.modules.generation.application.ports import (
    AllocateArtifactCommand,
    ArtifactAllocationResult,
    ArtifactFoundationUnitOfWorkFactory,
    ArtifactManifestInvalid,
    FinalizeArtifactVersionCommand,
    PrivateArtifactManifestResolver,
)
from app.modules.generation.domain.artifact import (
    ArtifactAllocation,
    validate_manifest_identity,
)


class ArtifactFoundationService:
    """Contract-only Allocation and recovery-safe Manifest finalization boundary."""

    def __init__(
        self,
        unit_of_work_factory: ArtifactFoundationUnitOfWorkFactory,
        manifest_resolver: PrivateArtifactManifestResolver,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._manifest_resolver = manifest_resolver

    async def allocate(
        self, command: AllocateArtifactCommand
    ) -> ArtifactAllocationResult:
        async with self._unit_of_work_factory() as unit_of_work:
            result = await unit_of_work.repository.allocate(command)
            await unit_of_work.commit()
            return result

    async def finalize(
        self, command: FinalizeArtifactVersionCommand
    ) -> ArtifactAllocation:
        manifest = await self._manifest_resolver.resolve_verified(
            account_id=command.account_id,
            project_id=command.project_id,
            artifact_version_id=command.artifact_version_id,
        )
        if manifest is None:
            raise ArtifactManifestInvalid
        validate_manifest_identity(manifest.storage_ref, manifest.artifact_hash)
        async with self._unit_of_work_factory() as unit_of_work:
            result = await unit_of_work.repository.finalize(command, manifest)
            await unit_of_work.commit()
            return result
