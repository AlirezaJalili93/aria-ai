from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

REPOSITORY_ROOT = Path(__file__).parents[2]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
for source_root in (
    API_ROOT,
    REPOSITORY_ROOT / "packages" / "backend-application" / "src",
    REPOSITORY_ROOT / "packages" / "observability" / "src",
):
    sys.path.insert(0, str(source_root))

from alembic import command
from alembic.config import Config
from app.core.config import ApiSettings
from app.infrastructure.db.runtime import DatabaseRuntime
from app.main import create_app
from app.modules.context.application.context_structuring_jobs import (
    ExplicitSyntheticContextStructuringProjects,
    ScheduleContextStructuringUseCase,
)
from app.modules.context.infrastructure.context_structuring_jobs import (
    SqlAlchemyContextStructuringJobUnitOfWorkFactory,
)
from app.modules.identity.application.ports import (
    AuthenticatedIdentity,
    InvalidAccessToken,
)
from app.modules.identity.application.tenant_context import TenantContext
from aria_observability import create_event_logger
from fastapi.testclient import TestClient
from sqlalchemy import text

SYNTHETIC_MARKER = "SYNTHETIC_0072_FIXTURE_ONLY"
DEDICATED_DATABASE_PATTERN = re.compile(r"aria_0072_test(?:_[A-Za-z0-9]+)*")


def _assert_dedicated_test_database(database_url: str) -> None:
    database_name = urlsplit(database_url).path.removeprefix("/")
    if DEDICATED_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise RuntimeError(
            "Controlled 0072 E2E requires a dedicated aria_0072_test... database"
        )


class _TokenVerifier:
    provider_name = "controlled-synthetic-e2e"

    def __init__(self, token: str, subject_id: UUID) -> None:
        self._token = token
        self._subject_id = subject_id

    async def verify(self, token: str) -> AuthenticatedIdentity:
        if token != self._token:
            raise InvalidAccessToken
        return AuthenticatedIdentity(subject=self._subject_id)


class _TenantResolver:
    def __init__(self, context: TenantContext) -> None:
        self._context = context

    async def execute(
        self, identity: AuthenticatedIdentity, account_id: UUID
    ) -> TenantContext:
        if identity.subject != self._context.subject_id or account_id != self._context.account_id:
            raise AssertionError("Controlled fixture identity mismatch")
        return self._context


async def _seed(database_url: str) -> tuple[TenantContext, UUID]:
    runtime = DatabaseRuntime(database_url)
    user_id, account_id, membership_id, project_id = (uuid4() for _ in range(4))
    source_id, source_version_id = uuid4(), uuid4()
    try:
        async with runtime.engine.begin() as connection:
            await connection.execute(text("TRUNCATE public.accounts CASCADE"))
            await connection.execute(
                text("INSERT INTO profiles (user_id) VALUES (:id)"), {"id": user_id}
            )
            await connection.execute(
                text("INSERT INTO accounts (id) VALUES (:id)"), {"id": account_id}
            )
            await connection.execute(
                text(
                    "INSERT INTO account_memberships (id, account_id, user_id, role, status) "
                    "VALUES (:id, :account_id, :user_id, 'owner', 'active')"
                ),
                {"id": membership_id, "account_id": account_id, "user_id": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO projects (id, account_id, owner_id, title, project_type) "
                    "VALUES (:id, :account_id, :owner_id, 'Synthetic 0072', 'landing')"
                ),
                {"id": project_id, "account_id": account_id, "owner_id": user_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO context_sources "
                    "(id, account_id, project_id, source_type, status, created_by) "
                    "VALUES (:id, :account_id, :project_id, 'text', 'ready', :created_by)"
                ),
                {
                    "id": source_id,
                    "account_id": account_id,
                    "project_id": project_id,
                    "created_by": user_id,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO context_source_versions "
                    "(id, account_id, project_id, source_id, version_no, canonical_text, "
                    "parse_status) VALUES (:id, :account_id, :project_id, :source_id, 1, "
                    ":canonical_text, 'ready')"
                ),
                {
                    "id": source_version_id,
                    "account_id": account_id,
                    "project_id": project_id,
                    "source_id": source_id,
                    "canonical_text": SYNTHETIC_MARKER,
                },
            )
    finally:
        await runtime.close()
    return (
        TenantContext(
            subject_id=user_id,
            account_id=account_id,
            membership_id=membership_id,
            role="owner",
            membership_status="active",
        ),
        project_id,
    )


async def _outbox_id(runtime: DatabaseRuntime, job_id: UUID) -> UUID:
    async with runtime.engine.connect() as connection:
        value = await connection.scalar(
            text(
                "SELECT id FROM outbox_events WHERE event_type="
                "'context.structuring_requested.v1' "
                "AND payload->>'jobId'=:job_id"
            ),
            {"job_id": str(job_id)},
        )
    if not isinstance(value, UUID):
        raise TypeError("Controlled E2E Outbox event was not persisted")
    return value


def main() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is required")
    _assert_dedicated_test_database(database_url)
    os.environ["DATABASE_URL"] = database_url
    command.upgrade(Config(str(API_ROOT / "alembic.ini")), "head")
    context, project_id = asyncio.run(_seed(database_url))
    runtime = DatabaseRuntime(database_url)
    token = "controlled-synthetic-e2e-token"
    event_logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
    )
    use_case = ScheduleContextStructuringUseCase(
        SqlAlchemyContextStructuringJobUnitOfWorkFactory(runtime.session_factory),
        event_logger,
        ExplicitSyntheticContextStructuringProjects(
            frozenset({(context.account_id, project_id)})
        ),
    )
    app = create_app(
        ApiSettings(
            app_env="test",
            app_version="0.1.0",
            log_level="INFO",
            database_url=database_url,
            context_structuring_enabled=True,
        ),
        access_token_verifier=_TokenVerifier(token, context.subject_id),
        tenant_context_resolver=_TenantResolver(context),
        context_structuring_use_case=use_case,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Account-ID": str(context.account_id),
        "Idempotency-Key": "controlled-synthetic-e2e",
    }
    path = f"/api/v1/projects/{project_id}/context-structuring"
    with TestClient(app) as client:
        accepted = client.post(path, headers=headers)
        replay = client.post(path, headers=headers)
        conflict = client.post(
            path,
            headers={**headers, "Idempotency-Key": "controlled-synthetic-e2e-conflict"},
        )
        if accepted.status_code != 202 or replay.json() != accepted.json():
            raise AssertionError("Controlled HTTP command or exact replay failed")
        if conflict.status_code != 409:
            raise AssertionError("Concurrent active Job did not fail with 409")
        job_id = UUID(accepted.json()["job_id"])
        if client.portal is None:
            raise AssertionError("Controlled TestClient portal is unavailable")
        outbox_event_id = client.portal.call(_outbox_id, runtime, job_id)
        client.portal.call(runtime.close)
    print(
        "E2E_STATE="
        + json.dumps(
            {
                "account_id": str(context.account_id),
                "project_id": str(project_id),
                "job_id": str(job_id),
                "outbox_event_id": str(outbox_event_id),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
