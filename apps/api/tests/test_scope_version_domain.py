from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.domain.scope_version import (
    SCOPE_SNAPSHOT_CANONICALIZATION_VERSION,
    NewScopeVersion,
    ScopeVersionValidationError,
    canonicalize_scope_snapshot,
    hash_scope_snapshot,
)


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {
                    "context_item_ids": [],
                    "requirement_ids": [],
                    "gap_ids": [],
                },
            }
            for section_id in SECTION_IDS
        ],
    }


def test_snapshot_hash_is_versioned_deterministic_and_includes_trace() -> None:
    snapshot = _snapshot()
    reordered = {
        "sections": [
            {
                "trace": dict(reversed(list(section["trace"].items()))),
                "value": section["value"],
                "section_id": section["section_id"],
            }
            for section in snapshot["sections"]
        ],
        "schema_version": snapshot["schema_version"],
    }

    assert SCOPE_SNAPSHOT_CANONICALIZATION_VERSION == "scope_snapshot_canonicalization_v1"
    assert canonicalize_scope_snapshot(snapshot) == canonicalize_scope_snapshot(reordered)
    digest = hash_scope_snapshot(snapshot)
    assert digest == hash_scope_snapshot(reordered)
    assert len(digest) == 71
    assert digest.startswith("sha256:")
    assert digest[7:] == digest[7:].lower()

    traced = deepcopy(snapshot)
    traced["sections"][0]["trace"]["context_item_ids"] = [str(uuid4())]
    assert hash_scope_snapshot(traced) != digest


def test_snapshot_hash_preserves_array_order() -> None:
    first = _snapshot()
    first["sections"][1]["value"] = ["هدف اول", "هدف دوم"]
    second = deepcopy(first)
    second["sections"][1]["value"] = ["هدف دوم", "هدف اول"]

    assert hash_scope_snapshot(first) != hash_scope_snapshot(second)


def test_scope_version_requires_exact_frozen_contract() -> None:
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "version_no": 1,
        "context_version": 2,
        "status": "awaiting_approval",
        "snapshot_data": _snapshot(),
        "snapshot_hash": hash_scope_snapshot(_snapshot()),
        "created_by": uuid4(),
    }
    version = NewScopeVersion(**values)
    assert version.version_no == 1

    for field, invalid in (
        ("version_no", 0),
        ("context_version", 0),
        ("status", "approved"),
        ("snapshot_hash", "sha256:ABC"),
    ):
        candidate = {**values, field: invalid}
        with pytest.raises(ScopeVersionValidationError):
            NewScopeVersion(**candidate)

    with pytest.raises(ScopeVersionValidationError):
        NewScopeVersion(**{**values, "snapshot_hash": "sha256:" + "0" * 64})

    assert now.tzinfo is not None
