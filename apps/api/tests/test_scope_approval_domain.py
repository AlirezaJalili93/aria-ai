from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.sharing.domain.scope_approval import (
    NewScopeApproval,
    ScopeApprovalValidationError,
    normalize_guest_name,
)


def _approval(**changes: object) -> NewScopeApproval:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "scope_version_id": uuid4(),
        "share_link_id": uuid4(),
        "version_no": 1,
        "version_hash": "sha256:" + "a" * 64,
        "guest_name": "علی جلیلی",
        "explicit_consent": True,
        "idempotency_key": "approval-key",
        "request_hash": "b" * 64,
        "approved_at": datetime.now(UTC),
    }
    values.update(changes)
    return NewScopeApproval(**values)  # type: ignore[arg-type]


def test_guest_name_normalizes_nfc_and_outer_whitespace_only() -> None:
    assert normalize_guest_name("  A\u0301li رضا  ") == "Áli رضا"
    assert normalize_guest_name("ي ك") == "ي ك"


@pytest.mark.parametrize("name", ["", " ", "A", "a" * 101, "Ali\x00", "Ali\x85"])
def test_guest_name_rejects_length_and_c0_c1_controls(name: str) -> None:
    with pytest.raises(ScopeApprovalValidationError):
        normalize_guest_name(name)


def test_approval_requires_normalized_name_consent_hash_and_timestamp() -> None:
    _approval()
    for changes in (
        {"guest_name": "  Ali  "},
        {"explicit_consent": False},
        {"version_hash": "a" * 64},
        {"version_no": 0},
        {"request_hash": "not-a-hash"},
        {"approved_at": datetime.now()},
    ):
        with pytest.raises(ScopeApprovalValidationError):
            _approval(**changes)
