from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.modules.scope.domain.scope_draft import (
    ScopeDraftValidationError,
    validate_scope_content,
)

ScopeVersionStatus = Literal["awaiting_approval", "approved", "changes_requested", "superseded"]
SCOPE_VERSION_STATUSES = frozenset(
    {"awaiting_approval", "approved", "changes_requested", "superseded"}
)
SCOPE_SNAPSHOT_CANONICALIZATION_VERSION = "scope_snapshot_canonicalization_v1"
_SNAPSHOT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ScopeVersionValidationError(ValueError):
    """A K05 Scope Version or snapshot invariant was violated."""


def canonicalize_scope_snapshot(snapshot_data: dict[str, Any]) -> bytes:
    """Return canonicalization-v1 bytes for a validated Scope snapshot.

    Version 1 supports the current Scope schema, whose values do not contain JSON numbers.
    Object keys are sorted, insignificant whitespace is removed, UTF-8 is used and array order
    remains meaningful.
    """
    try:
        validated = validate_scope_content(snapshot_data)
        serialized = json.dumps(
            validated,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (ScopeDraftValidationError, TypeError, ValueError) as exc:
        raise ScopeVersionValidationError("Scope snapshot is not canonical JSON") from exc
    return serialized.encode("utf-8")


def hash_scope_snapshot(snapshot_data: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonicalize_scope_snapshot(snapshot_data)).hexdigest()
    return f"sha256:{digest}"


def _validate_version(
    *,
    version_no: int,
    context_version: int,
    status: str,
    snapshot_data: dict[str, Any],
    snapshot_hash: str,
    initial: bool,
) -> None:
    if isinstance(version_no, bool) or not isinstance(version_no, int) or version_no < 1:
        raise ScopeVersionValidationError("version_no must be at least one")
    if (
        isinstance(context_version, bool)
        or not isinstance(context_version, int)
        or context_version < 1
    ):
        raise ScopeVersionValidationError("context_version must be at least one")
    if status not in SCOPE_VERSION_STATUSES:
        raise ScopeVersionValidationError("Unsupported Scope Version status")
    if initial and status != "awaiting_approval":
        raise ScopeVersionValidationError("K05 creates only awaiting_approval versions")
    if not isinstance(snapshot_hash, str) or not _SNAPSHOT_HASH_PATTERN.fullmatch(snapshot_hash):
        raise ScopeVersionValidationError("snapshot_hash format is invalid")
    expected = hash_scope_snapshot(snapshot_data)
    if snapshot_hash != expected:
        raise ScopeVersionValidationError("snapshot_hash does not match snapshot_data")


@dataclass(frozen=True, slots=True, kw_only=True)
class NewScopeVersion:
    id: UUID
    account_id: UUID
    project_id: UUID
    version_no: int
    context_version: int
    status: ScopeVersionStatus
    snapshot_data: dict[str, Any]
    snapshot_hash: str
    created_by: UUID

    def __post_init__(self) -> None:
        _validate_version(
            version_no=self.version_no,
            context_version=self.context_version,
            status=self.status,
            snapshot_data=self.snapshot_data,
            snapshot_hash=self.snapshot_hash,
            initial=True,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeVersion:
    id: UUID
    account_id: UUID
    project_id: UUID
    version_no: int
    context_version: int
    status: ScopeVersionStatus
    snapshot_data: dict[str, Any]
    snapshot_hash: str
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_version(
            version_no=self.version_no,
            context_version=self.context_version,
            status=self.status,
            snapshot_data=self.snapshot_data,
            snapshot_hash=self.snapshot_hash,
            initial=False,
        )
        if self.created_at.tzinfo is None:
            raise ScopeVersionValidationError("created_at must be timezone-aware")
