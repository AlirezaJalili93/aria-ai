from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.projects.domain.project import (
    PROJECT_STATUSES,
    PROJECT_TYPES,
    Project,
    ProjectValidationError,
)


def _project(**overrides: object) -> Project:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "owner_id": uuid4(),
        "title": "پروژه نمونه",
        "project_type": "landing",
        "status": "draft",
        "current_context_version": 0,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    values.update(overrides)
    return Project(**values)  # type: ignore[arg-type]


def test_project_accepts_only_the_documented_type_and_status_vocabularies() -> None:
    assert {"landing", "corporate", "portfolio"} == PROJECT_TYPES
    assert {
        "draft",
        "active",
        "awaiting_approval",
        "approved",
        "generating",
        "delivered",
        "archived",
    } == PROJECT_STATUSES
    for project_type in PROJECT_TYPES:
        assert _project(project_type=project_type).project_type == project_type
    for status in PROJECT_STATUSES:
        assert _project(status=status).status == status


@pytest.mark.parametrize(
    "overrides",
    [
        {"project_type": "shop"},
        {"status": "deleted"},
        {"current_context_version": -1},
        {"title": "x" * 256},
        {"created_at": datetime.now()},
    ],
)
def test_project_rejects_only_explicit_field_constraint_violations(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ProjectValidationError):
        _project(**overrides)


def test_project_title_is_preserved_without_undocumented_normalization() -> None:
    title = "  عنوان مستند  "
    assert _project(title=title).title == title


def test_archived_or_deleted_projects_are_read_only() -> None:
    assert _project(status="archived").is_read_only
    assert _project(deleted_at=datetime.now(UTC)).is_read_only
    assert not _project(status="active").is_read_only
