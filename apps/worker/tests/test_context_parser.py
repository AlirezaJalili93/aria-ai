from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.context_parser import (
    CanonicalTextParser,
    EmptyCanonicalTextError,
    ParsedText,
    SourceVersionInput,
    normalize_text,
)


def test_normalization_applies_approved_order_without_linguistic_rewrites() -> None:
    raw_text = "  ي\u0654   ك\t\u00a0\r\n\r\n  نیم\u200cفاصله\u200d  \n"

    assert normalize_text(raw_text) == "ئ ك\n\n نیم\u200cفاصله\u200d"


def test_normalization_preserves_internal_blank_lines_and_line_order() -> None:
    assert normalize_text("one  \r\n\r\ntwo\rthree") == "one\n\ntwo\nthree"


def test_parser_rejects_empty_content_after_normalization() -> None:
    parser = CanonicalTextParser()

    with pytest.raises(EmptyCanonicalTextError):
        parser.parse(SourceVersionInput(id=uuid4(), raw_text="\t\r\n   \n"))


def test_parser_returns_canonical_text_and_contract_empty_metadata() -> None:
    parsed = CanonicalTextParser().parse(
        SourceVersionInput(id=uuid4(), raw_text="  متن  \r\n دقیق  ")
    )

    assert parsed == ParsedText(canonical_text="متن\n دقیق", metadata={})
