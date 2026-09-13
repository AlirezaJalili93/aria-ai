from __future__ import annotations

import asyncio
import io
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from aria_observability import StructuredEventLogger
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import ApiSettings
from app.infrastructure.db.runtime import DatabaseRuntime
from app.main import create_app
from app.modules.context.infrastructure.context_item_repository import (
    SqlAlchemyContextItemRepository,
)
from app.modules.context.infrastructure.repository import SqlAlchemyContextSourceRepository
from app.modules.gaps.infrastructure.clarification_repository import (
    SqlAlchemyClarificationRepository,
)
from app.modules.identity.application.ports import AuthenticatedIdentity, InvalidAccessToken
from app.modules.jobs.infrastructure.repository import SqlAlchemyJobRepository
from app.modules.projects.infrastructure.repository import SqlAlchemyProjectRepository
from app.modules.requirements.infrastructure.repository import SqlAlchemyRequirementRepository
from app.modules.scope.domain.scope_draft import SECTION_IDS
from app.modules.scope.domain.scope_version import hash_scope_snapshot
from app.modules.scope.infrastructure.repository import SqlAlchemyScopeDraftRepository
from app.modules.scope.infrastructure.version_repository import SqlAlchemyScopeVersionRepository

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    TEST_DATABASE_URL is None,
    reason="TEST_DATABASE_URL is required for real PostgreSQL security evidence",
)
API_ROOT = Path(__file__).parents[1]


class StubTokenVerifier:
    provider_name = "test-provider"

    def __init__(self, token: str, subject: UUID) -> None:
        self._token = token
        self._subject = subject

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != self._token:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=self._subject)


@dataclass(frozen=True)
class TenantFixtures:
    user_a: UUID
    user_b: UUID
    account_a: UUID
    account_b: UUID
    project_a: UUID
    project_b: UUID
    source_b: UUID
    source_version_b: UUID
    context_item_b: UUID
    requirement_b: UUID
    gap_b: UUID
    clarification_b: UUID
    scope_draft_b: UUID
    scope_version_b: UUID
    job_b: UUID
    mutable_updated_at: datetime


def _migration_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


async def _execute(sql: str, parameters: dict[str, object] | None = None):
    assert TEST_DATABASE_URL is not None
    runtime = DatabaseRuntime(TEST_DATABASE_URL)
    try:
        async with runtime.engine.begin() as connection:
            return await connection.execute(text(sql), parameters or {})
    finally:
        await runtime.close()


@pytest.fixture(autouse=True)
def clean_security_schema() -> Iterator[None]:
    assert TEST_DATABASE_URL is not None
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    asyncio.run(
        _execute(
            "DO $aria$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN "
            "CREATE ROLE anon NOLOGIN; END IF; "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN "
            "CREATE ROLE authenticated NOLOGIN; END IF; END $aria$"
        )
    )
    command.upgrade(_migration_config(), "head")
    asyncio.run(
        _execute(
            "TRUNCATE scope_versions, scope_drafts, clarification_resolutions, "
            "clarifications, gap_requirement_links, gaps, requirements, context_items, "
            "usage_records, outbox_events, jobs, idempotency_records, "
            "context_source_versions, context_sources, project_create_requests, projects, "
            "account_memberships, profiles, accounts RESTART IDENTITY CASCADE"
        )
    )
    yield


def _scope_content() -> dict[str, object]:
    return {
        "schema_version": "scope_content_schema_v1",
        "sections": [
            {
                "section_id": section_id,
                "value": [] if section_id not in {"summary", "visual_direction"} else "",
                "trace": {
                    "context_item_ids": [],
                    "requirement_ids": [],
                    "gap_ids": [],
                },
            }
            for section_id in SECTION_IDS
        ],
    }


async def _seed_two_tenants() -> TenantFixtures:
    values = TenantFixtures(
        user_a=uuid4(),
        user_b=uuid4(),
        account_a=uuid4(),
        account_b=uuid4(),
        project_a=uuid4(),
        project_b=uuid4(),
        source_b=uuid4(),
        source_version_b=uuid4(),
        context_item_b=uuid4(),
        requirement_b=uuid4(),
        gap_b=uuid4(),
        clarification_b=uuid4(),
        scope_draft_b=uuid4(),
        scope_version_b=uuid4(),
        job_b=uuid4(),
        mutable_updated_at=datetime.now(UTC),
    )
    content = _scope_content()
    await _execute(
        "INSERT INTO profiles (user_id) VALUES (:user_a), (:user_b)",
        {"user_a": values.user_a, "user_b": values.user_b},
    )
    await _execute(
        "INSERT INTO accounts (id) VALUES (:account_a), (:account_b)",
        {"account_a": values.account_a, "account_b": values.account_b},
    )
    await _execute(
        "INSERT INTO account_memberships (id, account_id, user_id, role, status) VALUES "
        "(:membership_a, :account_a, :user_a, 'owner', 'active'), "
        "(:membership_b, :account_b, :user_b, 'owner', 'active')",
        {
            "membership_a": uuid4(),
            "membership_b": uuid4(),
            "account_a": values.account_a,
            "account_b": values.account_b,
            "user_a": values.user_a,
            "user_b": values.user_b,
        },
    )
    await _execute(
        "INSERT INTO projects "
        "(id, account_id, owner_id, title, project_type, current_context_version) VALUES "
        "(:project_a, :account_a, :user_a, 'Tenant A project', 'landing', 1), "
        "(:project_b, :account_b, :user_b, 'Tenant B project', 'corporate', 1)",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO context_sources "
        "(id, account_id, project_id, source_type, status, raw_text, created_by) VALUES "
        "(:source_b, :account_b, :project_b, 'text', 'ready', 'tenant-b-secret', :user_b)",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO context_source_versions "
        "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
        "VALUES (:source_version_b, :account_b, :project_b, :source_b, 1, "
        "'tenant-b-canonical-secret', 'ready')",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO context_items "
        "(id, account_id, project_id, context_version, item_type, content, source_refs, "
        "status, created_by_type) VALUES "
        "(:context_item_b, :account_b, :project_b, 1, 'assumption', "
        "'tenant-b-context-secret', '[]'::jsonb, 'proposed', 'ai')",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO requirements "
        "(id, account_id, project_id, context_version, category, title, description, "
        "priority, status, source_refs, created_by_type) VALUES "
        "(:requirement_b, :account_b, :project_b, 1, 'functional', "
        "'tenant-b-requirement-title', 'tenant-b-requirement-secret', 'must', 'draft', "
        "'[]'::jsonb, 'ai')",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO gaps "
        "(id, account_id, project_id, context_version, gap_type, severity, status, "
        "source_refs, explanation) VALUES "
        "(:gap_b, :account_b, :project_b, 1, 'ambiguity', 'high', 'open', '[]'::jsonb, "
        "'tenant-b-gap-secret')",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO clarifications "
        "(id, account_id, project_id, gap_id, question_text, status, created_by_type) VALUES "
        "(:clarification_b, :account_b, :project_b, :gap_b, "
        "'tenant-b-question-secret', 'open', 'system')",
        values.__dict__,
    )
    await _execute(
        "INSERT INTO jobs "
        "(id, account_id, project_id, job_type, status, max_attempts, correlation_id) VALUES "
        "(:job_b, :account_b, :project_b, 'security-fixture', 'queued', 1, :correlation_id)",
        {**values.__dict__, "correlation_id": uuid4()},
    )
    await _execute(
        "INSERT INTO scope_drafts "
        "(id, account_id, project_id, context_version, content, updated_by_type) VALUES "
        "(:scope_draft_b, :account_b, :project_b, 1, CAST(:content AS jsonb), 'system')",
        {**values.__dict__, "content": json.dumps(content)},
    )
    await _execute(
        "INSERT INTO scope_versions "
        "(id, account_id, project_id, version_no, context_version, status, snapshot_data, "
        "snapshot_hash, created_by) VALUES "
        "(:scope_version_b, :account_b, :project_b, 1, 1, 'awaiting_approval', "
        "CAST(:content AS jsonb), :snapshot_hash, :user_b)",
        {
            **values.__dict__,
            "content": json.dumps(content),
            "snapshot_hash": hash_scope_snapshot(content),
        },
    )
    timestamps = await _execute(
        "SELECT min(updated_at) FROM ("
        "SELECT updated_at FROM projects WHERE id=:project_b UNION ALL "
        "SELECT updated_at FROM context_items WHERE id=:context_item_b UNION ALL "
        "SELECT updated_at FROM requirements WHERE id=:requirement_b UNION ALL "
        "SELECT updated_at FROM gaps WHERE id=:gap_b UNION ALL "
        "SELECT updated_at FROM scope_drafts WHERE id=:scope_draft_b) AS values",
        values.__dict__,
    )
    return TenantFixtures(
        **{**values.__dict__, "mutable_updated_at": timestamps.scalar_one()}
    )


def _logger(stream: io.StringIO) -> StructuredEventLogger:
    return StructuredEventLogger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )


def _client(values: TenantFixtures, stream: io.StringIO) -> TestClient:
    assert TEST_DATABASE_URL is not None
    app = create_app(
        ApiSettings(
            app_env="test",
            app_version="0.1.0",
            log_level="INFO",
            database_url=TEST_DATABASE_URL,
        ),
        event_logger=_logger(stream),
        access_token_verifier=StubTokenVerifier("tenant-a-token", values.user_a),
    )
    return TestClient(app)


def _headers(values: TenantFixtures) -> dict[str, str]:
    return {
        "Authorization": "Bearer tenant-a-token",
        "X-Account-ID": str(values.account_a),
    }


def _safe_error(response) -> dict[str, object]:
    body = response.json()
    UUID(body["meta"]["request_id"])
    return body["error"]


def _assert_safe_pair(foreign, missing) -> None:
    assert foreign.status_code == missing.status_code == 404
    expected = {
        "code": "RESOURCE_NOT_FOUND",
        "message": "The requested resource was not found.",
        "retryable": False,
    }
    assert _safe_error(foreign) == _safe_error(missing) == expected


def test_account_selector_tampering_fails_before_resource_access() -> None:
    values = asyncio.run(_seed_two_tenants())
    stream = io.StringIO()
    with _client(values, stream) as client:
        base = {"Authorization": "Bearer tenant-a-token"}
        missing = client.get("/api/v1/projects", headers=base)
        empty = client.get("/api/v1/projects", headers={**base, "X-Account-ID": ""})
        malformed = client.get(
            "/api/v1/projects", headers={**base, "X-Account-ID": "not-a-uuid"}
        )
        foreign = client.get(
            "/api/v1/projects", headers={**base, "X-Account-ID": str(values.account_b)}
        )

    assert [response.status_code for response in (missing, empty, malformed)] == [400, 400, 400]
    assert all(
        response.json()["error"]["code"] == "ACCOUNT_CONTEXT_REQUIRED"
        for response in (missing, empty, malformed)
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "MEMBERSHIP_REQUIRED"
    assert str(values.account_b) not in stream.getvalue()


def test_cross_tenant_http_identifiers_match_missing_safe_404_and_do_not_mutate() -> None:
    values = asyncio.run(_seed_two_tenants())
    stream = io.StringIO()
    missing_project = uuid4()
    missing_child = uuid4()
    headers = _headers(values)
    timestamp = values.mutable_updated_at.isoformat()

    with _client(values, stream) as client:
        pairs = [
            (
                client.get(f"/api/v1/projects/{values.project_b}", headers=headers),
                client.get(f"/api/v1/projects/{missing_project}", headers=headers),
            ),
            (
                client.patch(
                    f"/api/v1/projects/{values.project_b}",
                    headers=headers,
                    json={"title": "tampered", "expected_updated_at": timestamp},
                ),
                client.patch(
                    f"/api/v1/projects/{missing_project}",
                    headers=headers,
                    json={"title": "tampered", "expected_updated_at": timestamp},
                ),
            ),
            (
                client.delete(f"/api/v1/projects/{values.project_b}", headers=headers),
                client.delete(f"/api/v1/projects/{missing_project}", headers=headers),
            ),
            (
                client.post(
                    f"/api/v1/projects/{values.project_b}/context-sources",
                    headers={**headers, "Idempotency-Key": "foreign-context"},
                    json={"source_type": "text", "raw_text": "attacker input"},
                ),
                client.post(
                    f"/api/v1/projects/{missing_project}/context-sources",
                    headers={**headers, "Idempotency-Key": "missing-context"},
                    json={"source_type": "text", "raw_text": "attacker input"},
                ),
            ),
            (
                client.patch(
                    f"/api/v1/projects/{values.project_b}/context-items/"
                    f"{values.context_item_b}",
                    headers=headers,
                    json={"command": "confirm", "expected_updated_at": timestamp},
                ),
                client.patch(
                    f"/api/v1/projects/{missing_project}/context-items/{missing_child}",
                    headers=headers,
                    json={"command": "confirm", "expected_updated_at": timestamp},
                ),
            ),
            (
                client.patch(
                    f"/api/v1/projects/{values.project_b}/requirements/{values.requirement_b}",
                    headers=headers,
                    json={"priority": "should", "expected_updated_at": timestamp},
                ),
                client.patch(
                    f"/api/v1/projects/{missing_project}/requirements/{missing_child}",
                    headers=headers,
                    json={"priority": "should", "expected_updated_at": timestamp},
                ),
            ),
            (
                client.post(
                    f"/api/v1/projects/{values.project_b}/gaps/{values.gap_b}/dismiss",
                    headers={**headers, "Idempotency-Key": "foreign-gap"},
                ),
                client.post(
                    f"/api/v1/projects/{missing_project}/gaps/{missing_child}/dismiss",
                    headers={**headers, "Idempotency-Key": "missing-gap"},
                ),
            ),
            (
                client.get(
                    f"/api/v1/projects/{values.project_b}/scope/draft", headers=headers
                ),
                client.get(
                    f"/api/v1/projects/{missing_project}/scope/draft", headers=headers
                ),
            ),
            (
                client.patch(
                    f"/api/v1/projects/{values.project_b}/scope/draft/sections/summary",
                    headers=headers,
                    json={"value": "tampered", "expected_updated_at": timestamp},
                ),
                client.patch(
                    f"/api/v1/projects/{missing_project}/scope/draft/sections/summary",
                    headers=headers,
                    json={"value": "tampered", "expected_updated_at": timestamp},
                ),
            ),
            (
                client.get(
                    f"/api/v1/projects/{values.project_b}/scope/versions/1", headers=headers
                ),
                client.get(
                    f"/api/v1/projects/{missing_project}/scope/versions/1", headers=headers
                ),
            ),
            (
                client.get(f"/api/v1/jobs/{values.job_b}", headers=headers),
                client.get(f"/api/v1/jobs/{missing_child}", headers=headers),
            ),
        ]

    for foreign, missing in pairs:
        _assert_safe_pair(foreign, missing)

    state = asyncio.run(
        _execute(
            "SELECT p.title, p.deleted_at, c.status AS context_status, "
            "r.priority, g.status AS gap_status, d.content->'sections'->0->>'value' AS summary, "
            "(SELECT count(*) FROM context_sources) AS source_count "
            "FROM projects p "
            "JOIN context_items c ON c.project_id=p.id "
            "JOIN requirements r ON r.project_id=p.id "
            "JOIN gaps g ON g.project_id=p.id "
            "JOIN scope_drafts d ON d.project_id=p.id "
            "WHERE p.id=:project_b",
            values.__dict__,
        )
    ).one()
    assert state.title == "Tenant B project"
    assert state.deleted_at is None
    assert state.context_status == "proposed"
    assert state.priority == "must"
    assert state.gap_status == "open"
    assert state.summary == ""
    assert state.source_count == 1

    log_text = stream.getvalue()
    events = [json.loads(line) for line in log_text.splitlines()]
    denied = [event for event in events if event["event_name"] == "resource.access_denied"]
    assert len(denied) == len(pairs) * 2
    assert {event["reason_code"] for event in denied} == {"not_visible_in_tenant_scope"}
    assert {event["account_id"] for event in denied} == {str(values.account_a)}
    assert {event["resource_type"] for event in denied} == {
        "project",
        "context_source",
        "context_item",
        "requirement",
        "gap",
        "scope_draft",
        "scope_version",
        "job",
    }
    for forbidden in (
        values.context_item_b,
        values.requirement_b,
        values.gap_b,
        values.scope_draft_b,
        values.scope_version_b,
        values.job_b,
    ):
        assert str(forbidden) not in log_text
    for secret in (
        "tenant-b-secret",
        "tenant-b-canonical-secret",
        "tenant-b-context-secret",
        "tenant-b-requirement-title",
        "tenant-b-requirement-secret",
        "tenant-b-gap-secret",
        "tenant-b-question-secret",
        "actual_owner_account_id",
        "cross_tenant_account_id",
    ):
        assert secret not in log_text


def test_repositories_hide_foreign_internal_uuids_and_data_api_roles_are_denied() -> None:
    values = asyncio.run(_seed_two_tenants())

    async def repository_checks() -> tuple[object, ...]:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.session_factory() as session:
                return (
                    await SqlAlchemyProjectRepository(session).get(
                        account_id=values.account_a, project_id=values.project_b
                    ),
                    await SqlAlchemyContextSourceRepository(session).get_source(
                        account_id=values.account_a,
                        project_id=values.project_a,
                        source_id=values.source_b,
                    ),
                    await SqlAlchemyContextItemRepository(session).get_current_for_update(
                        account_id=values.account_a,
                        project_id=values.project_a,
                        item_id=values.context_item_b,
                    ),
                    await SqlAlchemyRequirementRepository(session).get_by_id(
                        account_id=values.account_a,
                        project_id=values.project_a,
                        requirement_id=values.requirement_b,
                    ),
                    await SqlAlchemyClarificationRepository(session).get_gap_for_update(
                        account_id=values.account_a,
                        project_id=values.project_a,
                        gap_id=values.gap_b,
                    ),
                    await SqlAlchemyScopeDraftRepository(session).get_by_id(
                        account_id=values.account_a,
                        project_id=values.project_a,
                        draft_id=values.scope_draft_b,
                    ),
                    await SqlAlchemyScopeVersionRepository(session).get(
                        account_id=values.account_a,
                        project_id=values.project_b,
                        version_no=1,
                    ),
                    await SqlAlchemyJobRepository(session).get_for_account(
                        values.account_a, values.job_b
                    ),
                )
        finally:
            await runtime.close()

    assert asyncio.run(repository_checks()) == (None,) * 8

    table_names = (
        "projects",
        "context_sources",
        "context_source_versions",
        "context_items",
        "requirements",
        "gaps",
        "scope_drafts",
        "scope_versions",
        "jobs",
    )
    security = asyncio.run(
        _execute(
            "SELECT c.relname, c.relrowsecurity, "
            "(SELECT count(*) FROM information_schema.role_table_grants grants "
            " WHERE grants.table_schema='public' AND grants.table_name=c.relname "
            " AND grants.grantee IN ('anon','authenticated')) AS data_api_grants "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname = ANY(:tables) ORDER BY c.relname",
            {"tables": list(table_names)},
        )
    ).all()
    assert len(security) == len(table_names)
    assert all(row.relrowsecurity is True and row.data_api_grants == 0 for row in security)

    async def data_api_exact_uuid_probe() -> None:
        assert TEST_DATABASE_URL is not None
        runtime = DatabaseRuntime(TEST_DATABASE_URL)
        try:
            async with runtime.engine.begin() as connection:
                await connection.execute(text("SET LOCAL ROLE authenticated"))
                await connection.execute(
                    text("SELECT id FROM scope_versions WHERE id=:id"),
                    {"id": values.scope_version_b},
                )
        finally:
            await runtime.close()

    with pytest.raises(DBAPIError):
        asyncio.run(data_api_exact_uuid_probe())
