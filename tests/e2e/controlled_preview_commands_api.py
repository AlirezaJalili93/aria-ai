"""Test-only API process bridge; stdout is a captured response pipe, never a log."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).parents[2]
for source in (
    ROOT / "apps/api",
    ROOT / "packages/backend-application/src",
    ROOT / "packages/observability/src",
):
    sys.path.insert(0, str(source))

from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.generation.application.preview import PreviewPublicationService
from app.modules.generation.infrastructure.preview_repository import (
    PostgresPreviewCommands,
)
from app.modules.identity.application.membership_resolution import (
    ActiveMembershipRequired,
)
from app.modules.identity.application.ports import AuthenticatedIdentity
from app.modules.identity.application.tenant_context import ResolveTenantContextUseCase
from app.modules.identity.infrastructure.membership_resolution import (
    SqlAlchemyMembershipResolver,
)
from aria_backend_application.preview_delivery import PreviewError
from sqlalchemy import make_url


async def execute(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PreviewError("VALIDATION_FAILED")
    operation = value.get("operation")
    fields = {
        "publish": {"artifact_version_id", "source_hash"},
        "issue": {"publication_id", "expires_at"},
        "revoke": {"publication_id"},
    }
    common = {"operation", "subject_id", "account_id", "project_id", "key"}
    if operation not in fields or set(value) != common | fields[operation]:
        raise PreviewError("VALIDATION_FAILED")
    if not isinstance(value["key"], str):
        raise PreviewError("VALIDATION_FAILED")
    url = make_url(os.environ["TEST_DATABASE_URL"])
    if url.host != "127.0.0.1" or url.database != "aria_0102_joined":
        raise PreviewError("FEATURE_NOT_ENABLED")
    runtime = DatabaseRuntime(str(url.render_as_string(hide_password=False)))
    try:
        context = await ResolveTenantContextUseCase(
            SqlAlchemyMembershipResolver(runtime.session_factory)
        ).execute(
            AuthenticatedIdentity(UUID(value["subject_id"])), UUID(value["account_id"])
        )
        sources: frozenset[tuple[UUID, str]] = frozenset()
        if operation == "publish":
            if not isinstance(value["source_hash"], str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", value["source_hash"]
            ):
                raise PreviewError("VALIDATION_FAILED")
            sources = frozenset(
                {(UUID(value["artifact_version_id"]), value["source_hash"])}
            )
        service = PreviewPublicationService(
            PostgresPreviewCommands(runtime.session_factory), synthetic_sources=sources
        )
        project, key = UUID(value["project_id"]), value["key"]
        if operation == "publish":
            result = await service.publish(
                context,
                project_id=project,
                artifact_version_id=UUID(value["artifact_version_id"]),
                key=key,
            )
            return {
                "status": "ok",
                "publication_id": str(result.publication_id),
                "job_id": str(result.job_id),
                "replayed": result.replayed,
            }
        publication = UUID(value["publication_id"])
        if operation == "issue":
            issued = await service.issue(
                context,
                project_id=project,
                publication_id=publication,
                key=key,
                expires_at=datetime.fromisoformat(value["expires_at"]),
            )
            return {
                "status": "ok",
                "publication_id": str(issued.publication_id),
                "token": issued.token,
                "token_available": issued.token_available,
                "replayed": issued.replayed,
            }
        await service.revoke(
            context, project_id=project, publication_id=publication, key=key
        )
        return {"status": "ok"}
    finally:
        await runtime.close()


def response() -> dict[str, object]:
    try:
        response = asyncio.run(execute(json.loads(sys.stdin.read())))
    except PreviewError as exc:
        response = {"status": "failed", "error_code": exc.code}
    except ActiveMembershipRequired:
        response = {"status": "failed", "error_class": "ActiveMembershipRequired"}
    except (ValueError, TypeError, KeyError):
        response = {"status": "failed", "error_code": "VALIDATION_FAILED"}
    except Exception as error:
        # No stderr traceback, raw SQL, URL, exception message or captured request is emitted.
        # Preserve causality only inside this private process; main catches the wrapper and
        # emits only its bounded code, never a traceback/cause/message.
        raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE") from error
    return response


def main() -> None:
    try:
        result = response()
    except PreviewError as exc:
        result = {"status": "failed", "error_code": exc.code}
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    main()
