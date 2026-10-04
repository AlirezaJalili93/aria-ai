from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.sharing.application.service import (
    CreateScopeShareLinkCommand,
    CreateScopeShareLinkResult,
    RevokeScopeShareLinkCommand,
    ScopeShareLinkAccessNotFound,
    ScopeShareLinkIdempotencyConflict,
    ScopeShareLinkPermissionDenied,
)
from app.modules.sharing.domain.scope_share_link import (
    ScopeShareLink,
    ScopeShareLinkValidationError,
)

SUBJECT, ACCOUNT_ID, PROJECT_ID, VERSION_ID, LINK_ID = (uuid4() for _ in range(5))
NOW = datetime.now(UTC)
AUTH_VALUE = "scope-share-token"


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != AUTH_VALUE:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=SUBJECT)


class StubTenantContextResolver:
    async def execute(
        self, identity: AuthenticatedIdentity, account_id: UUID
    ) -> TenantContext:
        assert identity.subject == SUBJECT
        assert account_id == ACCOUNT_ID
        return TenantContext(
            subject_id=SUBJECT,
            account_id=ACCOUNT_ID,
            membership_id=uuid4(),
            role="member",
            membership_status="active",
        )


def _link() -> ScopeShareLink:
    return ScopeShareLink(
        id=LINK_ID,
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        scope_version_id=VERSION_ID,
        token_hash=b"h" * 32,
        expires_at=NOW + timedelta(days=1),
        revoked_at=None,
        created_by=SUBJECT,
        created_at=NOW,
    )


class StubScopeShareLinkService:
    def __init__(self) -> None:
        self.create_error: Exception | None = None
        self.revoke_error: Exception | None = None
        self.create_command: CreateScopeShareLinkCommand | None = None
        self.revoke_command: RevokeScopeShareLinkCommand | None = None
        self.replayed = False

    async def create(self, context, *, project_id, command):
        del context
        assert project_id == PROJECT_ID
        self.create_command = command
        if self.create_error is not None:
            raise self.create_error
        return CreateScopeShareLinkResult(
            link=_link(),
            public_token=None if self.replayed else "one-time-token",
            token_available=not self.replayed,
            replayed=self.replayed,
        )

    async def revoke(self, context, *, project_id, share_link_id, command):
        del context
        assert project_id == PROJECT_ID
        assert share_link_id == LINK_ID
        self.revoke_command = command
        if self.revoke_error is not None:
            raise self.revoke_error
        return _link()


def _fixture() -> tuple[TestClient, StubScopeShareLinkService]:
    service = StubScopeShareLinkService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        scope_share_link_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers(*, key="share-create") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {AUTH_VALUE}",
        "X-Account-ID": str(ACCOUNT_ID),
        "Idempotency-Key": key,
    }


def test_create_returns_one_time_token_then_safe_replay_metadata() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions/3/share"
    body = {"expires_at": (NOW + timedelta(days=1)).isoformat()}

    first = client.post(path, headers=_headers(), json=body)
    service.replayed = True
    replay = client.post(path, headers=_headers(), json=body)

    assert first.status_code == 201
    assert first.json()["data"] == {
        "id": str(LINK_ID),
        "scope_version_no": 3,
        "expires_at": _link().expires_at.isoformat().replace("+00:00", "Z"),
        "token": "one-time-token",
        "token_available": True,
    }
    assert first.json()["meta"]["replayed"] is False
    assert replay.status_code == 200
    assert replay.json()["data"]["token"] is None
    assert replay.json()["data"]["token_available"] is False
    assert replay.json()["meta"]["replayed"] is True
    assert service.create_command == CreateScopeShareLinkCommand(
        version_no=3,
        expires_at=NOW + timedelta(days=1),
        idempotency_key="share-create",
    )
    serialized = first.text
    assert str(ACCOUNT_ID) not in serialized
    assert "token_hash" not in serialized
    assert "created_by" not in serialized
    assert "snapshot_data" not in serialized


def test_create_requires_exact_body_auth_tenant_and_idempotency() -> None:
    client, _ = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions/1/share"
    body = {"expires_at": (NOW + timedelta(days=1)).isoformat()}

    assert client.post(path, headers=_headers(), json={**body, "extra": True}).status_code == 422
    headers = _headers()
    headers.pop("Idempotency-Key")
    assert client.post(path, headers=headers, json=body).status_code == 422
    assert client.post(path, json=body).status_code == 401


def test_create_maps_frozen_application_failures() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope/versions/1/share"
    body = {"expires_at": (NOW + timedelta(days=1)).isoformat()}
    cases = (
        (ScopeShareLinkAccessNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ScopeShareLinkPermissionDenied(), 403, "MEMBERSHIP_REQUIRED"),
        (ScopeShareLinkIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (ScopeShareLinkValidationError("invalid"), 422, "VALIDATION_FAILED"),
    )
    for error, expected_status, expected_code in cases:
        service.create_error = error
        response = client.post(path, headers=_headers(), json=body)
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code


def test_revoke_requires_exactly_empty_body_and_is_idempotent_204() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope-shares/{LINK_ID}/revoke"

    revoked = client.post(path, headers=_headers(key="revoke-key"), content=b"")
    replay = client.post(path, headers=_headers(key="revoke-key"), content=b"")
    nonempty = client.post(path, headers=_headers(key="bad-body"), json={})

    assert revoked.status_code == 204
    assert revoked.content == b""
    assert replay.status_code == 204
    assert nonempty.status_code == 422
    assert nonempty.json()["error"]["code"] == "VALIDATION_FAILED"
    assert service.revoke_command == RevokeScopeShareLinkCommand(idempotency_key="revoke-key")


def test_revoke_maps_safe_not_found_permission_and_idempotency_conflict() -> None:
    client, service = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/scope-shares/{LINK_ID}/revoke"
    cases = (
        (ScopeShareLinkAccessNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ScopeShareLinkPermissionDenied(), 403, "MEMBERSHIP_REQUIRED"),
        (ScopeShareLinkIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
    )
    for error, expected_status, expected_code in cases:
        service.revoke_error = error
        response = client.post(path, headers=_headers(key=str(expected_status)), content=b"")
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
