from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.gaps.application.clarification_ports import ClarificationHistoryEntry
from app.modules.gaps.application.clarification_service import (
    ClarificationDuplicate,
    ClarificationInvalidState,
    ClarificationNotFound,
    ClarificationVersionConflict,
    CreateClarificationQuestionCommand,
    DismissGapCommand,
    EditClarificationQuestionCommand,
    ResolveClarificationCommand,
)
from app.modules.gaps.domain.clarification import Clarification, ClarificationResolution
from app.modules.gaps.domain.gap import Gap
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext

SUBJECT, ACCOUNT_ID, PROJECT_ID, GAP_ID, CLARIFICATION_ID = (
    uuid4(),
    uuid4(),
    uuid4(),
    uuid4(),
    uuid4(),
)


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != "clarification-token":
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


class StubClarificationService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.question = Clarification(
            id=CLARIFICATION_ID,
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            gap_id=GAP_ID,
            question_text="پرسش",
            status="open",
            created_by_type="user",
            created_by=SUBJECT,
            created_at=now,
            updated_at=now,
        )
        self.resolution = ClarificationResolution(
            id=uuid4(),
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            gap_id=GAP_ID,
            clarification_id=CLARIFICATION_ID,
            resolution_type="provided_information",
            answer_text="پاسخ",
            author_type="client",
            author_id=None,
            actor_id=SUBJECT,
            created_at=now,
        )
        self.gap = Gap(
            id=GAP_ID,
            account_id=ACCOUNT_ID,
            project_id=PROJECT_ID,
            context_version=2,
            gap_type="unsupported_assumption",
            severity="critical",
            status="open",
            source_refs=(),
            created_at=now,
            updated_at=now,
            explanation="توضیح ساختاری",
            suggested_resolution_type="validate_assumption",
        )
        self.error: Exception | None = None
        self.create_command: CreateClarificationQuestionCommand | None = None
        self.edit_command: EditClarificationQuestionCommand | None = None
        self.resolve_command: ResolveClarificationCommand | None = None
        self.dismiss_command: DismissGapCommand | None = None

    async def list_gaps(self, context: TenantContext, **_: object) -> tuple[Gap, ...]:
        del context
        if self.error is not None:
            raise self.error
        return (self.gap,)

    async def list_clarifications(
        self, context: TenantContext, **_: object
    ) -> tuple[ClarificationHistoryEntry, ...]:
        del context
        if self.error is not None:
            raise self.error
        return (ClarificationHistoryEntry(self.question, self.resolution),)

    async def create_question(self, context: TenantContext, **kwargs: object) -> Clarification:
        del context
        self.create_command = kwargs["command"]  # type: ignore[assignment]
        if self.error is not None:
            raise self.error
        return self.question

    async def edit_question(self, context: TenantContext, **kwargs: object) -> Clarification:
        del context
        self.edit_command = kwargs["command"]  # type: ignore[assignment]
        if self.error is not None:
            raise self.error
        return self.question

    async def resolve_question(
        self, context: TenantContext, **kwargs: object
    ) -> ClarificationResolution:
        del context
        self.resolve_command = kwargs["command"]  # type: ignore[assignment]
        if self.error is not None:
            raise self.error
        return self.resolution

    async def dismiss_gap(self, context: TenantContext, **kwargs: object) -> None:
        del context
        self.dismiss_command = kwargs["command"]  # type: ignore[assignment]
        if self.error is not None:
            raise self.error


def _fixture() -> tuple[TestClient, StubClarificationService]:
    service = StubClarificationService()
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        clarification_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service


def _headers(*, key: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer clarification-token",
        "X-Account-ID": str(ACCOUNT_ID),
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def test_question_creation_and_resolution_use_distinct_idempotent_endpoints() -> None:
    client, service = _fixture()
    create = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications",
        headers=_headers(key="question-key"),
        json={"question_text": "پرسش"},
    )
    resolve = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
        f"{CLARIFICATION_ID}/resolutions",
        headers=_headers(key="resolution-key"),
        json={
            "resolution_type": "provided_information",
            "answer_text": "پاسخ",
            "author_type": "client",
        },
    )
    assert create.status_code == 201
    assert resolve.status_code == 201
    assert service.create_command == CreateClarificationQuestionCommand(
        "پرسش", "question-key"
    )
    assert service.resolve_command == ResolveClarificationCommand(
        "provided_information", "پاسخ", "client", "resolution-key"
    )
    assert set(create.json()["data"]) == {
        "id",
        "gap_id",
        "question_text",
        "status",
        "created_by_type",
        "created_at",
        "updated_at",
    }
    assert set(resolve.json()["data"]) == {
        "id",
        "clarification_id",
        "resolution_type",
        "answer_text",
        "author_type",
        "created_at",
    }


def test_gap_and_clarification_read_contracts_are_minimal() -> None:
    client, _ = _fixture()
    gaps = client.get(
        f"/api/v1/projects/{PROJECT_ID}/gaps?status=open&severity=critical&"
        "gap_type=unsupported_assumption",
        headers=_headers(),
    )
    history = client.get(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications",
        headers=_headers(),
    )
    assert gaps.status_code == 200
    assert set(gaps.json()["data"][0]) == {
        "id",
        "context_version",
        "gap_type",
        "severity",
        "status",
        "explanation",
        "suggested_resolution_type",
        "created_at",
        "updated_at",
        "resolved_at",
    }
    assert history.status_code == 200
    item = history.json()["data"][0]
    assert set(item) == {
        "id",
        "gap_id",
        "question_text",
        "status",
        "created_by_type",
        "created_at",
        "updated_at",
        "resolution",
    }
    assert set(item["resolution"]) == {
        "id",
        "resolution_type",
        "answer_text",
        "author_type",
        "created_at",
    }
    assert "actor_id" not in str(history.json())
    assert "author_id" not in str(history.json())


def test_gap_cursor_is_bound_to_active_filters() -> None:
    import base64
    import json

    client, service = _fixture()
    cursor = base64.urlsafe_b64encode(
        json.dumps(
            {
                "created_at": service.gap.created_at.isoformat(),
                "id": str(service.gap.id),
                "filters": {"status": "open", "severity": None, "gap_type": None},
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).decode().rstrip("=")
    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/gaps?status=resolved&cursor={cursor}",
        headers=_headers(),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_question_create_and_resolution_require_idempotency_keys() -> None:
    client, _ = _fixture()
    create = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications",
        headers=_headers(),
        json={"question_text": "پرسش"},
    )
    resolve = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
        f"{CLARIFICATION_ID}/resolutions",
        headers=_headers(),
        json={"resolution_type": "ignored", "author_type": "user"},
    )
    assert create.status_code == 422
    assert resolve.status_code == 422


def test_edit_is_cas_and_gap_dismissal_is_a_separate_command() -> None:
    client, service = _fixture()
    edit = client.patch(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/{CLARIFICATION_ID}",
        headers=_headers(),
        json={
            "question_text": "پرسش جدید",
            "expected_updated_at": service.question.updated_at.isoformat(),
        },
    )
    dismiss = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/dismiss",
        headers=_headers(key="dismiss-key"),
    )
    assert edit.status_code == 200
    assert dismiss.status_code == 204
    assert service.edit_command == EditClarificationQuestionCommand(
        "پرسش جدید", service.question.updated_at
    )
    assert service.dismiss_command == DismissGapCommand("dismiss-key")


def test_contract_rejects_system_resolution_and_extra_fields() -> None:
    client, _ = _fixture()
    invalid_author = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
        f"{CLARIFICATION_ID}/resolutions",
        headers=_headers(key="system"),
        json={"resolution_type": "ignored", "author_type": "system"},
    )
    extra = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications",
        headers=_headers(key="extra"),
        json={"question_text": "پرسش", "created_by_type": "ai"},
    )
    assert invalid_author.status_code == 422
    assert extra.status_code == 422


def test_safe_error_mapping_hides_missing_and_cross_tenant_resources() -> None:
    client, service = _fixture()
    cases = (
        (ClarificationNotFound(), 404, "RESOURCE_NOT_FOUND"),
        (ClarificationVersionConflict(), 409, "VERSION_CONFLICT"),
        (ClarificationInvalidState(), 409, "INVALID_CLARIFICATION_STATE"),
        (ClarificationDuplicate(), 409, "DUPLICATE_CLARIFICATION"),
    )
    for error, status_code, code in cases:
        service.error = error
        response = client.patch(
            f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
            f"{CLARIFICATION_ID}",
            headers=_headers(),
            json={
                "question_text": "پرسش",
                "expected_updated_at": service.question.updated_at.isoformat(),
            },
        )
        assert response.status_code == status_code
        assert response.json()["error"]["code"] == code


def test_answer_text_contract_is_enforced_at_api_boundary() -> None:
    client, _ = _fixture()
    missing = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
        f"{CLARIFICATION_ID}/resolutions",
        headers=_headers(key="missing"),
        json={"resolution_type": "provided_information", "author_type": "client"},
    )
    synthetic = client.post(
        f"/api/v1/projects/{PROJECT_ID}/gaps/{GAP_ID}/clarifications/"
        f"{CLARIFICATION_ID}/resolutions",
        headers=_headers(key="synthetic"),
        json={
            "resolution_type": "accepted_assumption",
            "answer_text": "accepted",
            "author_type": "user",
        },
    )
    assert missing.status_code == 422
    assert synthetic.status_code == 422
