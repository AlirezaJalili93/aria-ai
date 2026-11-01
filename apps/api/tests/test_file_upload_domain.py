from __future__ import annotations

from hashlib import sha256

import pytest

from app.modules.context.domain.file_upload import (
    TXT_UPLOAD_MAX_BYTES,
    FileTooLargeError,
    FileUploadValidationError,
    UnsupportedFileTypeError,
    validate_text_upload,
    validate_upload_filename,
)


def test_txt_upload_requires_exact_extension_normalized_mime_and_strict_utf8() -> None:
    content = "متن فارسی".encode()
    validated = validate_text_upload(
        filename="brief.txt",
        declared_mime_type=" Text/Plain; charset=UTF-8 ",
        content=content,
    )
    assert validated.original_name == "brief.txt"
    assert validated.mime_type == "text/plain"
    assert validated.content == content
    assert validated.content_digest == sha256(content).hexdigest()

    for filename, mime_type in (
        ("brief.TXT", "text/plain"),
        ("file.exe.txt.exe", "text/plain"),
        ("brief.txt", "application/octet-stream"),
    ):
        with pytest.raises(UnsupportedFileTypeError):
            validate_text_upload(
                filename=filename,
                declared_mime_type=mime_type,
                content=content,
            )
    with pytest.raises(FileUploadValidationError):
        validate_text_upload(
            filename="brief.txt",
            declared_mime_type="text/plain",
            content=b"\xff\xfe",
        )


def test_mime_spoofing_and_mixed_extension_are_rejected_before_storage() -> None:
    content = b"plain documentation"
    for filename, mime_type in (
        ("brief.txt", "application/pdf"),
        ("brief.txt", "application/x-msdownload"),
        ("brief.txt", "application/octet-stream"),
        ("brief.TXT", "text/plain"),
        ("brief.TxT", "text/plain"),
        ("brief.txt.exe", "text/plain"),
    ):
        with pytest.raises(UnsupportedFileTypeError):
            validate_text_upload(
                filename=filename,
                declared_mime_type=mime_type,
                content=content,
            )


def test_binary_executable_masquerading_as_txt_is_rejected_but_inert_text_is_allowed() -> None:
    for binary_payload in (
        b"MZ\x00\x02binary executable",
        b"\x7fELF\x02\x01\x00binary executable",
        b"PK\x03\x04\x00archive payload",
    ):
        with pytest.raises(FileUploadValidationError):
            validate_text_upload(
                filename="renamed.exe.txt",
                declared_mime_type="text/plain",
                content=binary_payload,
            )

    inert_text = b"#!/bin/bash\necho documentation"
    assert (
        validate_text_upload(
            filename="example.exe.txt",
            declared_mime_type="text/plain",
            content=inert_text,
        ).content
        == inert_text
    )


def test_txt_upload_enforces_byte_character_empty_and_text_safety_limits() -> None:
    valid_boundary = ("\U00010000" * 50_000).encode()
    assert (
        len(
            validate_text_upload(
                filename="brief.txt",
                declared_mime_type="text/plain",
                content=valid_boundary,
            ).content
        )
        == TXT_UPLOAD_MAX_BYTES
    )
    with pytest.raises(FileTooLargeError):
        validate_text_upload(
            filename="brief.txt",
            declared_mime_type="text/plain",
            content=valid_boundary + b"a",
        )
    with pytest.raises(FileUploadValidationError):
        validate_text_upload(
            filename="brief.txt",
            declared_mime_type="text/plain",
            content=("آ" * 50_001).encode(),
        )
    for content in (b"", b" \t\r\n", b"valid\x00text"):
        with pytest.raises(FileUploadValidationError):
            validate_text_upload(
                filename="brief.txt",
                declared_mime_type="text/plain",
                content=content,
            )


def test_filename_is_nfc_basename_only_and_rejects_controls_and_dot_names() -> None:
    assert validate_upload_filename("cafe\u0301.txt") == "caf\u00e9.txt"
    for filename in ("", ".", "..", "a/b.txt", "a\\b.txt", "bad\x00.txt", "a" * 256):
        with pytest.raises(FileUploadValidationError):
            validate_upload_filename(filename)


def test_path_traversal_filename_abuse_cannot_become_a_storage_path() -> None:
    for filename in (
        "../brief.txt",
        "..\\brief.txt",
        "folder/brief.txt",
        "folder\\brief.txt",
        "C:\\brief.txt",
        "bad\x1f.txt",
        "bad\x85.txt",
    ):
        with pytest.raises(FileUploadValidationError):
            validate_upload_filename(filename)

    # Percent-encoded traversal is inert display metadata. It is not decoded or used as a key.
    assert validate_upload_filename("%2e%2e%2fbrief.txt") == "%2e%2e%2fbrief.txt"


def test_utf8_bom_and_executable_looking_plain_text_are_accepted_without_execution() -> None:
    for content in (
        b"\xef\xbb\xbfPersian brief",
        b"<script>alert('documentation')</script>",
        b"#!/bin/bash\necho documentation",
    ):
        assert validate_text_upload(
            filename="brief.txt",
            declared_mime_type="text/plain",
            content=content,
        ).content == content
