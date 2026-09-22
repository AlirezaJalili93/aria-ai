from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.config import ApiSettings
from app.main import create_app
from app.modules.context.application.context_item_ports import CurrentContextItems
from app.modules.context.application.context_item_service import (
    ContextItemInvalidState,
    ContextItemVersionConflict,
    ReviewContextItemCommand,
)
from app.modules.context.domain.context_item import ContextItem, SourceReference
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.identity.application.tenant_context import TenantContext


class StubTokenVerifier:
    provider_name = "test-provider"

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != "context-review-token":
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=SUBJECT)


class StubTenantContextResolver:
    async def execute(self, identity: AuthenticatedIdentity, account_id: UUID) -> TenantContext:
        assert identity.subject == SUBJECT
        assert account_id == ACCOUNT_ID
        return TenantContext(
            subject_id=SUBJECT,
            account_id=ACCOUNT_ID,
            membership_id=uuid4(),
            role="member",
            membership_status="active",
        )


class StubReviewService:
    def __init__(self, item: ContextItem) -> None:
        self.item = item
        self.items = tuple(item for _ in range(21))
        self.last_command: ReviewContextItemCommand | None = None
        self.error: Exception | None = None

    async def list_current(self, context: TenantContext, **kwargs: object) -> CurrentContextItems:
        del context
        if self.error is not None:
            raise self.error
        assert kwargs["project_id"] == PROJECT_ID
        return CurrentContextItems(context_version=1, items=self.items)

    async def review(
        self,
        context: TenantContext,
        *,
        project_id: UUID,
        item_id: UUID,
        command: ReviewContextItemCommand,
    ) -> ContextItem:
        del context, project_id, item_id
        self.last_command = command
        if self.error is not None:
            raise self.error
        return self.item


SUBJECT, ACCOUNT_ID, PROJECT_ID = uuid4(), uuid4(), uuid4()


def _item() -> ContextItem:
    now = datetime.now(UTC)
    return ContextItem(
        id=uuid4(),
        account_id=ACCOUNT_ID,
        project_id=PROJECT_ID,
        context_version=1,
        item_type="fact",
        content="محتوا",
        source_refs=(SourceReference(uuid4(), uuid4(), 0, 4),),
        confidence=Decimal("0.5000"),
        status="proposed",
        created_by_type="ai",
        created_by=None,
        created_at=now,
        updated_at=now,
    )


def _fixture() -> tuple[TestClient, StubReviewService, TenantContext]:
    context = TenantContext(
        subject_id=SUBJECT,
        account_id=ACCOUNT_ID,
        membership_id=uuid4(),
        role="member",
        membership_status="active",
    )
    service = StubReviewService(_item())
    app = create_app(
        ApiSettings(app_env="test", app_version="0.1.0", log_level="INFO"),
        access_token_verifier=StubTokenVerifier(),
        tenant_context_resolver=StubTenantContextResolver(),
        context_item_review_service=service,  # type: ignore[arg-type]
    )
    return TestClient(app), service, context


def _headers(context: TenantContext) -> dict[str, str]:
    return {
        "Authorization": "Bearer context-review-token",
        "X-Account-ID": str(context.account_id),
    }


def test_context_items_collection_filters_and_opaque_cursor() -> None:
    client, _, context = _fixture()
    response = client.get(
        f"/api/v1/projects/{PROJECT_ID}/context-items?item_type=fact&status=proposed&source_id={uuid4()}&limit=20",
        headers=_headers(context),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 20
    assert body["meta"]["has_more"] is True
    assert body["meta"]["next_cursor"]
    assert set(body["data"][0]) == {
        "id",
        "context_version",
        "item_type",
        "content",
        "source_refs",
        "confidence",
        "status",
        "created_by_type",
        "created_at",
        "updated_at",
    }


def test_context_item_commands_map_to_application_and_errors_stay_distinct() -> None:
    client, service, context = _fixture()
    item = service.item
    response = client.patch(
        f"/api/v1/projects/{PROJECT_ID}/context-items/{item.id}",
        headers=_headers(context),
        json={
            "command": "edit",
            "expected_updated_at": item.updated_at.isoformat(),
            "content": "اصلاح‌شده",
        },
    )
    assert response.status_code == 200
    assert service.last_command is not None
    assert service.last_command.command == "edit"
    assert service.last_command.content == "اصلاح‌شده"

    for error, code in (
        (ContextItemVersionConflict(), "VERSION_CONFLICT"),
        (ContextItemInvalidState(), "INVALID_CONTEXT_ITEM_STATE"),
    ):
        service.error = error
        failed = client.patch(
            f"/api/v1/projects/{PROJECT_ID}/context-items/{item.id}",
            headers=_headers(context),
            json={"command": "confirm", "expected_updated_at": item.updated_at.isoformat()},
        )
        assert failed.status_code == 409
        assert failed.json()["error"]["code"] == code
        service.error = None


def test_context_item_review_requires_tenant_and_rejects_deferred_commands() -> None:
    client, _, context = _fixture()
    path = f"/api/v1/projects/{PROJECT_ID}/context-items/{uuid4()}"
    assert client.get(f"/api/v1/projects/{PROJECT_ID}/context-items").status_code == 401
    invalid = client.patch(
        path,
        headers=_headers(context),
        json={"command": "delete", "expected_updated_at": datetime.now(UTC).isoformat()},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_FAILED"
