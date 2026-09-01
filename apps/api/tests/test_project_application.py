from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.projects.application.ports import (
    ProjectRepository,
    ProjectRepositoryError,
    ProjectUnitOfWork,
)
from app.modules.projects.application.project_service import (
    CreateProjectCommand,
    ProjectApplicationService,
    ProjectPermissionDenied,
    ProjectReadOnly,
    UpdateProjectCommand,
)
from app.modules.projects.domain.project import (
    NewProject,
    Project,
    ProjectStatus,
    ProjectValidationError,
)


class FakeProjectRepository(ProjectRepository):
    def __init__(self) -> None:
        self.projects: dict[UUID, Project] = {}
        self.fail = False

    def _maybe_fail(self) -> None:
        if self.fail:
            raise ProjectRepositoryError

    async def add(self, project: NewProject) -> Project:
        self._maybe_fail()
        now = datetime.now(UTC)
        persisted = Project(
            id=project.id,
            account_id=project.account_id,
            owner_id=project.owner_id,
            title=project.title,
            project_type=project.project_type,
            status=project.status,
            current_context_version=project.current_context_version,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self.projects[project.id] = persisted
        return persisted

    async def get(self, *, account_id: UUID, project_id: UUID) -> Project | None:
        self._maybe_fail()
        project = self.projects.get(project_id)
        if project is None or project.account_id != account_id or project.is_deleted:
            return None
        return project

    async def get_including_deleted(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None:
        project = self.projects.get(project_id)
        return project if project is not None and project.account_id == account_id else None

    async def list_by_account(
        self,
        *,
        account_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[Project, ...]:
        rows = [
            project
            for project in self.projects.values()
            if project.account_id == account_id and not project.is_deleted
        ]
        return tuple(rows[offset : offset + limit])

    async def update(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        title: str | None = None,
        status: ProjectStatus | None = None,
    ) -> Project | None:
        project = await self.get(account_id=account_id, project_id=project_id)
        if project is None:
            return None
        updated = replace(
            project,
            title=title if title is not None else project.title,
            status=status if status is not None else project.status,
            updated_at=project.updated_at + timedelta(seconds=1),
        )
        self.projects[project_id] = updated
        return updated

    async def soft_delete(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
    ) -> Project | None:
        project = await self.get(account_id=account_id, project_id=project_id)
        if project is None:
            return None
        deleted = replace(project, deleted_at=datetime.now(UTC))
        self.projects[project_id] = deleted
        return deleted


class FakeProjectUnitOfWork(ProjectUnitOfWork):
    def __init__(self, repository: FakeProjectRepository) -> None:
        self._repository = repository
        self.commits = 0

    @property
    def repository(self) -> ProjectRepository:
        return self._repository

    async def __aenter__(self) -> FakeProjectUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback

    async def commit(self) -> None:
        self.commits += 1


def _context(*, status: str = "active", role: str = "owner") -> TenantContext:
    return TenantContext(
        subject_id=uuid4(),
        account_id=uuid4(),
        membership_id=uuid4(),
        role=role,  # type: ignore[arg-type]
        membership_status=status,  # type: ignore[arg-type]
    )


def _service(
    repository: FakeProjectRepository,
    stream: StringIO,
    project_id: UUID,
) -> ProjectApplicationService:
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return ProjectApplicationService(
        lambda: FakeProjectUnitOfWork(repository),
        logger,
        id_factory=lambda: project_id,
    )


def _trace() -> TraceContext:
    return TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))


def test_create_uses_active_tenant_subject_as_owner_and_emits_safe_event() -> None:
    repository = FakeProjectRepository()
    stream = StringIO()
    project_id = uuid4()
    context = _context()
    service = _service(repository, stream, project_id)

    async def scenario() -> Project:
        with bind_trace_context(_trace()):
            return await service.create(
                context,
                CreateProjectCommand(title="محرمانه", project_type="landing"),
            )

    project = asyncio.run(scenario())

    assert project.account_id == context.account_id
    assert project.owner_id == context.subject_id
    assert project.status == "draft"
    assert project.current_context_version == 0
    event = next(
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if json.loads(line)["event_name"] == "project.created"
    )
    assert event["account_id"] == str(context.account_id)
    assert event["project_id"] == str(project_id)
    assert event["correlation_id"]
    assert "محرمانه" not in stream.getvalue()
    assert str(context.subject_id) not in stream.getvalue()


@pytest.mark.parametrize("status", ["invited", "suspended"])
def test_create_rejects_non_active_membership_before_repository_write(status: str) -> None:
    repository = FakeProjectRepository()
    service = _service(repository, StringIO(), uuid4())

    async def scenario() -> None:
        with bind_trace_context(_trace()), pytest.raises(ProjectPermissionDenied):
            await service.create(
                _context(status=status),
                CreateProjectCommand(title="Project", project_type="corporate"),
            )

    asyncio.run(scenario())

    assert repository.projects == {}


def test_update_archive_and_soft_delete_emit_distinct_events_and_filter_deleted() -> None:
    repository = FakeProjectRepository()
    stream = StringIO()
    project_id = uuid4()
    context = _context(role="admin")
    service = _service(repository, stream, project_id)

    async def scenario() -> tuple[Project, Project, Project, Project | None, Project | None]:
        with bind_trace_context(_trace()):
            await service.create(
                context,
                CreateProjectCommand(title="Original", project_type="portfolio"),
            )
            updated = await service.update(
                context,
                project_id,
                UpdateProjectCommand(title="Updated", status="active"),
            )
            archived = await service.archive(context, project_id)
            deleted = await service.soft_delete(context, project_id)
        ordinary = await repository.get(account_id=context.account_id, project_id=project_id)
        internal = await repository.get_including_deleted(
            account_id=context.account_id,
            project_id=project_id,
        )
        return updated, archived, deleted, ordinary, internal

    updated, archived, deleted, ordinary, internal = asyncio.run(scenario())

    assert updated.title == "Updated"
    assert archived.status == "archived"
    assert deleted.is_deleted
    assert ordinary is None
    assert internal == deleted
    names = {json.loads(line)["event_name"] for line in stream.getvalue().splitlines()}
    assert {
        "project.created",
        "project.updated",
        "project.archived",
        "project.soft_deleted",
    } <= names


def test_archived_project_blocks_general_update_and_member_cannot_archive() -> None:
    repository = FakeProjectRepository()
    project_id = uuid4()
    owner = _context(role="owner")
    service = _service(repository, StringIO(), project_id)

    async def scenario() -> None:
        with bind_trace_context(_trace()):
            await service.create(
                owner,
                CreateProjectCommand(title="Project", project_type="landing"),
            )
            await service.archive(owner, project_id)
            with pytest.raises(ProjectReadOnly):
                await service.update(owner, project_id, UpdateProjectCommand(title="Blocked"))
            member = replace(owner, role="member")
            with pytest.raises(ProjectPermissionDenied):
                await service.archive(member, project_id)
            with pytest.raises(ProjectPermissionDenied):
                await service.update(
                    member,
                    project_id,
                    UpdateProjectCommand(status="archived"),
                )

    asyncio.run(scenario())


def test_empty_update_is_rejected_before_repository_access() -> None:
    repository = FakeProjectRepository()
    service = _service(repository, StringIO(), uuid4())

    async def scenario() -> None:
        with pytest.raises(ProjectValidationError):
            await service.update(_context(), uuid4(), UpdateProjectCommand())

    asyncio.run(scenario())
    assert repository.projects == {}


def test_declared_repository_failure_emits_safe_operational_event() -> None:
    repository = FakeProjectRepository()
    repository.fail = True
    stream = StringIO()
    context = _context()
    service = _service(repository, stream, uuid4())

    async def scenario() -> None:
        with bind_trace_context(_trace()), pytest.raises(ProjectRepositoryError):
            await service.create(
                context,
                CreateProjectCommand(title="never-log-this", project_type="landing"),
            )

    asyncio.run(scenario())

    event = next(
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if json.loads(line)["event_name"] == "project.repository_failed"
    )
    assert event["error_code"] == "PROJECT_REPOSITORY_FAILURE"
    assert event["operation"] == "create"
    assert "never-log-this" not in stream.getvalue()
