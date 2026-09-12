from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

ScopeDraftActorType = Literal["user", "ai", "system"]
SCOPE_CONTENT_SCHEMA_VERSION = "scope_content_schema_v1"
SECTION_IDS = (
    "summary",
    "goals",
    "pages_sections",
    "requirements",
    "content",
    "visual_direction",
    "constraints",
    "assumptions",
    "resolved_gaps",
    "remaining_non_blocking_gaps",
    "out_of_scope",
    "acceptance_notes",
)
TRACE_KEYS = ("context_item_ids", "requirement_ids", "gap_ids")
STRUCTURED_SECTION_ITEM_KEYS: dict[str, set[str]] = {
    "requirements": {"item_id", "text", "priority"},
    "content": {"item_id", "description"},
    "resolved_gaps": {"item_id", "text", "resolution_type"},
    "remaining_non_blocking_gaps": {"item_id", "text", "severity"},
}


class ScopeDraftValidationError(ValueError):
    """An approved Scope Draft invariant was violated."""


class ScopeDraftHistoricalError(ValueError):
    """A Draft bound to an older Context Version cannot be mutated."""


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScopeDraftValidationError(f"{label} must be a non-empty string")
    return value


def _require_uuid_text(value: Any, label: str) -> str:
    text = _require_text(value, label)
    try:
        UUID(text)
    except ValueError as exc:
        raise ScopeDraftValidationError(f"{label} must be a UUID") from exc
    return text


def _validate_trace(trace: Any) -> dict[str, list[str]]:
    if not isinstance(trace, dict) or set(trace) != set(TRACE_KEYS):
        raise ScopeDraftValidationError("Scope trace must contain exactly the approved keys")
    result: dict[str, list[str]] = {}
    for key in TRACE_KEYS:
        values = trace[key]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ScopeDraftValidationError("Scope trace values must be string arrays")
        if len(values) != len(set(values)):
            raise ScopeDraftValidationError("Scope trace IDs must be unique")
        for item in values:
            _require_uuid_text(item, f"trace.{key}")
        if values != sorted(values):
            raise ScopeDraftValidationError("Scope trace IDs must be deterministically ordered")
        result[key] = list(values)
    return result


def _validate_items(value: Any, label: str, required_keys: set[str]) -> None:
    if not isinstance(value, list):
        raise ScopeDraftValidationError(f"{label} must be an array")
    ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != required_keys:
            raise ScopeDraftValidationError(f"{label} item shape is invalid")
        item_id = _require_text(item.get("item_id"), f"{label}.item_id")
        if item_id in ids:
            raise ScopeDraftValidationError(f"{label} item IDs must be unique")
        ids.add(item_id)


def validate_scope_content(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "sections"}:
        raise ScopeDraftValidationError("Scope content must contain schema_version and sections")
    if value["schema_version"] != SCOPE_CONTENT_SCHEMA_VERSION:
        raise ScopeDraftValidationError("Unknown Scope content schema version")
    sections = value["sections"]
    if not isinstance(sections, list) or len(sections) != len(SECTION_IDS):
        raise ScopeDraftValidationError("All canonical Scope sections are structurally required")
    seen: set[str] = set()
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"section_id", "value", "trace"}:
            raise ScopeDraftValidationError("Scope section shape is invalid")
        section_id = section.get("section_id")
        if section_id not in SECTION_IDS or section_id in seen:
            raise ScopeDraftValidationError("Scope section IDs must be canonical and unique")
        seen.add(section_id)
        _validate_trace(section["trace"])
        value_part = section["value"]
        if section_id in {"summary", "visual_direction"}:
            if not isinstance(value_part, str):
                raise ScopeDraftValidationError(f"{section_id} must be a string")
        elif section_id in {
            "goals",
            "constraints",
            "assumptions",
            "out_of_scope",
            "acceptance_notes",
        }:
            if not isinstance(value_part, list) or any(
                not isinstance(item, str) for item in value_part
            ):
                raise ScopeDraftValidationError(f"{section_id} must be a string array")
        elif section_id == "pages_sections":
            _validate_items(value_part, section_id, {"item_id", "page_name", "sections"})
            for page in value_part:
                _require_text(page["page_name"], "pages_sections.page_name")
                _validate_items(page["sections"], "pages_sections.sections", {"item_id", "name"})
        elif section_id == "requirements":
            _validate_items(value_part, section_id, {"item_id", "text", "priority"})
            for item in value_part:
                _require_text(item["text"], "requirements.text")
                if item["priority"] not in {"must", "should", "could"}:
                    raise ScopeDraftValidationError("requirements.priority is invalid")
        elif section_id == "content":
            _validate_items(value_part, section_id, {"item_id", "description"})
            for item in value_part:
                _require_text(item["description"], "content.description")
        elif section_id == "resolved_gaps":
            _validate_items(value_part, section_id, {"item_id", "text", "resolution_type"})
            for item in value_part:
                _require_text(item["text"], "resolved_gaps.text")
                _require_text(item["resolution_type"], "resolved_gaps.resolution_type")
        elif section_id == "remaining_non_blocking_gaps":
            _validate_items(value_part, section_id, {"item_id", "text", "severity"})
            for item in value_part:
                _require_text(item["text"], "remaining_non_blocking_gaps.text")
                if item["severity"] not in {"critical", "high", "medium", "low"}:
                    raise ScopeDraftValidationError(
                        "remaining_non_blocking_gaps.severity is invalid"
                    )
    if seen != set(SECTION_IDS):
        raise ScopeDraftValidationError("Scope sections are incomplete")
    return value


def replace_scope_section_value(
    content: dict[str, object],
    *,
    section_id: str,
    value: object,
    id_factory: Callable[[], UUID] = uuid4,
) -> dict[str, Any]:
    """Replace one section value while retaining server-owned lineage."""
    current = validate_scope_content(deepcopy(content))
    if section_id not in SECTION_IDS:
        raise ScopeDraftValidationError("Unknown Scope section")
    sections = current["sections"]
    target = next(section for section in sections if section["section_id"] == section_id)
    target["value"] = _normalize_replacement_value(
        section_id, target["value"], value, id_factory
    )
    return validate_scope_content(current)


def _normalize_replacement_value(
    section_id: str,
    current: object,
    proposed: object,
    id_factory: Callable[[], UUID],
) -> object:
    if section_id == "pages_sections":
        return _normalize_pages_sections(current, proposed, id_factory)
    required_keys = STRUCTURED_SECTION_ITEM_KEYS.get(section_id)
    if required_keys is not None:
        return _normalize_item_array(
            current,
            proposed,
            required_keys=required_keys,
            id_factory=id_factory,
            label=section_id,
        )
    return deepcopy(proposed)


def _normalize_pages_sections(
    current: object,
    proposed: object,
    id_factory: Callable[[], UUID],
) -> list[dict[str, object]]:
    pages = _normalize_item_array(
        current,
        proposed,
        required_keys={"item_id", "page_name", "sections"},
        id_factory=id_factory,
        label="pages_sections",
        validate_after=False,
    )
    existing_pages = (
        {
            item["item_id"]: item
            for item in current
            if isinstance(item, dict) and isinstance(item.get("item_id"), str)
        }
        if isinstance(current, list)
        else {}
    )
    for page in pages:
        existing_page = existing_pages.get(page["item_id"])
        existing_sections = existing_page.get("sections", []) if existing_page else []
        page["sections"] = _normalize_item_array(
            existing_sections,
            page["sections"],
            required_keys={"item_id", "name"},
            id_factory=id_factory,
            label="pages_sections.sections",
        )
    return pages


def _normalize_item_array(
    current: object,
    proposed: object,
    *,
    required_keys: set[str],
    id_factory: Callable[[], UUID],
    label: str,
    validate_after: bool = True,
) -> list[dict[str, object]]:
    if not isinstance(proposed, list):
        raise ScopeDraftValidationError(f"{label} must be an array")
    current_ids = (
        {
            item["item_id"]
            for item in current
            if isinstance(item, dict) and isinstance(item.get("item_id"), str)
        }
        if isinstance(current, list)
        else set()
    )
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in proposed:
        if not isinstance(candidate, dict):
            raise ScopeDraftValidationError(f"{label} item shape is invalid")
        keys = set(candidate)
        if keys not in (required_keys, required_keys - {"item_id"}):
            raise ScopeDraftValidationError(f"{label} item shape is invalid")
        if "item_id" in candidate:
            item_id = candidate["item_id"]
            if not isinstance(item_id, str) or item_id not in current_ids:
                raise ScopeDraftValidationError(
                    f"{label} item ID is not an existing server ID"
                )
        else:
            item_id = str(id_factory())
        if item_id in seen:
            raise ScopeDraftValidationError(f"{label} item IDs must be unique")
        seen.add(item_id)
        normalized.append({**deepcopy(candidate), "item_id": item_id})
    if validate_after:
        _validate_items(normalized, label, required_keys)
    return normalized


@dataclass(frozen=True, slots=True, kw_only=True)
class NewScopeDraft:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    content: dict[str, Any]
    updated_by_type: ScopeDraftActorType
    updated_by: UUID | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.context_version, bool)
            or not isinstance(self.context_version, int)
            or self.context_version < 1
        ):
            raise ScopeDraftValidationError("context_version must be at least one")
        if self.updated_by_type not in {"user", "ai", "system"}:
            raise ScopeDraftValidationError("Unsupported Scope Draft actor type")
        if self.updated_by_type == "user" and self.updated_by is None:
            raise ScopeDraftValidationError("User Scope Draft updates require updated_by")
        validate_scope_content(self.content)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeDraft(NewScopeDraft):
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        NewScopeDraft.__post_init__(self)
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ScopeDraftValidationError("Scope Draft timestamps must be timezone-aware")
