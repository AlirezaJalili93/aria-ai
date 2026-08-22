from __future__ import annotations

import json
from io import StringIO
from typing import Annotated
from uuid import UUID, uuid4

from aria_observability import create_event_logger
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.authentication import require_authenticated_identity
from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import (
    AuthenticatedIdentity,
    AuthProviderUnavailable,
    InvalidAccessToken,
)


class StubTokenVerifier:
    provider_name = "test-provider"

    def __init__(self, valid_token: str, subject: UUID) -> None:
        self._valid_token = valid_token
        self._subject = subject
        self.tokens: list[str] = []

    async def verify(self, token: str) -> AuthenticatedIdentity:
        self.tokens.append(token)
        if token != self._valid_token:
            raise InvalidAccessToken(reason_code="invalid_signature")
        return AuthenticatedIdentity(subject=self._subject)


class UnavailableTokenVerifier:
    provider_name = "supabase"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        del token
        raise AuthProviderUnavailable(reason_code="jwks_unavailable")


def _protected_app(
    verifier: StubTokenVerifier | UnavailableTokenVerifier,
    *,
    stream: StringIO | None = None,
) -> FastAPI:
    settings = ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO")
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    app = create_app(settings, access_token_verifier=verifier, event_logger=logger)

    @app.get("/test/protected")
    async def protected(
        identity: Annotated[AuthenticatedIdentity, Depends(require_authenticated_identity)],
    ) -> dict[str, str]:
        return {"subject": str(identity.subject)}

    return app


def test_valid_bearer_token_resolves_authenticated_identity() -> None:
    stream = StringIO()
    subject = uuid4()
    verifier = StubTokenVerifier("valid-access-token", subject)
    client = TestClient(_protected_app(verifier, stream=stream))

    response = client.get(
        "/test/protected",
        headers={"Authorization": "Bearer valid-access-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"subject": str(subject)}
    assert verifier.tokens == ["valid-access-token"]
    event = json.loads(stream.getvalue().splitlines()[0])
    assert event["event_name"] == "auth.verification_succeeded"
    assert event["provider"] == "test-provider"
    assert event["duration_ms"] >= 0
    assert "valid-access-token" not in stream.getvalue()
    assert str(subject) not in stream.getvalue()


def test_missing_bearer_token_returns_stable_401_error_envelope() -> None:
    stream = StringIO()
    verifier = StubTokenVerifier("valid-access-token", uuid4())
    response = TestClient(_protected_app(verifier, stream=stream)).get("/test/protected")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    UUID(response.json()["meta"]["request_id"])
    assert response.json() == {
        "error": {
            "code": "AUTH_REQUIRED",
            "message": "Authentication is required.",
            "retryable": False,
        },
        "meta": {"request_id": response.json()["meta"]["request_id"]},
    }
    assert verifier.tokens == []
    event = json.loads(stream.getvalue().splitlines()[0])
    assert event["event_name"] == "auth.verification_rejected"
    assert event["reason_code"] == "missing_credential"


def test_invalid_token_returns_same_401_without_leaking_token() -> None:
    stream = StringIO()
    verifier = StubTokenVerifier("valid-access-token", uuid4())
    secret_token = "invalid-secret-token"
    response = TestClient(_protected_app(verifier, stream=stream)).get(
        "/test/protected",
        headers={"Authorization": f"Bearer {secret_token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert secret_token not in response.text
    assert secret_token not in stream.getvalue()
    event = json.loads(stream.getvalue().splitlines()[0])
    assert event["event_name"] == "auth.verification_rejected"
    assert event["reason_code"] == "invalid_signature"
    assert event["error_code"] == "AUTH_REQUIRED"


def test_auth_provider_failure_returns_retryable_503_and_safe_event() -> None:
    stream = StringIO()
    secret_token = "secret-token-during-provider-outage"
    response = TestClient(
        _protected_app(UnavailableTokenVerifier(), stream=stream)
    ).get(
        "/test/protected",
        headers={"Authorization": f"Bearer {secret_token}"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "AUTH_PROVIDER_UNAVAILABLE",
            "message": "Authentication provider is temporarily unavailable.",
            "retryable": True,
        },
        "meta": {"request_id": response.json()["meta"]["request_id"]},
    }
    event = json.loads(stream.getvalue().splitlines()[0])
    assert event["event_name"] == "auth.provider_unavailable"
    assert event["provider"] == "supabase"
    assert event["reason_code"] == "jwks_unavailable"
    assert event["error_code"] == "AUTH_PROVIDER_UNAVAILABLE"
    assert event["request_id"] == response.json()["meta"]["request_id"]
    assert event["correlation_id"] == response.headers["X-Correlation-ID"]
    assert event["duration_ms"] >= 0
    assert secret_token not in stream.getvalue()


def test_health_routes_remain_public_and_do_not_call_auth_verifier() -> None:
    verifier = StubTokenVerifier("valid-access-token", uuid4())
    client = TestClient(_protected_app(verifier))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert verifier.tokens == []
