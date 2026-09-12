from __future__ import annotations

import re
import unicodedata


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
