from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.scope.domain.scope_draft import (
    SCOPE_CONTENT_SCHEMA_VERSION,
    SECTION_IDS,
    NewScopeDraft,
    ScopeDraftValidationError,
    replace_scope_section_value,
    validate_scope_content,
)


def _content() -> dict[str, object]:
    return {
        "schema_version": SCOPE_CONTENT_SCHEMA_VERSION,
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
            for section_id in SECTION_IDS
        ],
    }


def test_scope_draft_accepts_all_structural_sections_with_empty_values() -> None:
    validate_scope_content(_content())
    NewScopeDraft(
        id=uuid4(), account_id=uuid4(), project_id=uuid4(), context_version=1,
        content=_content(), updated_by_type="system"
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["sections"].pop(),
        lambda value: value["sections"].append(value["sections"][0]),
        lambda value: value["sections"][0].update(section_id="unknown"),
        lambda value: value.update(schema_version="scope_content_schema_v0"),
    ],
)
def test_scope_content_rejects_invalid_structure(mutator) -> None:
    value = _content()
    mutator(value)
    with pytest.raises(ScopeDraftValidationError):
        validate_scope_content(value)


def test_scope_content_rejects_duplicate_or_unsorted_trace_ids() -> None:
    value = _content()
    first = str(uuid4())
    value["sections"][0]["trace"]["context_item_ids"] = [first, first]
    with pytest.raises(ScopeDraftValidationError):
        validate_scope_content(value)


def test_user_update_requires_actor_id() -> None:
    with pytest.raises(ScopeDraftValidationError):
        NewScopeDraft(
            id=uuid4(), account_id=uuid4(), project_id=uuid4(), context_version=1,
            content=_content(), updated_by_type="user"
        )


def test_section_replacement_preserves_trace_and_assigns_server_item_ids() -> None:
    content = _content()
    trace_id = str(uuid4())
    requirements = next(
        section for section in content["sections"] if section["section_id"] == "requirements"
    )
    requirements["trace"]["requirement_ids"] = [trace_id]
    assigned = uuid4()

    updated = replace_scope_section_value(
        content,
        section_id="requirements",
        value=[{"text": "نیاز تازه", "priority": "must"}],
        id_factory=lambda: assigned,
    )

    updated_section = next(
        section for section in updated["sections"] if section["section_id"] == "requirements"
    )
    assert updated_section["trace"] == requirements["trace"]
    assert updated_section["value"] == [
        {"item_id": str(assigned), "text": "نیاز تازه", "priority": "must"}
    ]
    assert next(
        section for section in updated["sections"] if section["section_id"] == "summary"
    ) == next(section for section in content["sections"] if section["section_id"] == "summary")


def test_structured_replacement_rejects_unknown_client_item_id() -> None:
    with pytest.raises(ScopeDraftValidationError):
        replace_scope_section_value(
            _content(),
            section_id="content",
            value=[{"item_id": "client-made", "description": "محتوا"}],
        )


def test_structured_replacement_preserves_known_ids_and_omits_deleted_items() -> None:
    content = _content()
    first, removed = str(uuid4()), str(uuid4())
    section = next(
        item for item in content["sections"] if item["section_id"] == "content"
    )
    section["value"] = [
        {"item_id": first, "description": "اول"},
        {"item_id": removed, "description": "حذف‌شونده"},
    ]

    updated = replace_scope_section_value(
        content,
        section_id="content",
        value=[{"item_id": first, "description": "ویرایش‌شده"}],
    )

    updated_section = next(
        item for item in updated["sections"] if item["section_id"] == "content"
    )
    assert updated_section["value"] == [
        {"item_id": first, "description": "ویرایش‌شده"}
    ]
