from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.identity.application.tenant_context import TenantContext
from app.modules.requirements.application.requirement_crud_service import (
    CreateManualRequirementCommand,
    RequirementContextRequired,
    RequirementCrudService,
    RequirementIdempotencyConflict,
    RequirementInvalidState,
    RequirementVersionConflict,
    UpdateRequirementCommand,
)
from app.modules.requirements.domain.requirement import NewRequirement, Requirement
from app.shared.idempotency import IdempotencyReservation


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.reservation = IdempotencyReservation(True, "", None, None)
        self.reserved: dict[str, object] | None = None
        self.completed: dict[str, object] | None = None

    async def reserve(self, **kwargs: object) -> IdempotencyReservation:
        self.reserved = kwargs
        if self.reservation.acquired:
            return IdempotencyReservation(True, str(kwargs["request_hash"]), None, None)
        return self.reservation

    async def complete(self, **kwargs: object) -> None:
        self.completed = kwargs


class FakeRequirementCrudRepository:
    def __init__(self, *, context_version: int | None = 2) -> None:
        self.context_version = context_version
        self.rows: dict[UUID, Requirement] = {}
        self.added: list[NewRequirement] = []
        self.list_result: tuple[Requirement, ...] | None = ()
        self.updated: list[dict[str, object]] = []
        self.force_update_conflict = False

    async def get_project_current_context_version(self, **_: object) -> int | None:
        return self.context_version

    async def add(self, value: NewRequirement) -> Requirement:
        self.added.append(value)
        now = datetime.now(UTC)
        persisted = Requirement(
            **{
                field: getattr(value, field)
                for field in value.__dataclass_fields__
            },
            created_at=now,
            updated_at=now,
        )
        self.rows[persisted.id] = persisted
        return persisted

    async def get_by_id(self, *, requirement_id: UUID, **_: object) -> Requirement | None:
        return self.rows.get(requirement_id)

    async def list_by_project(self, **_: object) -> tuple[Requirement, ...] | None:
        return self.list_result

    async def get_for_update(
        self, *, requirement_id: UUID, **_: object
    ) -> Requirement | None:
        return self.rows.get(requirement_id)

    async def update_mutable(self, **kwargs: object) -> Requirement | None:
        self.updated.append(kwargs)
        if self.force_update_conflict:
            return None
        requirement_id = UUID(str(kwargs["requirement_id"]))
        current = self.rows[requirement_id]
        persisted = replace(
            current,
            title=str(kwargs["title"]),
            description=str(kwargs["description"]),
            priority=kwargs["priority"],  # type: ignore[arg-type]
            acceptance_note=kwargs["acceptance_note"],  # type: ignore[arg-type]
            status=kwargs["status"],  # type: ignore[arg-type]
            updated_at=current.updated_at + timedelta(seconds=1),
        )
        self.rows[requirement_id] = persisted
        return persisted


class FakeRequirementCrudUnitOfWork:
    def __init__(self, repository: FakeRequirementCrudRepository) -> None:
        self.repository = repository
        self.idempotency = FakeIdempotencyRepository()
        self.committed = False

    async def __aenter__(self) -> FakeRequirementCrudUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


SUBJECT, ACCOUNT_ID, PROJECT_ID = uuid4(), uuid4(), uuid4()


def _context() -> TenantContext:
    return TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _requirement(*, status: str = "draft") -> Requirement:
    now = datetime.now(UTC)
    return Requirement(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=2,
        category="functional",
        title="عنوان محرمانه",
        description="شرح محرمانه",
        priority="must",
        source_refs=(),
        confidence=None,
        created_by_type="user",
        created_by=SUBJECT,
        status=status,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )


def _service(
    repository: FakeRequirementCrudRepository,
) -> tuple[RequirementCrudService, FakeRequirementCrudUnitOfWork, StringIO]:
    unit_of_work = FakeRequirementCrudUnitOfWork(repository)
    stream = StringIO()
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return RequirementCrudService(lambda: unit_of_work, logger), unit_of_work, stream


def _create_command(**overrides: object) -> CreateManualRequirementCommand:
    values: dict[str, object] = {
        "title": "عنوان محرمانه",
        "description": "شرح محرمانه",
        "category": "functional",
        "priority": "must",
        "idempotency_key": "manual-1",
    }
    values.update(overrides)
    return CreateManualRequirementCommand(**values)  # type: ignore[arg-type]


def test_manual_create_binds_current_context_and_user_identity_atomically() -> None:
    repository = FakeRequirementCrudRepository(context_version=3)
    service, unit_of_work, stream = _service(repository)
    command = _create_command()

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        persisted = asyncio.run(
            service.create_manual(_context(), project_id=PROJECT_ID, command=command)
        )

    assert persisted.context_version == 3
    assert persisted.status == "draft"
    assert persisted.created_by_type == "user"
    assert persisted.created_by == SUBJECT
    assert persisted.source_refs == ()
    assert persisted.confidence is None
    assert persisted.is_unsupported is False
    assert unit_of_work.committed
    assert unit_of_work.idempotency.completed is not None
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "requirement.added"
    assert command.title not in stream.getvalue()
    assert command.description not in stream.getvalue()


def test_manual_create_replays_same_resource_and_rejects_changed_payload() -> None:
    repository = FakeRequirementCrudRepository()
    existing = _requirement()
    repository.rows[existing.id] = existing
    service, unit_of_work, _ = _service(repository)
    command = _create_command()

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        first_hash = asyncio.run(
            service.create_manual(_context(), project_id=PROJECT_ID, command=command)
        )
    assert first_hash.id in repository.rows
    request_hash = str(unit_of_work.idempotency.reserved["request_hash"])
    repository.added.clear()
    unit_of_work.idempotency.reservation = IdempotencyReservation(
        False,
        request_hash,
        201,
        {"requirement_id": str(existing.id)},
    )
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        replayed = asyncio.run(
            service.create_manual(_context(), project_id=PROJECT_ID, command=command)
        )
    assert replayed.id == existing.id
    assert repository.added == []

    unit_of_work.idempotency.reservation = IdempotencyReservation(
        False,
        "different-hash",
        201,
        {"requirement_id": str(existing.id)},
    )
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(RequirementIdempotencyConflict):
        asyncio.run(service.create_manual(_context(), project_id=PROJECT_ID, command=command))


def test_manual_create_requires_existing_context_version() -> None:
    repository = FakeRequirementCrudRepository(context_version=0)
    service, unit_of_work, _ = _service(repository)

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(RequirementContextRequired):
        asyncio.run(
            service.create_manual(
                _context(), project_id=PROJECT_ID, command=_create_command()
            )
        )

    assert repository.added == []
    assert not unit_of_work.committed


def test_update_uses_cas_and_demotes_edited_confirmed_requirement() -> None:
    repository = FakeRequirementCrudRepository()
    current = _requirement(status="confirmed")
    repository.rows[current.id] = current
    service, unit_of_work, stream = _service(repository)

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        persisted = asyncio.run(
            service.update(
                _context(),
                project_id=PROJECT_ID,
                requirement_id=current.id,
                command=UpdateRequirementCommand(
                    expected_updated_at=current.updated_at,
                    title="عنوان جدید",
                    acceptance_note=None,
                    acceptance_note_set=True,
                ),
            )
        )

    assert persisted.status == "draft"
    assert persisted.title == "عنوان جدید"
    assert persisted.acceptance_note is None
    assert repository.updated
    assert json.loads(stream.getvalue())["event_name"] == "requirement.edited"
    assert "عنوان جدید" not in stream.getvalue()


def test_confirm_requires_draft_and_stale_update_is_distinct() -> None:
    repository = FakeRequirementCrudRepository()
    current = _requirement()
    repository.rows[current.id] = current
    service, _, _ = _service(repository)
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        confirmed = asyncio.run(
            service.update(
                _context(),
                project_id=PROJECT_ID,
                requirement_id=current.id,
                command=UpdateRequirementCommand(
                    expected_updated_at=current.updated_at, status="confirmed"
                ),
            )
        )
    assert confirmed.status == "confirmed"

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(RequirementInvalidState):
        asyncio.run(
            service.update(
                _context(),
                project_id=PROJECT_ID,
                requirement_id=current.id,
                command=UpdateRequirementCommand(
                    expected_updated_at=confirmed.updated_at, status="confirmed"
                ),
            )
        )

    draft = _requirement()
    repository.rows[draft.id] = draft
    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(RequirementVersionConflict):
        asyncio.run(
            service.update(
                _context(),
                project_id=PROJECT_ID,
                requirement_id=draft.id,
                command=UpdateRequirementCommand(
                    expected_updated_at=draft.updated_at - timedelta(seconds=1),
                    title="stale",
                ),
            )
        )


def test_remove_is_soft_and_draft_only() -> None:
    repository = FakeRequirementCrudRepository()
    draft = _requirement()
    repository.rows[draft.id] = draft
    confirmed = _requirement(status="confirmed")
    repository.rows[confirmed.id] = confirmed
    service, _, _ = _service(repository)

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        asyncio.run(
            service.remove_draft(
                _context(), project_id=PROJECT_ID, requirement_id=draft.id
            )
        )
    assert repository.rows[draft.id].status == "removed"

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ), pytest.raises(RequirementInvalidState):
        asyncio.run(
            service.remove_draft(
                _context(), project_id=PROJECT_ID, requirement_id=confirmed.id
            )
        )
