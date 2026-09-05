from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from app.application.context_parser import CanonicalTextParser, SourceVersionInput
from app.application.parser_metrics import validate_parse_outcome


@dataclass
class _MetricsSpy:
    latencies: list[tuple[float, str, str]] = field(default_factory=list)
    queue_waits: list[tuple[float, str]] = field(default_factory=list)
    outcomes: list[tuple[str, str, str | None]] = field(default_factory=list)

    def observe_parse_latency(self, duration_ms: float, *, parser_type: str, outcome: str) -> None:
        self.latencies.append((duration_ms, parser_type, outcome))

    def observe_queue_wait(self, duration_ms: float, *, parser_type: str) -> None:
        self.queue_waits.append((duration_ms, parser_type))

    def record_parse_outcome(
        self, *, parser_type: str, outcome: str, failure_class: str | None = None
    ) -> None:
        self.outcomes.append((parser_type, outcome, failure_class))


def test_parser_records_latency_and_success_outcome_without_identifiers_in_metrics() -> None:
    ticks = iter([10.0, 10.125])
    metrics = _MetricsSpy()

    result = CanonicalTextParser(metrics=metrics, clock=lambda: next(ticks)).parse(
        SourceVersionInput(id=uuid4(), raw_text="متن")
    )

    assert result.canonical_text == "متن"
    assert metrics.latencies == [(125.0, "text", "success")]
    assert metrics.outcomes == [("text", "success", None)]
    assert metrics.queue_waits == []


def test_parser_records_empty_failure_with_bounded_class() -> None:
    ticks = iter([20.0, 20.25])
    metrics = _MetricsSpy()

    with pytest.raises(ValueError):
        CanonicalTextParser(metrics=metrics, clock=lambda: next(ticks)).parse(
            SourceVersionInput(id=uuid4(), raw_text=" \t\n")
        )

    assert metrics.latencies == [(250.0, "text", "failure")]
    assert metrics.outcomes == [("text", "failure", "empty")]


def test_failure_class_contract_rejects_unbounded_or_mismatched_values() -> None:
    with pytest.raises(ValueError):
        validate_parse_outcome(outcome="success", failure_class="empty")
    with pytest.raises(ValueError):
        validate_parse_outcome(outcome="failure", failure_class=None)
    with pytest.raises(ValueError):
        validate_parse_outcome(outcome="failure", failure_class="free_text")  # type: ignore[arg-type]
