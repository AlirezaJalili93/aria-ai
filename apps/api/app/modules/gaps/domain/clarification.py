from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from aria_backend_application.text_normalization import normalize_text

ClarificationStatus = Literal["open", "answered", "ignored"]
ClarificationCreatorType = Literal["ai", "user", "system"]
ClarificationResolutionType = Literal[
    "provided_information",
    "internal_decision",
    "accepted_assumption",
    "ignored",
]
ClarificationAuthorType = Literal["user", "client"]

CLARIFICATION_STATUSES = frozenset({"open", "answered", "ignored"})
CLARIFICATION_CREATOR_TYPES = frozenset({"ai", "user", "system"})
CLARIFICATION_RESOLUTION_TYPES = frozenset(
    {"provided_information", "internal_decision", "accepted_assumption", "ignored"}
)
CLARIFICATION_AUTHOR_TYPES = frozenset({"user", "client"})


class ClarificationValidationError(ValueError):
    """An approved J03-A Clarification invariant was violated."""


@dataclass(frozen=True, slots=True, kw_only=True)
class NewClarification:
    id: UUID
    account_id: UUID
    project_id: UUID
    gap_id: UUID
    question_text: str
    created_by_type: ClarificationCreatorType
    created_by: UUID | None
    status: ClarificationStatus = "open"

    def __post_init__(self) -> None:
        normalized = normalize_question_text(self.question_text)
        object.__setattr__(self, "question_text", normalized)
        validate_status(self.status)
        validate_creator_type(self.created_by_type)
        if self.created_by_type == "user" and self.created_by is None:
            raise ClarificationValidationError("A user-created question requires created_by")


@dataclass(frozen=True, slots=True, kw_only=True)
class Clarification(NewClarification):
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        NewClarification.__post_init__(self)
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ClarificationValidationError("Clarification timestamps must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class NewClarificationResolution:
    id: UUID
    account_id: UUID
    project_id: UUID
    gap_id: UUID
    clarification_id: UUID
    resolution_type: ClarificationResolutionType
    answer_text: str | None
    author_type: ClarificationAuthorType
    author_id: UUID | None
    actor_id: UUID

    def __post_init__(self) -> None:
        validate_resolution_type(self.resolution_type)
        validate_author_type(self.author_type)
        if self.resolution_type in {"provided_information", "internal_decision"}:
            if self.answer_text is None:
                raise ClarificationValidationError("This resolution requires answer_text")
            normalized = normalize_question_text(self.answer_text)
            object.__setattr__(self, "answer_text", normalized)
        elif self.answer_text is not None:
            raise ClarificationValidationError("This resolution forbids answer_text")


@dataclass(frozen=True, slots=True, kw_only=True)
class ClarificationResolution(NewClarificationResolution):
    created_at: datetime

    def __post_init__(self) -> None:
        NewClarificationResolution.__post_init__(self)
        if self.created_at.tzinfo is None:
            raise ClarificationValidationError("Resolution created_at must be timezone-aware")


def normalize_question_text(value: str) -> str:
    if not isinstance(value, str):
        raise ClarificationValidationError("Clarification text must be a string")
    normalized = normalize_text(value)
    if not normalized:
        raise ClarificationValidationError("Clarification text must not be empty")
    return normalized


def validate_status(value: str) -> ClarificationStatus:
    if value not in CLARIFICATION_STATUSES:
        raise ClarificationValidationError("Unsupported Clarification status")
    return cast(ClarificationStatus, value)


def validate_creator_type(value: str) -> ClarificationCreatorType:
    if value not in CLARIFICATION_CREATOR_TYPES:
        raise ClarificationValidationError("Unsupported Clarification creator type")
    return cast(ClarificationCreatorType, value)


def validate_resolution_type(value: str) -> ClarificationResolutionType:
    if value not in CLARIFICATION_RESOLUTION_TYPES:
        raise ClarificationValidationError("Unsupported Clarification resolution type")
    return cast(ClarificationResolutionType, value)


def validate_author_type(value: str) -> ClarificationAuthorType:
    if value not in CLARIFICATION_AUTHOR_TYPES:
        raise ClarificationValidationError("Unsupported Clarification author type")
    return cast(ClarificationAuthorType, value)
