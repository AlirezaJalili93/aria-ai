from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.requirements.application.ports import RequirementProvenanceTarget
from app.modules.requirements.application.requirement_service import (
    PersistRequirementUseCase,
    RequirementContextVersionError,
    RequirementProvenanceError,
)
from app.modules.requirements.domain.requirement import (
    NewRequirement,
    Requirement,
    RequirementSourceReference,
)


class FakeRequirementRepository:
    def __init__(self, *, current_context_version: int | None) -> None:
        self.current_context_version = current_context_version
        self.provenance: dict[tuple[UUID, UUID], RequirementProvenanceTarget] = {}
        self.added: list[NewRequirement] = []

    async def get_project_current_context_version(
        self, *, account_id: UUID, project_id: UUID
    ) -> int | None:
        del account_id, project_id
        return self.current_context_version

    async def resolve_provenance(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        source_id: UUID,
        source_version_id: UUID,
    ) -> RequirementProvenanceTarget | None:
        del account_id, project_id
        return self.provenance.get((source_id, source_version_id))

    async def add(self, requirement: NewRequirement) -> Requirement:
        self.added.append(requirement)
        now = datetime.now(UTC)
        return Requirement(
            id=requirement.id,
            account_id=requirement.account_id,
            project_id=requirement.project_id,
            context_version=requirement.context_version,
            category=requirement.category,
            title=requirement.title,
            description=requirement.description,
            priority=requirement.priority,
            status=requirement.status,
            source_refs=requirement.source_refs,
            confidence=requirement.confidence,
            created_by_type=requirement.created_by_type,
            created_by=requirement.created_by,
            created_at=now,
            updated_at=now,
        )


class FakeRequirementUnitOfWork:
    def __init__(self, repository: FakeRequirementRepository) -> None:
        self.repository = repository
        self.committed = False

    async def __aenter__(self) -> FakeRequirementUnitOfWork:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def commit(self) -> None:
        self.committed = True


def _requirement(**overrides: object) -> NewRequirement:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "context_version": 1,
        "category": "business",
        "title": "عنوان محرمانه مشتری",
        "description": "شرح محرمانه مشتری",
        "priority": "should",
        "source_refs": (),
        "confidence": None,
        "created_by_type": "ai",
        "created_by": None,
    }
    values.update(overrides)
    return NewRequirement(**values)  # type: ignore[arg-type]


def _service(
    repository: FakeRequirementRepository, stream: StringIO | None = None
) -> tuple[PersistRequirementUseCase, FakeRequirementUnitOfWork, StringIO]:
    output = stream or StringIO()
    unit_of_work = FakeRequirementUnitOfWork(repository)
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=output,
    )
    return PersistRequirementUseCase(lambda: unit_of_work, logger), unit_of_work, output


def test_persistence_accepts_an_existing_context_version_and_logs_no_content() -> None:
    repository = FakeRequirementRepository(current_context_version=3)
    service, unit_of_work, stream = _service(repository)
    requirement = _requirement(context_version=2)

    with bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    ):
        persisted = asyncio.run(service.execute(requirement))

    assert persisted.id == requirement.id
    assert repository.added == [requirement]
    assert unit_of_work.committed
    event = json.loads(stream.getvalue())
    assert event["event_name"] == "requirement.created"
    assert event["account_id"] == str(requirement.account_id)
    assert event["project_id"] == str(requirement.project_id)
    assert event["requirement_id"] == str(requirement.id)
    assert event["priority"] == requirement.priority
    assert event["created_by_type"] == requirement.created_by_type
    assert requirement.title not in stream.getvalue()
    assert requirement.description not in stream.getvalue()
    assert "source_refs" not in stream.getvalue()


@pytest.mark.parametrize("current_context_version", [None, 0, 1])
def test_persistence_rejects_missing_or_future_project_context(
    current_context_version: int | None,
) -> None:
    repository = FakeRequirementRepository(current_context_version=current_context_version)
    service, unit_of_work, _ = _service(repository)

    with pytest.raises(RequirementContextVersionError):
        asyncio.run(service.execute(_requirement(context_version=2)))

    assert repository.added == []
    assert not unit_of_work.committed


def test_persistence_requires_ready_same_tenant_provenance_with_valid_offsets() -> None:
    requirement = _requirement()
    source_ref = RequirementSourceReference(uuid4(), uuid4(), 0, 5)
    requirement = _requirement(
        id=requirement.id,
        account_id=requirement.account_id,
        project_id=requirement.project_id,
        source_refs=(source_ref,),
    )
    repository = FakeRequirementRepository(current_context_version=1)
    service, unit_of_work, _ = _service(repository)

    with bind_trace_context(
        TraceContext(correlation_id=str(uuid4()))
    ), pytest.raises(RequirementProvenanceError):
        asyncio.run(service.execute(requirement))

    repository.provenance[(source_ref.source_id, source_ref.source_version_id)] = (
        RequirementProvenanceTarget(
            account_id=requirement.account_id,
            project_id=requirement.project_id,
            source_id=source_ref.source_id,
            source_version_id=source_ref.source_version_id,
            canonical_text_length=4,
        )
    )
    with bind_trace_context(
        TraceContext(correlation_id=str(uuid4()))
    ), pytest.raises(RequirementProvenanceError):
        asyncio.run(service.execute(requirement))

    assert repository.added == []
    assert not unit_of_work.committed
