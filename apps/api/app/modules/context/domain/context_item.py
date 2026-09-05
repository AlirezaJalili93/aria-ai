from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

ContextItemType = Literal[
    "fact", "assumption", "decision", "constraint", "reference", "unknown"
]
ContextItemStatus = Literal["proposed", "confirmed", "rejected", "superseded"]
ContextItemCreatorType = Literal["ai", "user", "system"]

CONTEXT_ITEM_TYPES = frozenset(
    {"fact", "assumption", "decision", "constraint", "reference", "unknown"}
)
CONTEXT_ITEM_STATUSES = frozenset({"proposed", "confirmed", "rejected", "superseded"})
CONTEXT_ITEM_CREATOR_TYPES = frozenset({"ai", "user", "system"})


class ContextItemValidationError(ValueError):
    """An approved Context Item invariant was violated."""


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        offsets_absent = self.start_offset is None and self.end_offset is None
        offsets_present = self.start_offset is not None and self.end_offset is not None
        if not offsets_absent and not offsets_present:
            raise ContextItemValidationError("Source Reference offsets must be provided together")
        if offsets_present:
            assert self.start_offset is not None and self.end_offset is not None
            if (
                isinstance(self.start_offset, bool)
                or isinstance(self.end_offset, bool)
                or not isinstance(self.start_offset, int)
                or not isinstance(self.end_offset, int)
                or self.start_offset < 0
                or self.start_offset >= self.end_offset
            ):
                raise ContextItemValidationError(
                    "Source Reference offsets must be a half-open range"
                )

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "source_id": str(self.source_id),
            "source_version_id": str(self.source_version_id),
        }
        if self.start_offset is not None:
            value["start_offset"] = self.start_offset
            value["end_offset"] = self.end_offset
        return value


@dataclass(frozen=True, slots=True, kw_only=True)
class NewContextItem:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    item_type: ContextItemType
    content: str
    source_refs: tuple[SourceReference, ...]
    confidence: Decimal | None
    created_by_type: ContextItemCreatorType
    created_by: UUID | None
    status: ContextItemStatus = "proposed"

    def __post_init__(self) -> None:
        validate_context_version(self.context_version)
        validate_item_type(self.item_type)
        validate_item_status(self.status)
        validate_creator_type(self.created_by_type)
        validate_confidence(self.confidence)
        if self.created_by_type == "user" and self.created_by is None:
            raise ContextItemValidationError("A user-created Context Item requires created_by")
        if self.item_type == "fact" and self.status == "confirmed" and not self.source_refs:
            raise ContextItemValidationError("A confirmed Fact requires valid provenance")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextItem(NewContextItem):
    created_at: datetime

    def __post_init__(self) -> None:
        NewContextItem.__post_init__(self)
        if self.created_at.tzinfo is None:
            raise ContextItemValidationError("created_at must be timezone-aware")


def validate_context_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContextItemValidationError("context_version must be at least one")
    return value


def validate_item_type(value: str) -> ContextItemType:
    if value not in CONTEXT_ITEM_TYPES:
        raise ContextItemValidationError("Unsupported Context Item type")
    return cast(ContextItemType, value)


def validate_item_status(value: str) -> ContextItemStatus:
    if value not in CONTEXT_ITEM_STATUSES:
        raise ContextItemValidationError("Unsupported Context Item status")
    return cast(ContextItemStatus, value)


def validate_creator_type(value: str) -> ContextItemCreatorType:
    if value not in CONTEXT_ITEM_CREATOR_TYPES:
        raise ContextItemValidationError("Unsupported Context Item creator type")
    return cast(ContextItemCreatorType, value)


def validate_confidence(value: Decimal | None) -> Decimal | None:
    if value is not None and (value < Decimal(0) or value > Decimal(1)):
        raise ContextItemValidationError("Context Item confidence must be between zero and one")
    return value
