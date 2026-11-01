from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.sharing.domain.scope_approval import normalize_guest_name


class ScopeChangeRequestValidationError(ValueError):
    """A public Scope Change Request invariant was violated."""


_SNAPSHOT_HASH = re.compile(r"sha256:[0-9a-f]{64}")


def normalize_change_comment(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    if any(_is_forbidden_control(character) for character in normalized):
        raise ScopeChangeRequestValidationError("comment cannot contain control characters")
    normalized = normalized.strip()
    if not 1 <= len(normalized) <= 4000:
        raise ScopeChangeRequestValidationError("comment must contain 1 to 4000 characters")
    return normalized


def _is_forbidden_control(character: str) -> bool:
    if character == "\n":
        return False
    codepoint = ord(character)
    return codepoint <= 0x1F or 0x7F <= codepoint <= 0x9F


def _validate(
    *,
    guest_name: str,
    comment: str,
    version_no: int,
    version_hash: str,
    idempotency_key: str,
    request_hash: str,
    requested_at: datetime,
) -> None:
    if normalize_guest_name(guest_name) != guest_name:
        raise ScopeChangeRequestValidationError("guest_name must already be normalized")
    if normalize_change_comment(comment) != comment:
        raise ScopeChangeRequestValidationError("comment must already be normalized")
    if version_no < 1:
        raise ScopeChangeRequestValidationError("version_no must be at least one")
    if not _SNAPSHOT_HASH.fullmatch(version_hash):
        raise ScopeChangeRequestValidationError("version_hash format is invalid")
    if not idempotency_key.strip():
        raise ScopeChangeRequestValidationError("Idempotency-Key must not be empty")
    if not re.fullmatch(r"[0-9a-f]{64}", request_hash):
        raise ScopeChangeRequestValidationError("request_hash format is invalid")
    if requested_at.tzinfo is None:
        raise ScopeChangeRequestValidationError("requested_at must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class NewScopeChangeRequest:
    id: UUID
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    share_link_id: UUID
    version_no: int
    version_hash: str
    guest_name: str
    comment: str
    idempotency_key: str
    request_hash: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _validate(
            guest_name=self.guest_name,
            comment=self.comment,
            version_no=self.version_no,
            version_hash=self.version_hash,
            idempotency_key=self.idempotency_key,
            request_hash=self.request_hash,
            requested_at=self.requested_at,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeChangeRequest(NewScopeChangeRequest):
    pass
