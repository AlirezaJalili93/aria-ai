from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest
from aria_observability import TraceContext, bind_trace_context, create_event_logger

from app.modules.gaps.application.clarification_ports import (
    DuplicateClarificationRepositoryError,
)
from app.modules.gaps.application.clarification_service import (
    ClarificationDuplicate,
    ClarificationInvalidState,
    ClarificationService,
    ClarificationVersionConflict,
    CreateClarificationQuestionCommand,
    DismissGapCommand,
    EditClarificationQuestionCommand,
    ResolveClarificationCommand,
)
from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationResolution,
    ClarificationStatus,
    NewClarification,
    NewClarificationResolution,
)
from app.modules.gaps.domain.gap import Gap, GapStatus
from app.modules.identity.application.tenant_context import TenantContext
from app.shared.idempotency import IdempotencyReservation

SUBJECT, ACCOUNT_ID, PROJECT_ID, GAP_ID = uuid4(), uuid4(), uuid4(), uuid4()


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


class FakeClarificationRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.gap = Gap(
            id=GAP_ID,
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            context_version=1,
            gap_type="missing_information",
            severity="critical",
            status="open",
            source_refs=(),
            created_at=now,
            updated_at=now,
        )
        self.questions: dict[UUID, Clarification] = {}
        self.resolutions: dict[UUID, ClarificationResolution] = {}

    async def get_gap_for_update(self, **kwargs: object) -> Gap | None:
        if kwargs["gap_id"] != self.gap.id or kwargs["account_id"] != self.gap.account_id:
            return None
        return self.gap

    async def add_question(self, value: NewClarification) -> Clarification:
        if any(
            item.gap_id == value.gap_id
            and item.status == "open"
            and item.question_text == value.question_text
            for item in self.questions.values()
        ):
            raise DuplicateClarificationRepositoryError
        now = datetime.now(UTC)
        result = Clarification(
            **{field: getattr(value, field) for field in value.__dataclass_fields__},
            created_at=now,
            updated_at=now,
        )
        self.questions[result.id] = result
        return result

    async def get_question_by_id(
        self, *, clarification_id: UUID, **_: object
    ) -> Clarification | None:
        return self.questions.get(clarification_id)

    async def get_question_for_update(
        self, *, clarification_id: UUID, **_: object
    ) -> Clarification | None:
        return self.questions.get(clarification_id)

    async def update_question_text(self, **kwargs: object) -> Clarification | None:
        item = self.questions[UUID(str(kwargs["clarification_id"]))]
        if item.updated_at != kwargs["expected_updated_at"]:
            return None
        if any(
            other.id != item.id
            and other.status == "open"
            and other.question_text == kwargs["question_text"]
            for other in self.questions.values()
        ):
            raise DuplicateClarificationRepositoryError
        updated = replace(
            item,
            question_text=str(kwargs["question_text"]),
            updated_at=item.updated_at + timedelta(seconds=1),
        )
        self.questions[item.id] = updated
        return updated

    async def set_question_status(
        self, *, clarification_id: UUID, status: ClarificationStatus, **_: object
    ) -> Clarification:
        item = self.questions[clarification_id]
        updated = replace(
            item, status=status, updated_at=item.updated_at + timedelta(seconds=1)
        )
        self.questions[item.id] = updated
        return updated

    async def add_resolution(
        self, value: NewClarificationResolution
    ) -> ClarificationResolution:
        result = ClarificationResolution(
            **{field: getattr(value, field) for field in value.__dataclass_fields__},
            created_at=datetime.now(UTC),
        )
        self.resolutions[result.id] = result
        return result

    async def get_resolution_by_id(
        self, *, resolution_id: UUID, **_: object
    ) -> ClarificationResolution | None:
        return self.resolutions.get(resolution_id)

    async def has_open_questions(self, **_: object) -> bool:
        return any(item.status == "open" for item in self.questions.values())

    async def set_gap_status(
        self,
        *,
        expected_updated_at: datetime,
        status: GapStatus,
        resolved_at: datetime | None,
        **_: object,
    ) -> Gap | None:
        if self.gap.updated_at != expected_updated_at:
            return None
        self.gap = replace(
            self.gap,
            status=status,
            resolved_at=resolved_at,
            updated_at=self.gap.updated_at + timedelta(seconds=1),
        )
        return self.gap


class FakeUnitOfWork:
    def __init__(self, repository: FakeClarificationRepository) -> None:
        self.repository = repository
        self.idempotency = FakeIdempotencyRepository()
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _context() -> TenantContext:
    return TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )


def _service() -> tuple[ClarificationService, FakeUnitOfWork, StringIO]:
    repository = FakeClarificationRepository()
    unit_of_work = FakeUnitOfWork(repository)
    stream = StringIO()
    logger = create_event_logger(
        service="test",
        environment="test",
        app_version="test",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    return ClarificationService(lambda: unit_of_work, logger), unit_of_work, stream


def _trace():
    return bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    )


def _create(
    service: ClarificationService, *, text: str, key: str
) -> Clarification:
    with _trace():
        return asyncio.run(
            service.create_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                command=CreateClarificationQuestionCommand(text, key),
            )
        )


def test_exact_open_duplicate_is_rejected_without_logging_question_content() -> None:
    service, _, stream = _service()
    _create(service, text="مخاطب   اصلی کیست؟", key="one")
    with _trace(), pytest.raises(ClarificationDuplicate):
        asyncio.run(
            service.create_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                command=CreateClarificationQuestionCommand(
                    " مخاطب اصلی کیست؟ ", "two"
                ),
            )
        )
    assert "مخاطب" not in stream.getvalue()
    assert "clarification.duplicate_rejected" in stream.getvalue()


def test_answering_one_of_two_questions_does_not_resolve_gap() -> None:
    service, unit_of_work, stream = _service()
    first = _create(service, text="پرسش اول؟", key="one")
    _create(service, text="پرسش دوم؟", key="two")
    with _trace():
        resolution = asyncio.run(
            service.resolve_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=first.id,
                command=ResolveClarificationCommand(
                    "provided_information", "پاسخ محرمانه", "client", "resolution-one"
                ),
            )
        )
    assert unit_of_work.repository.questions[first.id].status == "answered"
    assert unit_of_work.repository.gap.status == "open"
    assert resolution.author_type == "client"
    assert resolution.author_id is None
    assert resolution.actor_id == SUBJECT
    assert "پاسخ محرمانه" not in stream.getvalue()


def test_last_terminal_question_resolves_gap_but_ignore_never_dismisses_it() -> None:
    service, unit_of_work, _ = _service()
    question = _create(service, text="این مورد نادیده گرفته شود؟", key="question")
    with _trace():
        asyncio.run(
            service.resolve_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=question.id,
                command=ResolveClarificationCommand("ignored", None, "user", "ignore"),
            )
        )
    assert unit_of_work.repository.questions[question.id].status == "ignored"
    assert unit_of_work.repository.gap.status == "resolved"
    assert unit_of_work.repository.gap.status != "dismissed"


def test_edit_uses_cas_and_terminal_question_is_immutable() -> None:
    service, unit_of_work, _ = _service()
    question = _create(service, text="پرسش قبلی؟", key="question")
    with _trace():
        edited = asyncio.run(
            service.edit_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=question.id,
                command=EditClarificationQuestionCommand(
                    "پرسش جدید؟", question.updated_at
                ),
            )
        )
    assert edited.question_text == "پرسش جدید؟"
    with _trace(), pytest.raises(ClarificationVersionConflict):
        asyncio.run(
            service.edit_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=question.id,
                command=EditClarificationQuestionCommand("تغییر stale", question.updated_at),
            )
        )
    unit_of_work.repository.questions[question.id] = replace(edited, status="answered")
    with _trace(), pytest.raises(ClarificationInvalidState):
        asyncio.run(
            service.edit_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=question.id,
                command=EditClarificationQuestionCommand(
                    "تغییر ممنوع", edited.updated_at
                ),
            )
        )


def test_gap_dismissal_is_a_separate_idempotent_command() -> None:
    service, unit_of_work, _ = _service()
    _create(service, text="پرسش باز؟", key="question")
    with _trace():
        asyncio.run(
            service.dismiss_gap(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                command=DismissGapCommand("dismiss-key"),
            )
        )
    assert unit_of_work.repository.gap.status == "dismissed"
    assert any(item.status == "open" for item in unit_of_work.repository.questions.values())

    request_hash = str(unit_of_work.idempotency.reserved["request_hash"])
    unit_of_work.idempotency.reservation = IdempotencyReservation(
        False, request_hash, 204, {"gap_id": str(GAP_ID)}
    )
    with _trace():
        asyncio.run(
            service.dismiss_gap(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                command=DismissGapCommand("dismiss-key"),
            )
        )


def test_resolved_gap_cannot_be_dismissed() -> None:
    service, unit_of_work, _ = _service()
    unit_of_work.repository.gap = replace(
        unit_of_work.repository.gap,
        status="resolved",
        resolved_at=datetime.now(UTC),
    )
    with _trace(), pytest.raises(ClarificationInvalidState):
        asyncio.run(
            service.dismiss_gap(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                command=DismissGapCommand("resolved-key"),
            )
        )


def test_accepted_assumption_requires_both_gap_invariants() -> None:
    service, unit_of_work, _ = _service()
    question = _create(service, text="این فرض پذیرفته شود؟", key="question")
    for gap in (
        replace(unit_of_work.repository.gap, gap_type="unsupported_assumption"),
        replace(
            unit_of_work.repository.gap,
            gap_type="conflict",
            suggested_resolution_type="validate_assumption",
        ),
    ):
        unit_of_work.repository.gap = gap
        with _trace(), pytest.raises(ClarificationInvalidState):
            asyncio.run(
                service.resolve_question(
                    _context(),
                    project_id=PROJECT_ID,
                    gap_id=GAP_ID,
                    clarification_id=question.id,
                    command=ResolveClarificationCommand(
                        "accepted_assumption", None, "user", str(gap.gap_type)
                    ),
                )
            )
    unit_of_work.repository.gap = replace(
        unit_of_work.repository.gap,
        gap_type="unsupported_assumption",
        suggested_resolution_type="validate_assumption",
    )
    with _trace():
        result = asyncio.run(
            service.resolve_question(
                _context(),
                project_id=PROJECT_ID,
                gap_id=GAP_ID,
                clarification_id=question.id,
                command=ResolveClarificationCommand(
                    "accepted_assumption", None, "user", "valid-assumption"
                ),
            )
        )
    assert result.resolution_type == "accepted_assumption"


def test_same_create_idempotency_replays_without_second_question() -> None:
    service, unit_of_work, _ = _service()
    existing = _create(service, text="پرسش؟", key="same")
    request_hash = str(unit_of_work.idempotency.reserved["request_hash"])
    unit_of_work.idempotency.reservation = IdempotencyReservation(
        False, request_hash, 201, {"clarification_id": str(existing.id)}
    )
    replayed = _create(service, text="پرسش؟", key="same")
    assert replayed.id == existing.id
    assert len(unit_of_work.repository.questions) == 1


def test_logs_contain_only_safe_identifiers_and_event_metadata() -> None:
    service, _, stream = _service()
    question = _create(service, text="متن بسیار محرمانه سؤال", key="safe")
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    created = next(event for event in events if event["event_name"] == "clarification.created")
    assert created["clarification_id"] == str(question.id)
    assert "متن بسیار محرمانه سؤال" not in stream.getvalue()
