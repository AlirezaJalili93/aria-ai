from __future__ import annotations

from typing import Literal, Protocol

ParserType = Literal["text"]
ParserOutcome = Literal["success", "failure"]
FailureClass = Literal["unsupported_format", "empty", "parse_error", "timeout"]
_ALLOWED_FAILURE_CLASSES = frozenset(
    {"unsupported_format", "empty", "parse_error", "timeout"}
)


class ParserMetrics(Protocol):
    """Provider-neutral metrics sink for parser measurements."""

    def observe_parse_latency(
        self,
        duration_ms: float,
        *,
        parser_type: ParserType,
        outcome: ParserOutcome,
    ) -> None: ...

    def observe_queue_wait(self, duration_ms: float, *, parser_type: ParserType) -> None: ...

    def record_parse_outcome(
        self,
        *,
        parser_type: ParserType,
        outcome: ParserOutcome,
        failure_class: FailureClass | None = None,
    ) -> None: ...


def validate_parse_outcome(
    *, outcome: ParserOutcome, failure_class: FailureClass | None
) -> None:
    """Keep the bounded failure label contract valid before a sink receives it."""

    if outcome == "success" and failure_class is not None:
        raise ValueError("success outcomes cannot have a failure_class")
    if outcome == "failure" and failure_class is None:
        raise ValueError("failure outcomes require a failure_class")
    if failure_class is not None and failure_class not in _ALLOWED_FAILURE_CLASSES:
        raise ValueError("failure_class is outside the approved bounded set")
