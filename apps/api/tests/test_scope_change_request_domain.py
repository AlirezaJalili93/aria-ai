from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.sharing.domain.scope_change_request import (
    NewScopeChangeRequest,
    ScopeChangeRequestValidationError,
    normalize_change_comment,
)


def _change_request(**changes: object) -> NewScopeChangeRequest:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "scope_version_id": uuid4(),
        "share_link_id": uuid4(),
        "version_no": 1,
        "version_hash": "sha256:" + "a" * 64,
        "guest_name": "علی جلیلی",
        "comment": "لطفاً بخش بودجه اصلاح شود.",
        "idempotency_key": "change-key",
        "request_hash": "b" * 64,
        "requested_at": datetime.now(UTC),
    }
    values.update(changes)
    return NewScopeChangeRequest(**values)  # type: ignore[arg-type]


def test_comment_normalizes_nfc_newlines_and_outer_whitespace_only() -> None:
    assert normalize_change_comment("  A\u0301\r\n  خط دوم  \r") == "Á\n  خط دوم"
    assert normalize_change_comment("ي ك") == "ي ك"


@pytest.mark.parametrize(
    "comment",
    ["", " \r\n ", "a" * 4001, "متن\x00", "متن\x1f", "متن\x7f", "متن\x85"],
)
def test_comment_rejects_empty_oversize_and_controls_except_lf(comment: str) -> None:
    with pytest.raises(ScopeChangeRequestValidationError):
        normalize_change_comment(comment)


def test_change_request_requires_canonical_immutable_snapshot_metadata() -> None:
    _change_request()
    for changes in (
        {"guest_name": "  Ali  "},
        {"comment": "  comment  "},
        {"version_hash": "a" * 64},
        {"version_no": 0},
        {"request_hash": "not-a-hash"},
        {"requested_at": datetime.now()},
    ):
        with pytest.raises(ScopeChangeRequestValidationError):
            _change_request(**changes)
