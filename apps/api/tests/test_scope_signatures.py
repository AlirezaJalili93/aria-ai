from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app

FULL_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def create_test_client() -> TestClient:
    settings = ApiSettings(
        app_env="test",
        app_version="0.1.0",
        log_level="INFO",
        release_commit_sha=FULL_COMMIT_SHA,
    )
    return TestClient(create_app(settings))


def test_scope_signature_get_returns_null_when_no_session_factory() -> None:
    client = create_test_client()
    response = client.get("/api/v1/scopes/test-scope-1/signature")
    assert response.status_code == 200
    assert response.json() is None


def test_scope_signature_sign_requires_fields() -> None:
    client = create_test_client()
    response = client.post("/api/v1/scopes/test-scope-1/sign", json={})
    assert response.status_code == 422
