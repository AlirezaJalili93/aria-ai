from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.generation.domain.artifact import (
    Artifact,
    ArtifactValidationError,
    ArtifactVersion,
)


def _version(**overrides: object) -> ArtifactVersion:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "artifact_id": uuid4(),
        "scope_version_id": uuid4(),
        "version_no": 1,
        "parent_version_id": None,
        "storage_ref": None,
        "schema_name": "generation_ast_schema",
        "schema_version": "v1",
        "artifact_hash": None,
        "trigger_type": "initial",
        "status": "queued",
        "created_by": uuid4(),
        "generation_job_id": uuid4(),
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ArtifactVersion(**values)  # type: ignore[arg-type]


def test_artifact_accepts_only_stable_website_identity() -> None:
    now = datetime.now(UTC)
    artifact = Artifact(
        id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        artifact_type="website",
        current_version_id=None,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    assert artifact.artifact_type == "website"
    with pytest.raises(ArtifactValidationError):
        Artifact(
            id=uuid4(),
            account_id=uuid4(),
            project_id=uuid4(),
            artifact_type="application",
            current_version_id=None,
            status="draft",
            created_at=now,
            updated_at=now,
        )
    with pytest.raises(ArtifactValidationError):
        Artifact(
            id=uuid4(),
            account_id=uuid4(),
            project_id=uuid4(),
            artifact_type="website",
            current_version_id=None,
            status="ready",
            created_at=now,
            updated_at=now,
        )


def test_initial_and_revision_lineage_are_explicit() -> None:
    assert _version().version_no == 1
    parent_id = uuid4()
    assert (
        _version(
            version_no=2,
            parent_version_id=parent_id,
            trigger_type="feedback_revision",
        ).parent_version_id
        == parent_id
    )
    with pytest.raises(ArtifactValidationError):
        _version(version_no=2, parent_version_id=None, trigger_type="feedback_revision")
    with pytest.raises(ArtifactValidationError):
        _version(version_no=1, parent_version_id=parent_id)


def test_manifest_identity_exists_only_for_ready_version() -> None:
    digest = "sha256:" + "a" * 64
    ready = _version(
        status="ready",
        storage_ref="private manifest reference",
        artifact_hash=digest,
    )
    assert ready.artifact_hash == digest
    with pytest.raises(ArtifactValidationError):
        _version(status="ready", storage_ref="private manifest reference")
    with pytest.raises(ArtifactValidationError):
        _version(storage_ref="private manifest reference", artifact_hash=digest)


def test_schema_identity_is_frozen_to_generation_ast_v1() -> None:
    with pytest.raises(ArtifactValidationError):
        _version(schema_name="candidate")
    with pytest.raises(ArtifactValidationError):
        _version(schema_version="v2")
