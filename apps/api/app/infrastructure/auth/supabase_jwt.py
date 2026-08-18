from __future__ import annotations

import asyncio
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.modules.identity.application.ports import (
    AuthenticatedIdentity,
    InvalidAccessToken,
)

_ALLOWED_ALGORITHM = "ES256"
_JWKS_CACHE_LIFESPAN_SECONDS = 600


class SupabaseJwtVerifier:
    """Verify Supabase access tokens without leaking provider claims upstream."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        clock_skew_seconds: int,
    ) -> None:
        if clock_skew_seconds != 30:
            raise ValueError("Supabase JWT clock skew must be the approved 30 seconds")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._clock_skew_seconds = clock_skew_seconds
        self._jwk_client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
        )

    async def verify(self, token: str) -> AuthenticatedIdentity:
        return await asyncio.to_thread(self._verify_sync, token)

    def _verify_sync(self, token: str) -> AuthenticatedIdentity:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            kid = header.get("kid")
            if algorithm != _ALLOWED_ALGORITHM:
                raise InvalidAccessToken
            if not isinstance(kid, str) or not kid:
                raise InvalidAccessToken

            signing_key = self._jwk_client.get_signing_key(kid)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[_ALLOWED_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            subject = claims.get("sub")
            if not isinstance(subject, str):
                raise InvalidAccessToken
            return AuthenticatedIdentity(subject=UUID(subject))
        except InvalidAccessToken:
            raise
        except (PyJWTError, TypeError, ValueError):
            raise InvalidAccessToken from None


class RejectingAccessTokenVerifier:
    """Fail closed when no hosted Auth provider configuration is available."""

    async def verify(self, token: str) -> AuthenticatedIdentity:
        raise InvalidAccessToken
