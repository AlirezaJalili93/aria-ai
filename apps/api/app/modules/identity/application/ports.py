from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

AuthRejectionReason = Literal[
    "invalid_token",
    "malformed_token",
    "expired_token",
    "issuer_mismatch",
    "audience_mismatch",
    "algorithm_mismatch",
    "invalid_signature",
    "missing_claim",
    "missing_kid",
    "unknown_kid",
    "invalid_subject",
]
AuthProviderFailureReason = Literal["jwks_unavailable", "provider_unconfigured"]


class InvalidAccessToken(Exception):
    """Raised when a token cannot establish an authenticated identity."""

    def __init__(self, *, reason_code: AuthRejectionReason = "invalid_token") -> None:
        super().__init__()
        self.reason_code = reason_code


class AuthProviderUnavailable(Exception):
    """Raised when Auth verification cannot run because provider infrastructure failed."""

    def __init__(
        self,
        *,
        reason_code: AuthProviderFailureReason = "jwks_unavailable",
    ) -> None:
        super().__init__()
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: UUID


class AccessTokenVerifier(Protocol):
    provider_name: str

    async def verify(self, token: str) -> AuthenticatedIdentity:
        """Verify a provider token and return the canonical external subject."""
        ...
