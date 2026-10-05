from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.sharing.application.public_change_request import (
    PublicScopeChangeRequestIdempotencyConflict,
    PublicScopeChangeRequestNotFound,
    RequestPublicScopeChangesCommand,
    RequestPublicScopeChangesResult,
)
from app.modules.sharing.application.public_decision_errors import (
    PublicScopeAlreadyApproved,
    PublicScopeChangesAlreadyRequested,
)
from app.modules.sharing.domain.scope_change_request import ScopeChangeRequest

NOW = datetime.now(UTC)
CHANGE_REQUEST_ID = uuid4()


def _change_request() -> ScopeChangeRequest:
    return ScopeChangeRequest(
        id=CHANGE_REQUEST_ID,
        account_id=uuid4(),
        project_id=uuid4(),
        scope_version_id=uuid4(),
        share_link_id=uuid4(),
        version_no=2,
        version_hash="sha256:" + "a" * 64,
        guest_name="مینا احمدی",
        comment="لطفاً بودجه اصلاح شود.",
        idempotency_key="change-key",
        request_hash="b" * 64,
        requested_at=NOW,
    )


class StubChangeRequestService:
    def __init__(self) -> None:
        self.command: RequestPublicScopeChangesCommand | None = None
        self.error: Exception | None = None
        self.replayed = False

    async def request_changes(
        self, command: RequestPublicScopeChangesCommand
    ) -> RequestPublicScopeChangesResult:
        self.command = command
        if self.error is not None:
            raise self.error
        change_request = ScopeChangeRequest(
            **{
                **asdict(_change_request()),
                "guest_name": command.guest_name.strip(),
                "comment": command.comment.strip(),
                "idempotency_key": command.idempotency_key,
            }
        )
        return RequestPublicScopeChangesResult(change_request, self.replayed)


def _fixture() -> tuple[TestClient, StubChangeRequestService]:
    service = StubChangeRequestService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        public_scope_change_request_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _body(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "token": "t" * 43,
        "guest_name": "مینا احمدی",
        "comment": "لطفاً بودجه اصلاح شود.",
    }
    body.update(changes)
    return body


def test_first_request_is_201_and_replay_is_same_business_result_with_200() -> None:
    client, service = _fixture()
    headers = {"Idempotency-Key": "change-key"}

    first = client.post(
        "/api/v1/public/scope-shares/request-changes", headers=headers, json=_body()
    )
    service.replayed = True
    replay = client.post(
        "/api/v1/public/scope-shares/request-changes", headers=headers, json=_body()
    )

    assert first.status_code == 201
    assert replay.status_code == 200
    assert first.json()["data"] == replay.json()["data"] == {
        "change_request_id": str(CHANGE_REQUEST_ID),
        "scope_version_no": 2,
        "status": "changes_requested",
        "guest_name": "مینا احمدی",
        "requested_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    assert first.json()["meta"]["replayed"] is False
    assert replay.json()["meta"]["replayed"] is True
    assert first.headers["Cache-Control"] == "no-store"
    serialized = first.text
    for forbidden in ("comment", "version_hash", "token_hash", "account_id"):
        assert forbidden not in serialized


def test_request_requires_exact_body_and_idempotency_header() -> None:
    client, _ = _fixture()
    path = "/api/v1/public/scope-shares/request-changes"
    headers = {"Idempotency-Key": "change-key"}
    for invalid_body in (
        {"token": "t" * 43, "guest_name": "مینا احمدی"},
        _body(comment=None),
        _body(extra=True),
    ):
        response = client.post(path, headers=headers, json=invalid_body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"
        assert response.headers["Cache-Control"] == "no-store"
    assert client.post(path, json=_body()).status_code == 422


def test_public_failures_use_frozen_safe_codes_without_auth_headers() -> None:
    client, service = _fixture()
    path = "/api/v1/public/scope-shares/request-changes"
    headers = {"Idempotency-Key": "change-key"}
    cases = (
        (PublicScopeChangeRequestNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (PublicScopeChangeRequestIdempotencyConflict(), 409, "IDEMPOTENCY_CONFLICT"),
        (PublicScopeAlreadyApproved(), 409, "SCOPE_ALREADY_APPROVED"),
        (PublicScopeChangesAlreadyRequested(), 409, "SCOPE_CHANGES_ALREADY_REQUESTED"),
    )
    for error, expected_status, expected_code in cases:
        service.error = error
        response = client.post(path, headers=headers, json=_body())
        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code
        assert response.headers["Cache-Control"] == "no-store"
