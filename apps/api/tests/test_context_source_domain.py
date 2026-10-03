from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.context.domain.context_source import (
    CONTEXT_SOURCE_PARSE_STATUSES,
    CONTEXT_SOURCE_STATUSES,
    CONTEXT_SOURCE_TYPES,
    TEXT_CONTEXT_MAX_CHARACTERS,
    ContextSource,
    ContextSourceValidationError,
    ContextSourceVersion,
    NewContextSource,
    NewContextSourceVersion,
    text_context_checksum,
    validate_text_context,
)


def _new_source(**overrides: object) -> NewContextSource:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "source_type": "text",
        "status": "uploaded",
        "original_name": None,
        "mime_type": None,
        "storage_ref": None,
        "raw_text": "محتوای خصوصی",
        "checksum": None,
        "created_by": uuid4(),
    }
    values.update(overrides)
    return NewContextSource(**values)  # type: ignore[arg-type]


def _new_version(**overrides: object) -> NewContextSourceVersion:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": uuid4(),
        "project_id": uuid4(),
        "source_id": uuid4(),
        "version_no": 1,
        "content_hash": None,
        "canonical_text": None,
        "storage_ref": None,
        "metadata": None,
        "parse_status": "pending",
    }
    values.update(overrides)
    return NewContextSourceVersion(**values)  # type: ignore[arg-type]


def test_exact_source_and_parse_vocabularies_are_preserved() -> None:
    assert frozenset({"text", "file", "message", "url_reference"}) == CONTEXT_SOURCE_TYPES
    assert (
        frozenset({"uploaded", "parsing", "ready", "failed", "deleted"}) == CONTEXT_SOURCE_STATUSES
    )
    assert frozenset({"pending", "parsing", "ready", "failed"}) == CONTEXT_SOURCE_PARSE_STATUSES


@pytest.mark.parametrize(
    ("factory", "overrides"),
    [
        (_new_source, {"source_type": "voice"}),
        (_new_source, {"status": "processing"}),
        (_new_version, {"parse_status": "uploaded"}),
        (_new_version, {"version_no": 0}),
    ],
)
def test_domain_rejects_unsupported_vocabulary_and_non_positive_versions(
    factory: object, overrides: dict[str, object]
) -> None:
    with pytest.raises(ContextSourceValidationError):
        factory(**overrides)  # type: ignore[operator]


def test_ready_version_requires_canonical_text_or_storage_reference() -> None:
    with pytest.raises(ContextSourceValidationError):
        _new_version(parse_status="ready")

    assert _new_version(parse_status="ready", canonical_text="متن").parse_status == "ready"
    assert _new_version(parse_status="ready", storage_ref="internal/ref").parse_status == "ready"


def test_persisted_timestamps_must_be_timezone_aware() -> None:
    source = _new_source()
    now = datetime.now(UTC)
    ContextSource(**asdict(source), created_at=now, updated_at=now)

    with pytest.raises(ContextSourceValidationError):
        ContextSource(**asdict(source), created_at=now.replace(tzinfo=None), updated_at=now)

    version = _new_version()
    ContextSourceVersion(**asdict(version), created_at=now)
    with pytest.raises(ContextSourceValidationError):
        ContextSourceVersion(**asdict(version), created_at=now.replace(tzinfo=None))


def test_text_context_preserves_exact_unicode_and_hashes_persisted_utf8_bytes() -> None:
    raw_text = "  متن فارسی\r\nبا فاصلهٔ پایانی  \n"
    assert validate_text_context(raw_text) == raw_text
    assert (
        text_context_checksum(raw_text)
        == "13142762d1ca6edb485f1bca41d72a6e4bc790138b41d2a1b0c84709f4e3d4ec"
    )


@pytest.mark.parametrize("value", ["", " \t\r\n", "text\x00", "text\x1f", "text\x7f"])
def test_text_context_rejects_blank_and_disallowed_control_characters(value: str) -> None:
    with pytest.raises(ContextSourceValidationError):
        validate_text_context(value)


def test_text_context_enforces_the_approved_unicode_character_limit() -> None:
    assert validate_text_context("آ" * TEXT_CONTEXT_MAX_CHARACTERS)
    with pytest.raises(ContextSourceValidationError):
        validate_text_context("آ" * (TEXT_CONTEXT_MAX_CHARACTERS + 1))
