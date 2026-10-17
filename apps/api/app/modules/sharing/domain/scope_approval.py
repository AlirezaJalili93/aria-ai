from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class ScopeApprovalValidationError(ValueError):
    """A public Scope Approval invariant was violated."""


_SNAPSHOT_HASH = re.compile(r"sha256:[0-9a-f]{64}")


def normalize_guest_name(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if any(_is_forbidden_control(character) for character in normalized):
        raise ScopeApprovalValidationError("guest_name cannot contain control characters")
    normalized = normalized.strip()
    if not 2 <= len(normalized) <= 100:
        raise ScopeApprovalValidationError("guest_name must contain 2 to 100 characters")
    return normalized


def _is_forbidden_control(character: str) -> bool:
    codepoint = ord(character)
    return codepoint <= 0x1F or 0x7F <= codepoint <= 0x9F


def _validate(
    *,
    guest_name: str,
    explicit_consent: bool,
    version_no: int,
    version_hash: str,
    idempotency_key: str,
    request_hash: str,
    approved_at: datetime,
) -> None:
    if normalize_guest_name(guest_name) != guest_name:
        raise ScopeApprovalValidationError("guest_name must already be normalized")
    if explicit_consent is not True:
        raise ScopeApprovalValidationError("explicit_consent must be true")
    if version_no < 1:
        raise ScopeApprovalValidationError("version_no must be at least one")
    if not _SNAPSHOT_HASH.fullmatch(version_hash):
        raise ScopeApprovalValidationError("version_hash format is invalid")
    if not idempotency_key.strip():
        raise ScopeApprovalValidationError("Idempotency-Key must not be empty")
    if not re.fullmatch(r"[0-9a-f]{64}", request_hash):
        raise ScopeApprovalValidationError("request_hash format is invalid")
    if approved_at.tzinfo is None:
        raise ScopeApprovalValidationError("approved_at must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class NewScopeApproval:
    id: UUID
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    share_link_id: UUID
    version_no: int
    version_hash: str
    guest_name: str
    explicit_consent: bool
    idempotency_key: str
    request_hash: str
    approved_at: datetime

    def __post_init__(self) -> None:
        _validate(
            guest_name=self.guest_name,
            explicit_consent=self.explicit_consent,
            version_no=self.version_no,
            version_hash=self.version_hash,
            idempotency_key=self.idempotency_key,
            request_hash=self.request_hash,
            approved_at=self.approved_at,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeApproval(NewScopeApproval):
    pass
