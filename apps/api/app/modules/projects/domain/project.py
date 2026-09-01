from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

ProjectType = Literal["landing", "corporate", "portfolio"]
ProjectStatus = Literal[
    "draft",
    "active",
    "awaiting_approval",
    "approved",
    "generating",
    "delivered",
    "archived",
]

PROJECT_TYPES = frozenset({"landing", "corporate", "portfolio"})
PROJECT_STATUSES = frozenset(
    {
        "draft",
        "active",
        "awaiting_approval",
        "approved",
        "generating",
        "delivered",
        "archived",
    }
)
MAX_PROJECT_TITLE_LENGTH = 255


class ProjectValidationError(ValueError):
    """A documented Project field constraint was violated."""


@dataclass(frozen=True, slots=True)
class NewProject:
    id: UUID
    account_id: UUID
    owner_id: UUID
    title: str
    project_type: ProjectType
    status: ProjectStatus = "draft"
    current_context_version: int = 0

    def __post_init__(self) -> None:
        validate_project_title(self.title)
        validate_project_type(self.project_type)
        validate_project_status(self.status)
        if self.current_context_version < 0:
            raise ProjectValidationError("current_context_version must be non-negative")


@dataclass(frozen=True, slots=True)
class Project:
    id: UUID
    account_id: UUID
    owner_id: UUID
    title: str
    project_type: ProjectType
    status: ProjectStatus
    current_context_version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    def __post_init__(self) -> None:
        validate_project_title(self.title)
        validate_project_type(self.project_type)
        validate_project_status(self.status)
        if self.current_context_version < 0:
            raise ProjectValidationError("current_context_version must be non-negative")
        for value in (self.created_at, self.updated_at, self.deleted_at):
            if value is not None and value.tzinfo is None:
                raise ProjectValidationError("Project timestamps must be timezone-aware")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_read_only(self) -> bool:
        return self.status == "archived" or self.is_deleted


def validate_project_title(value: str) -> str:
    if not isinstance(value, str):
        raise ProjectValidationError("Project title must be text")
    if len(value) > MAX_PROJECT_TITLE_LENGTH:
        raise ProjectValidationError("Project title exceeds VARCHAR(255)")
    return value


def validate_project_type(value: str) -> ProjectType:
    if value not in PROJECT_TYPES:
        raise ProjectValidationError("Unsupported Project type")
    return cast(ProjectType, value)


def validate_project_status(value: str) -> ProjectStatus:
    if value not in PROJECT_STATUSES:
        raise ProjectValidationError("Unsupported Project status")
    return cast(ProjectStatus, value)
