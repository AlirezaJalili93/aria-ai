from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from aria_backend_application.scope_content import (
    SCOPE_CONTENT_SCHEMA_VERSION,
    SECTION_IDS,
    STRUCTURED_SECTION_ITEM_KEYS,
    TRACE_KEYS,
    ScopeDraftActorType,
    ScopeDraftValidationError,
    replace_scope_section_value,
    validate_scope_content,
)

__all__ = (
    "SCOPE_CONTENT_SCHEMA_VERSION",
    "SECTION_IDS",
    "STRUCTURED_SECTION_ITEM_KEYS",
    "TRACE_KEYS",
    "ScopeDraftActorType",
    "ScopeDraftValidationError",
    "replace_scope_section_value",
    "validate_scope_content",
    "NewScopeDraft",
    "ScopeDraft",
)


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
