from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.requirements.domain.requirement import (
    NewRequirement,
    Requirement,
    RequirementSourceReference,
    RequirementValidationError,
)


def _new_requirement(**overrides: object) -> NewRequirement:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "context_version": 1,
        "category": "functional",
        "title": "عنوان نیازمندی",
        "description": "شرح نیازمندی",
        "priority": "must",
        "status": "draft",
        "source_refs": (),
        "confidence": None,
        "created_by_type": "ai",
        "created_by": None,
    }
    values.update(overrides)
    return NewRequirement(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("context_version", 0),
        ("context_version", True),
        ("category", "security"),
        ("priority", None),
        ("priority", ""),
        ("priority", "default"),
        ("priority", "medium"),
        ("status", "active"),
        ("created_by_type", "system"),
        ("confidence", Decimal("-0.0001")),
        ("confidence", Decimal("1.0001")),
    ],
)
def test_requirement_rejects_values_outside_the_canonical_contract(
    field: str, value: object
) -> None:
    with pytest.raises(RequirementValidationError):
        _new_requirement(**{field: value})


def test_user_requirement_requires_creator_and_ai_creator_is_optional() -> None:
    with pytest.raises(RequirementValidationError):
        _new_requirement(created_by_type="user", created_by=None)

    creator = uuid4()
    assert _new_requirement(created_by_type="user", created_by=creator).created_by == creator
    assert _new_requirement(created_by_type="ai", created_by=None).created_by is None


def test_source_reference_matches_h01_shape_and_half_open_offsets() -> None:
    source_id, source_version_id = uuid4(), uuid4()
    assert RequirementSourceReference(source_id, source_version_id).to_dict() == {
        "source_id": str(source_id),
        "source_version_id": str(source_version_id),
    }
    assert RequirementSourceReference(source_id, source_version_id, 2, 7).to_dict() == {
        "source_id": str(source_id),
        "source_version_id": str(source_version_id),
        "start_offset": 2,
        "end_offset": 7,
    }
    for offsets in ((0, None), (None, 2), (-1, 2), (2, 2), (3, 2), (False, 2)):
        with pytest.raises(RequirementValidationError):
            RequirementSourceReference(source_id, source_version_id, *offsets)


def test_persisted_requirement_requires_timezone_aware_timestamps() -> None:
    values = _new_requirement()
    fields = {
        "id": values.id,
        "account_id": values.account_id,
        "project_id": values.project_id,
        "context_version": values.context_version,
        "category": values.category,
        "title": values.title,
        "description": values.description,
        "priority": values.priority,
        "status": values.status,
        "source_refs": values.source_refs,
        "confidence": values.confidence,
        "created_by_type": values.created_by_type,
        "created_by": values.created_by,
    }
    with pytest.raises(RequirementValidationError):
        Requirement(**fields, created_at=datetime.now(), updated_at=datetime.now())

    fields["status"] = "removed"
    persisted = Requirement(
        **fields,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert persisted.is_removed
