from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

GapType = Literal[
    "missing_information",
    "ambiguity",
    "conflict",
    "decision_required",
    "unsupported_assumption",
    "scope_risk",
]
GapSeverity = Literal["critical", "high", "medium", "low"]
GapStatus = Literal["open", "resolved", "dismissed"]

GAP_TYPES = frozenset(
    {
        "missing_information",
        "ambiguity",
        "conflict",
        "decision_required",
        "unsupported_assumption",
        "scope_risk",
    }
)
GAP_SEVERITIES = frozenset({"critical", "high", "medium", "low"})
GAP_STATUSES = frozenset({"open", "resolved", "dismissed"})


class GapValidationError(ValueError):
    """An approved Gap invariant was violated."""


@dataclass(frozen=True, slots=True)
class GapSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        offsets_absent = self.start_offset is None and self.end_offset is None
        offsets_present = self.start_offset is not None and self.end_offset is not None
        if not offsets_absent and not offsets_present:
            raise GapValidationError("Source Reference offsets must be provided together")
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
                raise GapValidationError("Source Reference offsets must be a half-open range")

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
class NewGap:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    gap_type: GapType
    severity: GapSeverity
    source_refs: tuple[GapSourceReference, ...]
    status: GapStatus = "open"
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_context_version(self.context_version)
        validate_gap_type(self.gap_type)
        validate_severity(self.severity)
        validate_status(self.status)
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(reference, GapSourceReference) for reference in self.source_refs
        ):
            raise GapValidationError("Gap source_refs must use the provenance contract")
        if self.resolved_at is not None:
            if self.resolved_at.tzinfo is None:
                raise GapValidationError("resolved_at must be timezone-aware")
            if self.status != "resolved":
                raise GapValidationError("resolved_at is only valid for a resolved Gap")


@dataclass(frozen=True, slots=True, kw_only=True)
class Gap(NewGap):
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        NewGap.__post_init__(self)
        if self.created_at.tzinfo is None:
            raise GapValidationError("created_at must be timezone-aware")
        if self.updated_at.tzinfo is None:
            raise GapValidationError("updated_at must be timezone-aware")


def validate_context_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GapValidationError("context_version must be at least one")
    return value


def validate_gap_type(value: str) -> GapType:
    if value not in GAP_TYPES:
        raise GapValidationError("Unsupported Gap type")
    return cast(GapType, value)


def validate_severity(value: str) -> GapSeverity:
    if value not in GAP_SEVERITIES:
        raise GapValidationError("Unsupported Gap severity")
    return cast(GapSeverity, value)


def validate_status(value: str) -> GapStatus:
    if value not in GAP_STATUSES:
        raise GapValidationError("Unsupported Gap status")
    return cast(GapStatus, value)
