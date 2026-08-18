from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class InvalidAccessToken(Exception):
    """Raised when a token cannot establish an authenticated identity."""


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: UUID


class AccessTokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedIdentity:
        """Verify a provider token and return the canonical external subject."""
        ...
