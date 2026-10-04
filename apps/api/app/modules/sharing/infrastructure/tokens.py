from __future__ import annotations

import base64
import hashlib
import secrets

from app.modules.sharing.application.ports import IssuedScopeShareToken


class SecureScopeShareTokenIssuer:
    """Issue opaque public tokens while retaining only one-way hashes."""

    @staticmethod
    def hash_public_token(public_token: str) -> bytes:
        return hashlib.sha256(public_token.encode("utf-8")).digest()

    def issue(self) -> IssuedScopeShareToken:
        public_token = (
            base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
        )
        return IssuedScopeShareToken(
            public_token=public_token,
            token_hash=self.hash_public_token(public_token),
        )
