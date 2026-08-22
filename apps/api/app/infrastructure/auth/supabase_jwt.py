from __future__ import annotations

import asyncio
from json import JSONDecodeError
from time import perf_counter
from uuid import UUID

import jwt
from aria_observability import StructuredEventLogger
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidSubjectError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWKClientConnectionError,
    PyJWKClientError,
    PyJWKSetError,
)

from app.modules.identity.application.ports import (
    AuthenticatedIdentity,
    AuthProviderUnavailable,
    InvalidAccessToken,
)

_ALLOWED_ALGORITHM = "ES256"
_JWKS_CACHE_LIFESPAN_SECONDS = 600
_JWKS_TIMEOUT_SECONDS = 5


class SupabaseJwtVerifier:
    """Verify Supabase access tokens without leaking provider claims upstream."""

    provider_name = "supabase"

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        clock_skew_seconds: int,
        event_logger: StructuredEventLogger | None = None,
    ) -> None:
        if clock_skew_seconds != 30:
            raise ValueError("Supabase JWT clock skew must be the approved 30 seconds")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._clock_skew_seconds = clock_skew_seconds
        self._event_logger = event_logger
        self._jwk_client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=_JWKS_CACHE_LIFESPAN_SECONDS,
            timeout=_JWKS_TIMEOUT_SECONDS,
        )

    async def verify(self, token: str) -> AuthenticatedIdentity:
        return await asyncio.to_thread(self._verify_sync, token)

    def _verify_sync(self, token: str) -> AuthenticatedIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except (DecodeError, InvalidTokenError, TypeError):
            raise InvalidAccessToken(reason_code="malformed_token") from None

        algorithm = header.get("alg")
        kid = header.get("kid")
        if algorithm != _ALLOWED_ALGORITHM:
            raise InvalidAccessToken(reason_code="algorithm_mismatch")
        if not isinstance(kid, str) or not kid:
            raise InvalidAccessToken(reason_code="missing_kid")

        try:
            signing_key = self._resolve_signing_key(kid)
        except InvalidAccessToken:
            raise
        except (
            JSONDecodeError,
            PyJWKClientConnectionError,
            PyJWKClientError,
            PyJWKSetError,
            TypeError,
            ValueError,
        ):
            raise AuthProviderUnavailable(reason_code="jwks_unavailable") from None

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[_ALLOWED_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._clock_skew_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except ExpiredSignatureError:
            raise InvalidAccessToken(reason_code="expired_token") from None
        except InvalidIssuerError:
            raise InvalidAccessToken(reason_code="issuer_mismatch") from None
        except InvalidAudienceError:
            raise InvalidAccessToken(reason_code="audience_mismatch") from None
        except InvalidAlgorithmError:
            raise InvalidAccessToken(reason_code="algorithm_mismatch") from None
        except InvalidSignatureError:
            raise InvalidAccessToken(reason_code="invalid_signature") from None
        except InvalidSubjectError:
            raise InvalidAccessToken(reason_code="invalid_subject") from None
        except MissingRequiredClaimError:
            raise InvalidAccessToken(reason_code="missing_claim") from None
        except (DecodeError, InvalidTokenError, TypeError):
            raise InvalidAccessToken(reason_code="malformed_token") from None

        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise InvalidAccessToken(reason_code="invalid_subject")
        try:
            subject_id = UUID(subject)
        except ValueError:
            raise InvalidAccessToken(reason_code="invalid_subject") from None
        return AuthenticatedIdentity(subject=subject_id)

    def _resolve_signing_key(self, kid: str) -> PyJWK:
        signing_key = _find_signing_key(self._jwk_client.get_signing_keys(), kid)
        if signing_key is not None:
            return signing_key

        refresh_started_at = perf_counter()
        signing_key = _find_signing_key(
            self._jwk_client.get_signing_keys(refresh=True),
            kid,
        )
        if self._event_logger is not None:
            self._event_logger.emit(
                "auth.jwks_refreshed",
                provider=self.provider_name,
                reason_code="unknown_kid",
                duration_ms=(perf_counter() - refresh_started_at) * 1000,
            )
        if signing_key is None:
            raise InvalidAccessToken(reason_code="unknown_kid")
        return signing_key


class RejectingAccessTokenVerifier:
    """Fail closed when no hosted Auth provider configuration is available."""

    provider_name = "unconfigured"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        del token
        raise AuthProviderUnavailable(reason_code="provider_unconfigured")


def _find_signing_key(signing_keys: list[PyJWK], kid: str) -> PyJWK | None:
    return next((key for key in signing_keys if key.key_id == kid), None)
