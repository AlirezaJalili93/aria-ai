from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.sharing.domain.scope_share_link import (
    ScopeShareLink,
    ScopeShareLinkValidationError,
)
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer

NOW = datetime.now(UTC)


def _link(*, expires_at=None, revoked_at=None) -> ScopeShareLink:
    return ScopeShareLink(
        id=uuid4(),
        account_id=uuid4(),
        project_id=uuid4(),
        scope_version_id=uuid4(),
        token_hash=b"x" * 32,
        expires_at=expires_at or NOW + timedelta(hours=1),
        revoked_at=revoked_at,
        created_by=uuid4(),
        created_at=NOW,
    )


def test_secure_token_is_32_random_bytes_encoded_as_unpadded_base64url() -> None:
    issuer = SecureScopeShareTokenIssuer()
    first = issuer.issue()
    second = issuer.issue()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", first.public_token)
    assert "=" not in first.public_token
    assert first.public_token != second.public_token
    assert len(first.token_hash) == 32
    assert first.token_hash == issuer.hash_public_token(first.public_token)


def test_access_is_derived_synchronously_from_expiry_and_revocation() -> None:
    link = _link()
    assert link.is_accessible(now=NOW + timedelta(minutes=1)) is True
    assert link.is_accessible(now=link.expires_at) is False

    revoked = link.revoke(now=NOW + timedelta(minutes=2))
    assert revoked.is_accessible(now=NOW + timedelta(minutes=3)) is False
    assert revoked.revoke(now=NOW + timedelta(minutes=4)) is revoked


@pytest.mark.parametrize(
    ("token_hash", "expires_at"),
    [(b"short", NOW + timedelta(hours=1)), (b"x" * 32, NOW)],
)
def test_invalid_hash_or_non_future_expiry_is_rejected(token_hash, expires_at) -> None:
    with pytest.raises(ScopeShareLinkValidationError):
        ScopeShareLink(
            id=uuid4(),
            account_id=uuid4(),
            project_id=uuid4(),
            scope_version_id=uuid4(),
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_by=uuid4(),
            created_at=NOW,
        )
