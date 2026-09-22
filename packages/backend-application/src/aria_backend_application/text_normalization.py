from __future__ import annotations

import re
import unicodedata

TEXT_CONTEXT_MAX_CHARACTERS = 50_000
_ALLOWED_TEXT_CONTROLS = frozenset({"\t", "\n", "\r"})


class TextSafetyValidationError(ValueError):
    """Stored or submitted text violates the approved shared safety contract."""


def validate_text_safety(value: str) -> str:
    if not value:
        raise TextSafetyValidationError("Text Context cannot be blank")
    if len(value) > TEXT_CONTEXT_MAX_CHARACTERS:
        raise TextSafetyValidationError("Text Context exceeds the approved character limit")
    if any(
        character not in _ALLOWED_TEXT_CONTROLS and unicodedata.category(character) == "Cc"
        for character in value
    ):
        raise TextSafetyValidationError("Text Context contains a disallowed control character")
    return value


def normalize_text(raw_text: str) -> str:
    """Apply the approved deterministic, non-destructive text normalization contract."""

    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    text = "".join(
        " " if character == "\t" or unicodedata.category(character) == "Zs" else character
        for character in text
    )
    lines = [_HORIZONTAL_SPACES.sub(" ", line).rstrip(" ") for line in text.split("\n")]
    return "\n".join(lines).strip()


_HORIZONTAL_SPACES = re.compile(r" +")
