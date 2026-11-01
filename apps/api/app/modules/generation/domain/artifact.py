from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

ArtifactStatus = Literal["draft", "ready", "delivered", "archived"]
ArtifactVersionStatus = Literal["queued", "generating", "validating", "ready", "failed"]
ArtifactTriggerType = Literal["initial", "prompt_edit", "feedback_revision"]

ARTIFACT_STATUSES = frozenset({"draft", "ready", "delivered", "archived"})
ARTIFACT_VERSION_STATUSES = frozenset(
    {"queued", "generating", "validating", "ready", "failed"}
)
ARTIFACT_TRIGGER_TYPES = frozenset({"initial", "prompt_edit", "feedback_revision"})
ARTIFACT_TYPE = "website"
ARTIFACT_SCHEMA_NAME = "generation_ast_schema"
ARTIFACT_SCHEMA_VERSION = "v1"
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ArtifactValidationError(ValueError):
    """An Artifact or immutable ArtifactVersion invariant was violated."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Artifact:
    id: UUID
    account_id: UUID
    project_id: UUID
    artifact_type: str
    current_version_id: UUID | None
    status: ArtifactStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.artifact_type != ARTIFACT_TYPE:
            raise ArtifactValidationError("Unsupported Artifact type")
        validate_artifact_status(self.status)
        if (self.status == "draft") != (self.current_version_id is None):
            raise ArtifactValidationError(
                "Artifact status and current Version must be coherent"
            )
        _require_timezone(self.created_at, "created_at")
        _require_timezone(self.updated_at, "updated_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactVersion:
    id: UUID
    account_id: UUID
    project_id: UUID
    artifact_id: UUID
    scope_version_id: UUID
    version_no: int
    parent_version_id: UUID | None
    storage_ref: str | None
    schema_name: str
    schema_version: str
    artifact_hash: str | None
    trigger_type: ArtifactTriggerType
    status: ArtifactVersionStatus
    created_by: UUID
    generation_job_id: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.version_no, int)
            or isinstance(self.version_no, bool)
            or self.version_no < 1
        ):
            raise ArtifactValidationError("Artifact Version number must be at least one")
        if self.schema_name != ARTIFACT_SCHEMA_NAME:
            raise ArtifactValidationError("Artifact schema name is not canonical")
        if self.schema_version != ARTIFACT_SCHEMA_VERSION:
            raise ArtifactValidationError("Artifact schema version is not canonical")
        validate_artifact_version_status(self.status)
        validate_artifact_trigger_type(self.trigger_type)
        if self.version_no == 1:
            if self.parent_version_id is not None or self.trigger_type != "initial":
                raise ArtifactValidationError("Initial Artifact Version lineage is invalid")
        elif self.parent_version_id is None or self.trigger_type == "initial":
            raise ArtifactValidationError("Revision Artifact Version lineage is invalid")
        if self.status == "ready":
            validate_manifest_identity(self.storage_ref, self.artifact_hash)
        elif self.storage_ref is not None or self.artifact_hash is not None:
            raise ArtifactValidationError("Only ready Artifact Versions expose a Manifest")
        _require_timezone(self.created_at, "created_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactAllocation:
    artifact: Artifact
    version: ArtifactVersion


def validate_artifact_status(value: str) -> ArtifactStatus:
    if value not in ARTIFACT_STATUSES:
        raise ArtifactValidationError("Unsupported Artifact status")
    return cast(ArtifactStatus, value)


def validate_artifact_version_status(value: str) -> ArtifactVersionStatus:
    if value not in ARTIFACT_VERSION_STATUSES:
        raise ArtifactValidationError("Unsupported Artifact Version status")
    return cast(ArtifactVersionStatus, value)


def validate_artifact_trigger_type(value: str) -> ArtifactTriggerType:
    if value not in ARTIFACT_TRIGGER_TYPES:
        raise ArtifactValidationError("Unsupported Artifact trigger type")
    return cast(ArtifactTriggerType, value)


def validate_manifest_identity(
    storage_ref: str | None, artifact_hash: str | None
) -> tuple[str, str]:
    if storage_ref is None or not storage_ref.strip():
        raise ArtifactValidationError("Artifact Manifest reference is required")
    if artifact_hash is None or _SHA256_PATTERN.fullmatch(artifact_hash) is None:
        raise ArtifactValidationError("Artifact Manifest hash is invalid")
    return storage_ref, artifact_hash


def _require_timezone(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise ArtifactValidationError(f"{field} must be timezone-aware")
