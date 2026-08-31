from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies.account_bootstrap import ensure_bootstrapped_identity
from app.modules.identity.application.account_bootstrap import AccountBootstrapContext


def create_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post(
        "/bootstrap",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        responses={
            401: {"description": "The Bearer credential is missing or invalid."},
            503: {"description": "Auth or Account Bootstrap infrastructure is unavailable."},
        },
    )
    async def bootstrap_account(
        context: Annotated[
            AccountBootstrapContext,
            Depends(ensure_bootstrapped_identity),
        ],
    ) -> Response:
        """Create or resolve the authenticated identity projection without returning data."""
        del context
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
