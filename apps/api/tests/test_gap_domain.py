from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.gaps.domain.gap import (
    Gap,
    GapSourceReference,
    GapValidationError,
    NewGap,
)


def _gap(**overrides: object) -> NewGap:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "context_version": 1,
        "gap_type": "missing_information",
        "severity": "critical",
        "source_refs": (),
        "status": "open",
        "resolved_at": None,
    }
    values.update(overrides)
    return NewGap(**values)  # type: ignore[arg-type]


def test_domain_accepts_exact_vocabularies_and_open_default() -> None:
    for gap_type in (
        "missing_information",
        "ambiguity",
        "conflict",
        "decision_required",
        "unsupported_assumption",
        "scope_risk",
    ):
        assert _gap(gap_type=gap_type).gap_type == gap_type
    for severity in ("critical", "high", "medium", "low"):
        assert _gap(severity=severity).severity == severity
    for status in ("open", "resolved", "dismissed"):
        resolved_at = datetime.now(UTC) if status == "resolved" else None
        assert _gap(status=status, resolved_at=resolved_at).status == status

    assert NewGap(
        id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        context_version=1,
        gap_type="ambiguity",
        severity="low",
        source_refs=(),
    ).status == "open"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("gap_type", "missing_info"),
        ("gap_type", "incomplete_requirement"),
        ("severity", "non_critical"),
        ("status", "answered"),
    ],
)
def test_domain_rejects_superseded_or_unsupported_values(field: str, value: object) -> None:
    with pytest.raises(GapValidationError):
        _gap(**{field: value})


def test_resolved_at_is_null_for_open_and_dismissed() -> None:
    timestamp = datetime.now(UTC)
    for status in ("open", "dismissed"):
        with pytest.raises(GapValidationError):
            _gap(status=status, resolved_at=timestamp)

    assert _gap(status="resolved", resolved_at=None).resolved_at is None


def test_source_reference_contract_allows_empty_and_validates_half_open_offsets() -> None:
    assert _gap(gap_type="missing_information", source_refs=()).source_refs == ()
    source_id, version_id = uuid4(), uuid4()
    assert GapSourceReference(source_id, version_id, 0, 1).to_dict() == {
        "source_id": str(source_id),
        "source_version_id": str(version_id),
        "start_offset": 0,
        "end_offset": 1,
    }
    for offsets in ((0, None), (None, 1), (-1, 1), (1, 1), (2, 1)):
        with pytest.raises(GapValidationError):
            GapSourceReference(source_id, version_id, *offsets)


def test_persisted_gap_requires_timezone_aware_timestamps() -> None:
    values = _gap()
    now = datetime.now(UTC)
    assert Gap(**asdict(values), created_at=now, updated_at=now).created_at == now
    with pytest.raises(GapValidationError):
        Gap(**asdict(values), created_at=datetime.now(), updated_at=now)
    with pytest.raises(GapValidationError):
        Gap(**asdict(values), created_at=now, updated_at=datetime.now())
