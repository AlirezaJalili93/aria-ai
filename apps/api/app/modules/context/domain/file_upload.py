from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from unicodedata import category, normalize

from app.modules.context.domain.context_source import (
    ContextSourceValidationError,
    validate_text_context,
)

TXT_UPLOAD_MAX_BYTES = 200_000
TXT_UPLOAD_MAX_CHARACTERS = 50_000
TXT_UPLOAD_MIME_TYPE = "text/plain"


class FileUploadValidationError(ValueError):
    """A TXT upload violates the frozen D03 content or filename contract."""


class UnsupportedFileTypeError(FileUploadValidationError):
    """The declared file extension or normalized MIME type is unsupported."""


class FileTooLargeError(FileUploadValidationError):
    """The encoded upload exceeds the approved byte limit."""


@dataclass(frozen=True, slots=True)
class ValidatedTextUpload:
    original_name: str
    mime_type: str
    content: bytes
    content_digest: str


def validate_text_upload(
    *,
    filename: str,
    declared_mime_type: str | None,
    content: bytes,
) -> ValidatedTextUpload:
    original_name = validate_upload_filename(filename)
    mime_type = normalize_declared_mime_type(declared_mime_type)
    if not original_name.endswith(".txt") or mime_type != TXT_UPLOAD_MIME_TYPE:
        raise UnsupportedFileTypeError("Only .txt files declared as text/plain are supported")
    if len(content) > TXT_UPLOAD_MAX_BYTES:
        raise FileTooLargeError("TXT upload exceeds the approved byte limit")
    try:
        decoded = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise FileUploadValidationError("TXT upload must contain valid UTF-8") from None
    if len(decoded) > TXT_UPLOAD_MAX_CHARACTERS:
        raise FileUploadValidationError("TXT upload exceeds the approved character limit")
    try:
        validate_text_context(decoded)
    except ContextSourceValidationError:
        raise FileUploadValidationError("TXT upload failed text safety validation") from None
    return ValidatedTextUpload(
        original_name=original_name,
        mime_type=mime_type,
        content=content,
        content_digest=sha256(content).hexdigest(),
    )


def validate_upload_filename(value: str) -> str:
    normalized = normalize("NFC", value)
    if not 1 <= len(normalized) <= 255:
        raise FileUploadValidationError("Filename length is invalid")
    if normalized in {".", ".."}:
        raise FileUploadValidationError("Filename is not a basename")
    if "/" in normalized or "\\" in normalized:
        raise FileUploadValidationError("Filename contains a path separator")
    if any(category(character) == "Cc" for character in normalized):
        raise FileUploadValidationError("Filename contains a control character")
    return normalized


def normalize_declared_mime_type(value: str | None) -> str:
    if value is None:
        return ""
    return value.split(";", maxsplit=1)[0].strip().lower()
