from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.gaps.application.clarification_question_generation import (
    ClarificationQuestionCandidate,
    ClarificationQuestionGenerationRequest,
    ClarificationQuestionGenerator,
)
from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationResolution,
    ClarificationValidationError,
    NewClarification,
    NewClarificationResolution,
)


def _new_clarification(**overrides: object) -> NewClarification:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "gap_id": uuid4(),
        "question_text": "  هدف   اصلی\r\nپروژه چیست؟  ",
        "created_by_type": "user",
        "created_by": uuid4(),
    }
    values.update(overrides)
    return NewClarification(**values)  # type: ignore[arg-type]


def _new_resolution(**overrides: object) -> NewClarificationResolution:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "gap_id": uuid4(),
        "clarification_id": uuid4(),
        "resolution_type": "provided_information",
        "answer_text": "  پاسخ   مشتری  ",
        "author_type": "client",
        "author_id": None,
        "actor_id": uuid4(),
    }
    values.update(overrides)
    return NewClarificationResolution(**values)  # type: ignore[arg-type]


def test_question_uses_approved_normalization_and_preserves_persian_zwnj() -> None:
    value = _new_clarification(question_text="  وب\u200cسایت\tشرکتی\r\n\r\n  آماده است؟  ")
    assert value.question_text == "وب\u200cسایت شرکتی\n\n آماده است؟"


@pytest.mark.parametrize("value", ["", "  \t\r\n ", "\u00a0"])
def test_question_rejects_empty_normalized_text(value: str) -> None:
    with pytest.raises(ClarificationValidationError):
        _new_clarification(question_text=value)


def test_user_question_requires_creator_and_persisted_times_are_aware() -> None:
    with pytest.raises(ClarificationValidationError):
        _new_clarification(created_by=None)
    now = datetime.now(UTC)
    value = _new_clarification()
    persisted = Clarification(
        **{field: getattr(value, field) for field in value.__dataclass_fields__},
        created_at=now,
        updated_at=now,
    )
    assert persisted.status == "open"


@pytest.mark.parametrize("resolution_type", ["provided_information", "internal_decision"])
def test_answering_resolutions_require_non_empty_text(resolution_type: str) -> None:
    with pytest.raises(ClarificationValidationError):
        _new_resolution(resolution_type=resolution_type, answer_text=" \t ")
    assert _new_resolution(
        resolution_type=resolution_type, answer_text=" پاسخ "
    ).answer_text == "پاسخ"


@pytest.mark.parametrize("resolution_type", ["accepted_assumption", "ignored"])
def test_action_only_resolutions_forbid_synthetic_answer_text(resolution_type: str) -> None:
    with pytest.raises(ClarificationValidationError):
        _new_resolution(resolution_type=resolution_type, answer_text="accepted")
    assert _new_resolution(resolution_type=resolution_type, answer_text=None).answer_text is None


def test_resolution_forbids_system_authorship_and_persisted_time_is_aware() -> None:
    with pytest.raises(ClarificationValidationError):
        _new_resolution(author_type="system")
    value = _new_resolution()
    persisted = ClarificationResolution(
        **{field: getattr(value, field) for field in value.__dataclass_fields__},
        created_at=datetime.now(UTC),
    )
    assert persisted.author_type == "client"


class FakeDeterministicQuestionGenerator:
    async def generate(
        self, request: ClarificationQuestionGenerationRequest
    ) -> ClarificationQuestionCandidate:
        del request
        return ClarificationQuestionCandidate(question_text=" مخاطب اصلی چه کسی است؟ ")


def test_fake_provider_satisfies_provider_neutral_ai04_port() -> None:
    provider: ClarificationQuestionGenerator = FakeDeterministicQuestionGenerator()
    request = ClarificationQuestionGenerationRequest(
        gap_id=uuid4(), gap_type="missing_information", severity="critical"
    )

    import asyncio

    candidate = asyncio.run(provider.generate(request))
    assert candidate.question_text == "مخاطب اصلی چه کسی است؟"
