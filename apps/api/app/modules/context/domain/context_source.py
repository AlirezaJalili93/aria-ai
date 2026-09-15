from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal, cast
from unicodedata import category
from uuid import UUID

ContextSourceType = Literal["text", "file", "message", "url_reference"]
ContextSourceStatus = Literal["uploaded", "parsing", "ready", "failed", "deleted"]
ContextSourceParseStatus = Literal["pending", "parsing", "ready", "failed"]

CONTEXT_SOURCE_TYPES = frozenset({"text", "file", "message", "url_reference"})
CONTEXT_SOURCE_STATUSES = frozenset({"uploaded", "parsing", "ready", "failed", "deleted"})
CONTEXT_SOURCE_PARSE_STATUSES = frozenset({"pending", "parsing", "ready", "failed"})
TEXT_CONTEXT_MAX_CHARACTERS = 50_000
_ALLOWED_TEXT_CONTROLS = frozenset({"\t", "\n", "\r"})


class ContextSourceValidationError(ValueError):
    """An approved Context Source invariant was violated."""


@dataclass(frozen=True, slots=True)
class NewContextSource:
    id: UUID
    account_id: UUID
    project_id: UUID
    source_type: ContextSourceType
    status: ContextSourceStatus
    original_name: str | None
    mime_type: str | None
    storage_ref: str | None
    raw_text: str | None
    checksum: str | None
    created_by: UUID

    def __post_init__(self) -> None:
        validate_source_type(self.source_type)
        validate_source_status(self.status)


@dataclass(frozen=True, slots=True)
class ContextSource(NewContextSource):
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        NewContextSource.__post_init__(self)
        _require_timezone(self.created_at, "created_at")
        _require_timezone(self.updated_at, "updated_at")

    @property
    def is_deleted(self) -> bool:
        return self.status == "deleted"


@dataclass(frozen=True, slots=True)
class NewContextSourceVersion:
    id: UUID
    account_id: UUID
    project_id: UUID
    source_id: UUID
    version_no: int
    content_hash: str | None
    canonical_text: str | None
    storage_ref: str | None
    metadata: dict[str, object] | None
    parse_status: ContextSourceParseStatus

    def __post_init__(self) -> None:
        validate_parse_status(self.parse_status)
        validate_version_number(self.version_no)
        if self.parse_status == "ready":
            validate_ready_content(self.canonical_text, self.storage_ref)


@dataclass(frozen=True, slots=True)
class ContextSourceVersion(NewContextSourceVersion):
    created_at: datetime

    def __post_init__(self) -> None:
        NewContextSourceVersion.__post_init__(self)
        _require_timezone(self.created_at, "created_at")


def validate_source_type(value: str) -> ContextSourceType:
    if value not in CONTEXT_SOURCE_TYPES:
        raise ContextSourceValidationError("Unsupported Context Source type")
    return cast(ContextSourceType, value)


def validate_source_status(value: str) -> ContextSourceStatus:
    if value not in CONTEXT_SOURCE_STATUSES:
        raise ContextSourceValidationError("Unsupported Context Source status")
    return cast(ContextSourceStatus, value)


def validate_parse_status(value: str) -> ContextSourceParseStatus:
    if value not in CONTEXT_SOURCE_PARSE_STATUSES:
        raise ContextSourceValidationError("Unsupported Context Source parse status")
    return cast(ContextSourceParseStatus, value)


def validate_version_number(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContextSourceValidationError("Context Source version_no must be at least one")
    return value


def validate_ready_content(canonical_text: str | None, storage_ref: str | None) -> None:
    if canonical_text is None and storage_ref is None:
        raise ContextSourceValidationError(
            "A ready Context Source Version requires canonical_text or storage_ref"
        )


def validate_text_context(value: str) -> str:
    if not value or value.isspace():
        raise ContextSourceValidationError("Text Context cannot be blank")
    if len(value) > TEXT_CONTEXT_MAX_CHARACTERS:
        raise ContextSourceValidationError("Text Context exceeds the approved character limit")
    if any(
        character not in _ALLOWED_TEXT_CONTROLS and category(character) == "Cc"
        for character in value
    ):
        raise ContextSourceValidationError("Text Context contains a disallowed control character")
    return value


def text_context_checksum(value: str) -> str:
    validate_text_context(value)
    return sha256(value.encode("utf-8")).hexdigest()


def _require_timezone(value: datetime, field: str) -> None:
    if value.tzinfo is None:
        raise ContextSourceValidationError(f"{field} must be timezone-aware")
