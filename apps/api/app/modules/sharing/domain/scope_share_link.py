from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID


class ScopeShareLinkValidationError(ValueError):
    """A Scope Share Link invariant was violated."""


def _validate(
    *, token_hash: bytes, expires_at: datetime, created_at: datetime, revoked_at: datetime | None
) -> None:
    if len(token_hash) != 32:
        raise ScopeShareLinkValidationError("token_hash must contain exactly 32 bytes")
    if created_at.tzinfo is None or expires_at.tzinfo is None:
        raise ScopeShareLinkValidationError("share link timestamps must be timezone-aware")
    if expires_at <= created_at:
        raise ScopeShareLinkValidationError("expires_at must be later than created_at")
    if revoked_at is not None:
        if revoked_at.tzinfo is None:
            raise ScopeShareLinkValidationError("revoked_at must be timezone-aware")
        if revoked_at < created_at:
            raise ScopeShareLinkValidationError("revoked_at cannot precede created_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class NewScopeShareLink:
    id: UUID
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    token_hash: bytes
    expires_at: datetime
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        _validate(
            token_hash=self.token_hash,
            expires_at=self.expires_at,
            created_at=self.created_at,
            revoked_at=None,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeShareLink:
    id: UUID
    account_id: UUID
    project_id: UUID
    scope_version_id: UUID
    token_hash: bytes
    expires_at: datetime
    revoked_at: datetime | None
    created_by: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        _validate(
            token_hash=self.token_hash,
            expires_at=self.expires_at,
            created_at=self.created_at,
            revoked_at=self.revoked_at,
        )

    def is_accessible(self, *, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ScopeShareLinkValidationError("now must be timezone-aware")
        return self.revoked_at is None and now < self.expires_at

    def revoke(self, *, now: datetime) -> ScopeShareLink:
        if now.tzinfo is None:
            raise ScopeShareLinkValidationError("now must be timezone-aware")
        if self.revoked_at is not None:
            return self
        if now < self.created_at:
            raise ScopeShareLinkValidationError("revoked_at cannot precede created_at")
        return replace(self, revoked_at=now)
