from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.context.domain.context_item import (
    ContextItem,
    ContextItemValidationError,
    NewContextItem,
    SourceReference,
)


def _item(**overrides: object) -> NewContextItem:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "context_version": 1,
        "item_type": "assumption",
        "content": "  متن بدون نرمال‌سازی  ",
        "source_refs": (),
        "confidence": None,
        "status": "proposed",
        "created_by_type": "system",
        "created_by": None,
    }
    values.update(overrides)
    return NewContextItem(**values)  # type: ignore[arg-type]


def test_domain_accepts_exact_vocabulary_and_preserves_content() -> None:
    for item_type in ("fact", "assumption", "decision", "constraint", "reference", "unknown"):
        item = _item(item_type=item_type)
        assert item.item_type == item_type
        assert item.content == "  متن بدون نرمال‌سازی  "
    for status in ("proposed", "confirmed", "rejected", "superseded"):
        refs = (SourceReference(uuid4(), uuid4()),) if status == "confirmed" else ()
        item = _item(item_type="fact", status=status, source_refs=refs)
        assert item.status == status
    for creator_type in ("ai", "user", "system"):
        creator = uuid4() if creator_type == "user" else None
        item = _item(created_by_type=creator_type, created_by=creator)
        assert item.created_by_type == creator_type

    default_status = NewContextItem(
        id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        context_version=1,
        item_type="unknown",
        content="",
        source_refs=(),
        confidence=None,
        created_by_type="system",
        created_by=None,
    )
    assert default_status.status == "proposed"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("item_type", "claim"),
        ("status", "active"),
        ("created_by_type", "human"),
        ("confidence", Decimal("-0.0001")),
        ("confidence", Decimal("1.0001")),
    ],
)
def test_domain_rejects_invalid_context_item_values(field: str, value: object) -> None:
    with pytest.raises(ContextItemValidationError):
        _item(**{field: value})


def test_confirmed_fact_requires_evidence_and_user_requires_creator() -> None:
    with pytest.raises(ContextItemValidationError):
        _item(item_type="fact", status="confirmed", source_refs=())
    with pytest.raises(ContextItemValidationError):
        _item(created_by_type="user", created_by=None)


def test_source_reference_offsets_are_all_or_nothing_and_half_open() -> None:
    source_id, version_id = uuid4(), uuid4()
    assert SourceReference(source_id, version_id, 0, 1).to_dict() == {
        "source_id": str(source_id),
        "source_version_id": str(version_id),
        "start_offset": 0,
        "end_offset": 1,
    }
    assert SourceReference(source_id, version_id).to_dict() == {
        "source_id": str(source_id),
        "source_version_id": str(version_id),
    }
    for offsets in ((0, None), (None, 1), (-1, 1), (1, 1), (2, 1)):
        with pytest.raises(ContextItemValidationError):
            SourceReference(source_id, version_id, *offsets)


def test_persisted_item_requires_timezone_aware_created_at() -> None:
    values = _item()
    item = ContextItem(**asdict(values), created_at=datetime.now(UTC))
    assert item.created_at.tzinfo is not None
    with pytest.raises(ContextItemValidationError):
        ContextItem(**asdict(values), created_at=datetime.now())
