from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.errors import AuthenticationRequiredError
from app.modules.identity.application.ports import (
    AccessTokenVerifier,
    AuthenticatedIdentity,
    InvalidAccessToken,
)

_bearer_scheme = HTTPBearer(auto_error=False)


def _access_token_verifier(request: Request) -> AccessTokenVerifier:
    return cast(AccessTokenVerifier, request.app.state.access_token_verifier)


async def require_authenticated_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    verifier: Annotated[AccessTokenVerifier, Depends(_access_token_verifier)],
) -> AuthenticatedIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequiredError
    try:
        return await verifier.verify(credentials.credentials)
    except InvalidAccessToken:
        raise AuthenticationRequiredError from None
