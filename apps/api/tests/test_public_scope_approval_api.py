from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.sharing.application.public_approval import (
    ApprovePublicScopeCommand,
    ApprovePublicScopeResult,
    PublicScopeAlreadyApproved,
    PublicScopeApprovalIdempotencyConflict,
    PublicScopeApprovalNotFound,
)
from app.modules.sharing.domain.scope_approval import ScopeApproval

NOW = datetime.now(UTC)
APPROVAL_ID = uuid4()


def _approval() -> ScopeApproval:
    return ScopeApproval(
        id=APPROVAL_ID,
        account_id=uuid4(),
        project_id=uuid4(),
        scope_version_id=uuid4(),
        share_link_id=uuid4(),
        version_no=2,
        version_hash="sha256:" + "a" * 64,
        guest_name="مینا احمدی",
        explicit_consent=True,
        idempotency_key="approval-key",
        request_hash="b" * 64,
        approved_at=NOW,
    )


class StubApprovalService:
    def __init__(self) -> None:
        self.command: ApprovePublicScopeCommand | None = None
        self.error: Exception | None = None
        self.replayed = False

    async def approve(self, command: ApprovePublicScopeCommand) -> ApprovePublicScopeResult:
        self.command = command
        if self.error is not None:
            raise self.error
        approval = ScopeApproval(
            **{
                **asdict(_approval()),
                "guest_name": command.guest_name.strip(),
                "idempotency_key": command.idempotency_key,
            }
        )
        return ApprovePublicScopeResult(approval=approval, replayed=self.replayed)


def _fixture() -> tuple[TestClient, StubApprovalService]:
    service = StubApprovalService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        public_scope_approval_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _body(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "token": "t" * 43,
        "guest_name": "مینا احمدی",
        "explicit_consent": True,
    }
    body.update(changes)
    return body


def test_first_approval_is_201_and_replay_is_same_business_result_with_200() -> None:
    client, service = _fixture()
    headers = {"Idempotency-Key": "approval-key"}

    first = client.post("/api/v1/public/scope-shares/approve", headers=headers, json=_body())
    service.replayed = True
    replay = client.post("/api/v1/public/scope-shares/approve", headers=headers, json=_body())

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["data"] == replay.json()["data"] == {
        "approval_id": str(APPROVAL_ID),
        "scope_version_no": 2,
        "status": "approved",
        "guest_name": "مینا احمدی",
        "approved_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    assert first.json()["meta"]["replayed"] is False
    assert replay.json()["meta"]["replayed"] is True
    assert first.json()["meta"]["request_id"] != replay.json()["meta"]["request_id"]
    assert first.headers["Cache-Control"] == "no-store"
    serialized = first.text
    assert "version_hash" not in serialized
    assert "account_id" not in serialized
    assert service.command == ApprovePublicScopeCommand(
        token="t" * 43,
        guest_name="مینا احمدی",
        explicit_consent=True,
        idempotency_key="approval-key",
    )


def test_request_requires_exact_body_literal_true_and_idempotency_header() -> None:
    client, _ = _fixture()
    path = "/api/v1/public/scope-shares/approve"
    headers = {"Idempotency-Key": "approval-key"}

    for invalid_body in (
        _body(explicit_consent=False),
        _body(explicit_consent="true"),
        _body(explicit_consent=None),
        {"token": "t" * 43, "guest_name": "مینا احمدی"},
        _body(extra=True),
    ):
        response = client.post(path, headers=headers, json=invalid_body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"
        assert response.headers["Cache-Control"] == "no-store"

    assert client.post(path, json=_body()).status_code == 422


def test_public_failures_use_frozen_safe_codes() -> None:
    client, service = _fixture()
    path = "/api/v1/public/scope-shares/approve"
    headers = {"Idempotency-Key": "approval-key"}
    cases = (
        (PublicScopeApprovalNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (PublicScopeApprovalIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (PublicScopeAlreadyApproved(), 409, "SCOPE_ALREADY_APPROVED"),
    )
    for error, expected_status, expected_code in cases:
        service.error = error
        response = client.post(path, headers=headers, json=_body())
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
        assert response.headers["Cache-Control"] == "no-store"


def test_public_approval_does_not_require_jwt_or_tenant_header() -> None:
    client, _ = _fixture()
    response = client.post(
        "/api/v1/public/scope-shares/approve",
        headers={"Idempotency-Key": "approval-key"},
        json=_body(),
    )
    assert response.status_code == 201
