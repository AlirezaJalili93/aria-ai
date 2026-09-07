from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

RequirementCategory = Literal[
    "functional", "content", "visual", "technical", "constraint", "business"
]
RequirementPriority = Literal["must", "should", "could"]
RequirementStatus = Literal["draft", "confirmed", "superseded", "removed"]
RequirementCreatorType = Literal["ai", "user"]

REQUIREMENT_CATEGORIES = frozenset(
    {"functional", "content", "visual", "technical", "constraint", "business"}
)
REQUIREMENT_PRIORITIES = frozenset({"must", "should", "could"})
REQUIREMENT_STATUSES = frozenset({"draft", "confirmed", "superseded", "removed"})
REQUIREMENT_CREATOR_TYPES = frozenset({"ai", "user"})


class RequirementValidationError(ValueError):
    """An approved Requirement invariant was violated."""


@dataclass(frozen=True, slots=True)
class RequirementSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        offsets_absent = self.start_offset is None and self.end_offset is None
        offsets_present = self.start_offset is not None and self.end_offset is not None
        if not offsets_absent and not offsets_present:
            raise RequirementValidationError("Source Reference offsets must be provided together")
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
                raise RequirementValidationError(
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
class NewRequirement:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    category: RequirementCategory
    title: str
    description: str
    priority: RequirementPriority
    source_refs: tuple[RequirementSourceReference, ...]
    confidence: Decimal | None
    created_by_type: RequirementCreatorType
    created_by: UUID | None
    is_unsupported: bool = False
    duplicate_group_key: str | None = None
    generation_job_id: UUID | None = None
    acceptance_note: str | None = None
    status: RequirementStatus = "draft"

    def __post_init__(self) -> None:
        validate_context_version(self.context_version)
        validate_category(self.category)
        validate_priority(self.priority)
        validate_status(self.status)
        validate_creator_type(self.created_by_type)
        validate_confidence(self.confidence)
        if not isinstance(self.title, str) or len(self.title) > 255:
            raise RequirementValidationError("Requirement title exceeds its data contract")
        if not isinstance(self.description, str):
            raise RequirementValidationError("Requirement description must be text")
        if not isinstance(self.is_unsupported, bool):
            raise RequirementValidationError("is_unsupported must be boolean")
        if self.duplicate_group_key is not None and not isinstance(
            self.duplicate_group_key, str
        ):
            raise RequirementValidationError("duplicate_group_key must be text")
        if self.acceptance_note is not None and not isinstance(self.acceptance_note, str):
            raise RequirementValidationError("acceptance_note must be text or null")
        if self.created_by_type == "user" and self.created_by is None:
            raise RequirementValidationError("A user-created Requirement requires created_by")


@dataclass(frozen=True, slots=True, kw_only=True)
class Requirement(NewRequirement):
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        NewRequirement.__post_init__(self)
        if self.created_at.tzinfo is None:
            raise RequirementValidationError("created_at must be timezone-aware")
        if self.updated_at.tzinfo is None:
            raise RequirementValidationError("updated_at must be timezone-aware")

    @property
    def is_removed(self) -> bool:
        return self.status == "removed"


def validate_context_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RequirementValidationError("context_version must be at least one")
    return value


def validate_category(value: str) -> RequirementCategory:
    if value not in REQUIREMENT_CATEGORIES:
        raise RequirementValidationError("Unsupported Requirement category")
    return cast(RequirementCategory, value)


def validate_priority(value: str) -> RequirementPriority:
    if value not in REQUIREMENT_PRIORITIES:
        raise RequirementValidationError("Unsupported Requirement priority")
    return cast(RequirementPriority, value)


def validate_status(value: str) -> RequirementStatus:
    if value not in REQUIREMENT_STATUSES:
        raise RequirementValidationError("Unsupported Requirement status")
    return cast(RequirementStatus, value)


def validate_creator_type(value: str) -> RequirementCreatorType:
    if value not in REQUIREMENT_CREATOR_TYPES:
        raise RequirementValidationError("Unsupported Requirement creator type")
    return cast(RequirementCreatorType, value)


def validate_confidence(value: Decimal | None) -> Decimal | None:
    if value is not None and (value < Decimal(0) or value > Decimal(1)):
        raise RequirementValidationError("Requirement confidence must be between zero and one")
    return value
