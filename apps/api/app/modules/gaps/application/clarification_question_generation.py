from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.gaps.domain.clarification import normalize_question_text
from app.modules.gaps.domain.gap import GapSeverity, GapType


@dataclass(frozen=True, slots=True, kw_only=True)
class ClarificationQuestionGenerationRequest:
    gap_id: UUID
    gap_type: GapType
    severity: GapSeverity


@dataclass(frozen=True, slots=True, kw_only=True)
class ClarificationQuestionCandidate:
    question_text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_text", normalize_question_text(self.question_text))


class ClarificationQuestionGenerator(Protocol):
    """Provider-neutral AI-04 boundary; concrete real Providers remain deferred."""

    async def generate(
        self, request: ClarificationQuestionGenerationRequest
    ) -> ClarificationQuestionCandidate: ...
