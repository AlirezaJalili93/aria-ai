from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol
from uuid import UUID

from aria_observability import StructuredEventLogger

from app.application.parser_metrics import (
    ParserMetrics,
    validate_parse_outcome,
)


class ContextParseError(ValueError):
    """A documented Context parsing invariant was violated."""


class EmptyCanonicalTextError(ContextParseError):
    """The normalized text contains no content."""


@dataclass(frozen=True, slots=True)
class SourceVersionInput:
    """Provider-neutral input accepted by the text parser boundary."""

    id: UUID
    raw_text: str


@dataclass(frozen=True, slots=True)
class ParsedText:
    canonical_text: str
    metadata: dict[str, object]


class TextParser(Protocol):
    def parse(self, source_version: SourceVersionInput) -> ParsedText: ...


class CanonicalTextParser:
    """Apply the approved deterministic, non-destructive text normalization contract."""

    def __init__(
        self,
        *,
        metrics: ParserMetrics | None = None,
        event_logger: StructuredEventLogger | None = None,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._metrics = metrics
        self._event_logger = event_logger
        self._clock = clock

    def parse(self, source_version: SourceVersionInput) -> ParsedText:
        started_at = self._clock()
        self._emit("parser.parse_started", source_id=str(source_version.id), status="started")
        try:
            canonical_text = normalize_text(source_version.raw_text)
            if not canonical_text:
                raise EmptyCanonicalTextError
        except EmptyCanonicalTextError:
            self._record_failure(started_at, source_version, "empty")
            raise
        except ContextParseError:
            self._record_failure(started_at, source_version, "parse_error")
            raise

        duration_ms = (self._clock() - started_at) * 1000
        if self._metrics is not None:
            self._metrics.observe_parse_latency(
                duration_ms,
                parser_type="text",
                outcome="success",
            )
            self._metrics.record_parse_outcome(parser_type="text", outcome="success")
        self._emit(
            "parser.parse_succeeded",
            source_id=str(source_version.id),
            duration_ms=duration_ms,
            status="succeeded",
        )
        # Parser metadata is intentionally empty until a metadata contract is approved.
        return ParsedText(canonical_text=canonical_text, metadata={})

    def _record_failure(
        self,
        started_at: float,
        source_version: SourceVersionInput,
        failure_class: Literal["empty", "parse_error"],
    ) -> None:
        duration_ms = (self._clock() - started_at) * 1000
        if self._metrics is not None:
            self._metrics.observe_parse_latency(
                duration_ms,
                parser_type="text",
                outcome="failure",
            )
            validate_parse_outcome(outcome="failure", failure_class=failure_class)
            self._metrics.record_parse_outcome(
                parser_type="text",
                outcome="failure",
                failure_class=failure_class,
            )
        self._emit(
            "parser.parse_failed",
            level="ERROR",
            source_id=str(source_version.id),
            duration_ms=duration_ms,
            status="failed",
            error_code=failure_class,
        )

    def _emit(self, event_name: str, *, level: str = "INFO", **fields: object) -> None:
        if self._event_logger is not None:
            self._event_logger.emit(event_name, level=level, **fields)


def normalize_text(raw_text: str) -> str:
    """Normalize line endings, NFC and horizontal spacing without linguistic rewrites."""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        " " if character == "\t" or unicodedata.category(character) == "Zs" else character
        for character in text
    )
    lines = [_HORIZONTAL_SPACES.sub(" ", line).rstrip(" ") for line in text.split("\n")]
    return "\n".join(lines).strip()


_HORIZONTAL_SPACES = re.compile(r" +")
