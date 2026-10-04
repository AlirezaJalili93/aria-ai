from __future__ import annotations

from io import StringIO
from uuid import uuid4

from aria_observability import create_event_logger
from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.sharing.application.ports import ResolvedPublicScope
from app.modules.sharing.application.public_resolver import PublicScopeShareNotFound
from app.modules.sharing.infrastructure.tokens import SecureScopeShareTokenIssuer


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": "summary",
                "value": "Synthetic public Scope",
                "trace": {"context_item_ids": [], "requirement_ids": [], "gap_ids": []},
            }
        ],
    }


class StubResolver:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.tokens: list[str] = []

    async def resolve(self, *, token: str) -> ResolvedPublicScope:
        self.tokens.append(token)
        if self.error is not None:
            raise self.error
        return ResolvedPublicScope(
            share_link_id=uuid4(),
            scope_version_id=uuid4(),
            version_no=4,
            snapshot_data=_snapshot(),
        )


def _fixture() -> tuple[TestClient, StubResolver]:
    resolver = StubResolver()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        public_scope_share_resolver=resolver,  # type: ignore[arg-type]
    )
    return TestClient(app), resolver


def test_public_resolve_requires_no_identity_and_returns_minimal_no_store_snapshot() -> None:
    client, resolver = _fixture()
    token = SecureScopeShareTokenIssuer().issue().public_token

    response = client.post("/api/v1/public/scope-shares/resolve", json={"token": token})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert resolver.tokens == [token]
    assert response.json()["data"] == {"version_no": 4, "snapshot_data": _snapshot()}
    assert set(response.json()["data"]) == {"version_no", "snapshot_data"}
    assert "authorization" not in response.request.headers
    assert "x-account-id" not in response.request.headers


def test_unknown_and_malformed_capabilities_share_safe_404_and_no_store() -> None:
    client, resolver = _fixture()
    resolver.error = PublicScopeShareNotFound()

    unknown = client.post("/api/v1/public/scope-shares/resolve", json={"token": "a" * 43})
    malformed = client.post("/api/v1/public/scope-shares/resolve", json={"token": "malformed"})

    for response in (unknown, malformed):
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["error"] == {
            "code": "RESOURCE_NOT_FOUND",
            "message": "The requested resource was not found.",
            "retryable": False,
        }


def test_invalid_request_shape_is_422_and_no_store() -> None:
    client, resolver = _fixture()
    for body in ({}, {"token": None}, {"token": "a" * 43, "extra": "forbidden"}):
        response = client.post("/api/v1/public/scope-shares/resolve", json=body)
        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert resolver.tokens == []


def test_token_path_query_and_other_methods_are_not_capability_transports() -> None:
    client, resolver = _fixture()
    token = SecureScopeShareTokenIssuer().issue().public_token

    assert client.get(f"/api/v1/public/scope-shares/resolve/{token}").status_code == 404
    assert (
        client.post(f"/api/v1/public/scope-shares/resolve?token={token}", json={}).status_code
        == 422
    )
    assert client.get("/api/v1/public/scope-shares/resolve").status_code == 405
    assert resolver.tokens == []


def test_request_observability_never_records_raw_token_or_hash() -> None:
    resolver = StubResolver()
    stream = StringIO()
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        event_logger=logger,
        public_scope_share_resolver=resolver,  # type: ignore[arg-type]
    )
    token = SecureScopeShareTokenIssuer().issue().public_token

    response = TestClient(app).post(
        "/api/v1/public/scope-shares/resolve",
        json={"token": token},
    )

    assert response.status_code == 200
    logged = stream.getvalue()
    assert token not in logged
    assert SecureScopeShareTokenIssuer.hash_public_token(token).hex() not in logged
    assert "snapshot_data" not in logged
