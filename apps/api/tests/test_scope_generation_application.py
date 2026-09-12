from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.scope_generation import (
    SCOPE_CONTENT_SCHEMA_VERSION,
    ScopeDraftAlreadyExistsError,
    ScopeGenerationBlockedError,
    ScopeGenerationCommand,
    ScopeGenerationRequirement,
    ScopeGenerationSnapshot,
    ScopeGenerationUseCase,
    ScopeRepairPolicy,
)

ACCOUNT_ID = uuid4()
PROJECT_ID = uuid4()
JOB_ID = uuid4()
CORRELATION_ID = uuid4()


def _content() -> dict[str, object]:
    return {"schema_version": SCOPE_CONTENT_SCHEMA_VERSION, "sections": []}


def _command(*, repair_no: int = 0) -> ScopeGenerationCommand:
    return ScopeGenerationCommand(
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        job_id=JOB_ID,
        correlation_id=CORRELATION_ID,
        context_version=1,
        task_type="scope_generation",
        workflow_version="ai-05-v1",
        prompt_version="scope-prompt-v1",
        repair_prompt_version="scope-repair-v1",
        output_schema_version=SCOPE_CONTENT_SCHEMA_VERSION,
        repair_policy=ScopeRepairPolicy(
            policy_version="scope-repair-policy-v1", max_repairs=repair_no
        ),
        pricing_version="pricing-v1",
        output_schema={"type": "object"},
        routing_policy={"tier": "standard"},
        cost_budget={"max_usd": "1"},
        timeout_policy={"request_timeout_seconds": 5},
    )


def _snapshot(*, ready: bool = True) -> ScopeGenerationSnapshot:
    return ScopeGenerationSnapshot(
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=1,
        project_type="landing",
        context_items=({"id": str(uuid4()), "content": "متن"},),
        requirements=(
            ScopeGenerationRequirement(
                id=uuid4(), context_version=1, status="draft", payload={"title": "نیاز"}
            ),
            ScopeGenerationRequirement(
                id=uuid4(), context_version=1, status="confirmed", payload={"title": "نیاز قطعی"}
            ),
        ),
        resolved_gaps=(),
        remaining_non_blocking_gaps=(),
        ready_for_share=ready,
    )


class FakeAI:
    def __init__(self, responses: list[StructuredAIResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    async def execute_structured(self, **kwargs: object) -> StructuredAIResponse:
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeUsageLedger:
    def __init__(self) -> None:
        self.records = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class FakeReader:
    def __init__(self, snapshot: ScopeGenerationSnapshot | None) -> None:
        self.snapshot = snapshot

    async def resolve_exact(self, **_: object) -> ScopeGenerationSnapshot | None:
        return self.snapshot


class FakeValidator:
    def __init__(self, *, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.calls = 0

    def validate(self, content: object) -> dict[str, object]:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise ValueError("invalid candidate")
        assert isinstance(content, dict)
        return content


class FakeWriter:
    def __init__(self, *, existing: bool = False) -> None:
        self.existing = existing
        self.created: list[dict[str, object]] = []

    async def exists(self, **_: object) -> bool:
        return self.existing

    async def create_ai_draft(self, **kwargs: object) -> UUID:
        self.created.append(kwargs)
        return uuid4()


@dataclass
class FakeLogger:
    events: list[tuple[str, dict[str, object]]]

    def emit(self, event_name: str, **fields: object) -> None:
        self.events.append((event_name, fields))


def _response(data: object, *, prompt_version: str = "scope-prompt-v1") -> StructuredAIResponse:
    return StructuredAIResponse(
        data=data,
        provider="fake",
        model="fake-scope-v1",
        provider_request_id="req-1",
        input_tokens=10,
        cached_input_tokens=0,
        output_tokens=20,
        latency_ms=12.5,
        retry_no=0,
        workflow_version="ai-05-v1",
        prompt_version=prompt_version,
        estimated_cost=0.01,
        status="success",
    )


def _use_case(
    ai: FakeAI,
    reader: FakeReader,
    validator: FakeValidator,
    writer: FakeWriter,
    ledger: FakeUsageLedger,
    logger: FakeLogger,
) -> ScopeGenerationUseCase:
    return ScopeGenerationUseCase(
        snapshot_reader=reader,
        ai_execution=ai,
        usage_ledger=ledger,
        content_validator=validator,
        draft_writer=writer,
        event_logger=logger,
    )


def test_scope_generation_accepts_draft_and_confirmed_and_maps_usage() -> None:
    ai = FakeAI([_response(_content())])
    ledger = FakeUsageLedger()
    writer = FakeWriter()
    logger = FakeLogger([])
    result = asyncio.run(
        _use_case(ai, FakeReader(_snapshot()), FakeValidator(), writer, ledger, logger).execute(
            _command()
        )
    )

    assert result.context_version == 1
    assert len(writer.created) == 1
    assert len(ledger.records) == 1
    assert ai.calls[0]["input_context"]["requirements"][0]["status"] == "draft"
    assert ai.calls[0]["input_context"]["requirements"][1]["status"] == "confirmed"
    assert [event[0] for event in logger.events] == [
        "scope.generation_started",
        "scope.generation_completed",
    ]


def test_existing_draft_conflicts_before_ai_and_persistence() -> None:
    ai = FakeAI([_response(_content())])
    ledger = FakeUsageLedger()
    writer = FakeWriter(existing=True)
    logger = FakeLogger([])
    with pytest.raises(ScopeDraftAlreadyExistsError) as error:
        asyncio.run(
            _use_case(ai, FakeReader(_snapshot()), FakeValidator(), writer, ledger, logger).execute(
                _command()
            )
        )

    assert error.value.reason_code == "SCOPE_DRAFT_ALREADY_EXISTS"
    assert ai.calls == []
    assert writer.created == []
    assert ledger.records == []


def test_blocked_readiness_never_calls_ai() -> None:
    ai = FakeAI([_response(_content())])
    ledger = FakeUsageLedger()
    logger = FakeLogger([])
    with pytest.raises(ScopeGenerationBlockedError):
        asyncio.run(
            _use_case(
                ai,
                FakeReader(_snapshot(ready=False)),
                FakeValidator(),
                FakeWriter(),
                ledger,
                logger,
            ).execute(_command())
        )
    assert ai.calls == []
    assert ledger.records == []


def test_invalid_candidate_gets_one_repair_and_both_calls_are_metered() -> None:
    ai = FakeAI(
        [_response({"invalid": True}), _response(_content(), prompt_version="scope-repair-v1")]
    )
    ledger = FakeUsageLedger()
    validator = FakeValidator(fail_once=True)
    result = asyncio.run(
        _use_case(
            ai, FakeReader(_snapshot()), validator, FakeWriter(), ledger, FakeLogger([])
        ).execute(_command(repair_no=1))
    )

    assert result.repair_no == 1
    assert len(ai.calls) == 2
    assert len(ledger.records) == 2
    assert ai.calls[1]["prompt_version"] == "scope-repair-v1"


def test_no_repair_policy_fails_without_persisting() -> None:
    ai = FakeAI([_response({"invalid": True})])
    writer = FakeWriter()
    with pytest.raises(Exception) as error:
        asyncio.run(
            _use_case(
                ai,
                FakeReader(_snapshot()),
                FakeValidator(fail_once=True),
                writer,
                FakeUsageLedger(),
                FakeLogger([]),
            ).execute(_command())
        )
    assert getattr(error.value, "reason_code", None) == "scope_content_validation_failed"
    assert writer.created == []


@pytest.mark.parametrize("status", ["removed", "superseded"])
def test_scope_requirement_rejects_non_working_statuses(status: str) -> None:
    with pytest.raises(ValueError, match="draft or confirmed"):
        ScopeGenerationRequirement(
            id=uuid4(),
            context_version=1,
            status=status,
            payload={"title": "نباید وارد شود"},  # type: ignore[arg-type]
        )
