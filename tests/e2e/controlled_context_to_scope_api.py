"""Controlled synthetic Context-to-Scope scenarios; never used in production."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).parents[2]
API = ROOT / "apps" / "api"
for source in (
    API,
    ROOT / "packages" / "backend-application" / "src",
    ROOT / "packages" / "observability" / "src",
):
    sys.path.insert(0, str(source))

from alembic import command
from alembic.config import Config
from app.infrastructure.db.runtime import DatabaseRuntime
from app.modules.context.application.context_structuring_jobs import (
    ExplicitSyntheticContextStructuringProjects,
    ScheduleContextStructuringCommand,
    ScheduleContextStructuringUseCase,
)
from app.modules.context.infrastructure.context_structuring_jobs import (
    SqlAlchemyContextStructuringJobUnitOfWorkFactory,
)
from app.modules.gaps.application.clarification_service import (
    ClarificationService,
    DismissGapCommand,
)
from app.modules.gaps.application.detection_jobs import (
    ExplicitSyntheticGapDetectionProjects,
    ScheduleGapDetectionCommand,
    ScheduleGapDetectionUseCase,
)
from app.modules.gaps.infrastructure.clarification_repository import (
    SqlAlchemyClarificationUnitOfWorkFactory,
)
from app.modules.gaps.infrastructure.detection_jobs import (
    SqlAlchemyGapDetectionJobUnitOfWorkFactory,
)
from app.modules.gaps.infrastructure.detection_repository import (
    SqlAlchemyGapDetectionSnapshotReader,
)
from app.modules.identity.application.tenant_context import TenantContext
from app.modules.requirements.application.generation_jobs import (
    ExplicitSyntheticRequirementGenerationProjects,
    ScheduleRequirementGenerationCommand,
    ScheduleRequirementGenerationUseCase,
)
from app.modules.requirements.application.requirement_crud_service import (
    RequirementCrudService,
    RequirementVersionConflict,
    UpdateRequirementCommand,
)
from app.modules.requirements.infrastructure.generation_jobs import (
    SqlAlchemyRequirementGenerationJobUnitOfWorkFactory,
)
from app.modules.requirements.infrastructure.generation_repository import (
    SqlAlchemyRequirementContextSnapshotReader,
)
from app.modules.requirements.infrastructure.repository import (
    SqlAlchemyRequirementCrudUnitOfWorkFactory,
)
from app.modules.scope.application.generation_jobs import (
    ExplicitSyntheticScopeProjects,
    ScheduleScopeGenerationCommand,
    ScheduleScopeGenerationUseCase,
    ScopeGenerationBlocked,
)
from app.modules.scope.infrastructure.generation_jobs import (
    SqlAlchemyScopeGenerationJobUnitOfWorkFactory,
    SqlAlchemyScopeGenerationPreflightReader,
)
from aria_backend_application.scope_generation import ScopeDraftAlreadyExistsError
from aria_observability import TraceContext, bind_trace_context, create_event_logger
from sqlalchemy import text

FIXTURE = json.loads(
    Path(__file__)
    .with_name("fixtures")
    .joinpath("context_to_scope_synthetic_fa_v1.json")
    .read_text(encoding="utf-8")
)
if (
    FIXTURE["fixture_set_version"] != "context_to_scope_synthetic_fa_v1"
    or FIXTURE["fixture_id"] != "fa_ctx_scope_0077_001"
):
    raise RuntimeError("0077 fixture identity changed without a versioned contract")
EDIT_FIXTURE = json.loads(
    Path(__file__)
    .with_name("fixtures")
    .joinpath("requirement_edit_to_scope_synthetic_fa_v1.json")
    .read_text(encoding="utf-8")
)
if (
    EDIT_FIXTURE["fixture_set_version"] != "requirement_edit_to_scope_synthetic_fa_v1"
    or EDIT_FIXTURE["fixture_id"] != "fa_req_scope_0078_001"
    or not isinstance(EDIT_FIXTURE["edited_requirement_title"], str)
    or not EDIT_FIXTURE["edited_requirement_title"].strip()
):
    raise RuntimeError("0078 fixture identity or edited title is invalid")
MARKER = FIXTURE["source_text"]
SENSITIVE_SYNTHETIC_TEXT = (
    MARKER,
    "مرجع ساختاریافتهٔ مصنوعی",
    "نیازمندی مصنوعی کنترل‌شده",
    "این خروجی فقط برای آزمون",
    EDIT_FIXTURE["edited_requirement_title"],
)
DEDICATED_NAME = re.compile(r"aria_0077_test(?:_[A-Za-z0-9]+)*")


class DedicatedTestDatabaseRequired(RuntimeError):
    """Refuse every non-0077 throwaway database before migration or reset."""


def database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL", "")
    if (
        not value
        or DEDICATED_NAME.fullmatch(urlsplit(value).path.removeprefix("/")) is None
    ):
        raise DedicatedTestDatabaseRequired
    return value


async def seed(runtime: DatabaseRuntime) -> tuple[TenantContext, UUID]:
    user_id, account_id, membership_id, project_id = (uuid4() for _ in range(4))
    source_id, source_version_id = uuid4(), uuid4()
    async with runtime.engine.begin() as connection:
        # Destructive fixture reset is allowed only after database_url() verified the name.
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
                "VALUES (:id, :account_id, :owner_id, 'Synthetic 0077', :project_type)"
            ),
            {
                "id": project_id,
                "account_id": account_id,
                "owner_id": user_id,
                "project_type": FIXTURE["project_type"],
            },
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
                "(id, account_id, project_id, source_id, version_no, canonical_text, parse_status) "
                "VALUES (:id, :account_id, :project_id, :source_id, 1, :body, 'ready')"
            ),
            {
                "id": source_version_id,
                "account_id": account_id,
                "project_id": project_id,
                "source_id": source_id,
                "body": MARKER,
            },
        )
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=membership_id,
        role="owner",
        membership_status="active",
    ), project_id


async def run_worker(
    stage: str,
    *,
    context: TenantContext,
    project_id: UUID,
    job_id: UUID,
    event_id: UUID,
    context_version: int | None = None,
) -> None:
    worker = ROOT / "apps" / "worker" / ".venv" / "Scripts" / "python.exe"
    script = Path(__file__).with_name("controlled_context_to_scope_worker.py")
    arguments = [
        str(worker),
        str(script),
        stage,
        str(context.account_id),
        str(project_id),
        str(job_id),
        str(event_id),
    ]
    if context_version is not None:
        arguments.extend(("--context-version", str(context_version)))
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        # Expose a bounded exception class for diagnosis, never raw stderr/SQL/credentials.
        kinds = re.findall(
            r"(?m)^SAFE_WORKER_ERROR_CLASS=([A-Za-z_][A-Za-z0-9_]*)\r?$",
            stderr.decode(errors="replace"),
        )
        reason = kinds[-1] if kinds else "unknown_error"
        raise AssertionError(
            f"0077 {stage} Worker failed (exit {process.returncode}, class {reason})"
        )
    if b"CONTROLLED_0077_STAGE=PASS" not in stdout:
        raise AssertionError(f"0077 {stage} Worker did not report PASS")
    if any(
        fragment.encode() in stdout + stderr for fragment in SENSITIVE_SYNTHETIC_TEXT
    ):
        raise AssertionError("Synthetic fixture content leaked through Worker output")


async def job_count(
    runtime: DatabaseRuntime, *, project_id: UUID, job_type: str
) -> int:
    async with runtime.engine.connect() as connection:
        return int(
            await connection.scalar(
                text(
                    "SELECT count(*) FROM jobs WHERE project_id=:id AND job_type=:kind"
                ),
                {"id": project_id, "kind": job_type},
            )
        )


async def main_async(*, requirement_edit: bool = False) -> None:
    url = database_url()  # Must precede migration or any database mutation.
    runtime = DatabaseRuntime(url)
    stream = StringIO()
    logger = create_event_logger(
        service="aria-api",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    trace_scope = bind_trace_context(
        TraceContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    )
    trace_scope.__enter__()
    try:
        context, project_id = await seed(runtime)
        approved = frozenset({(context.account_id, project_id)})
        context_scheduler = ScheduleContextStructuringUseCase(
            SqlAlchemyContextStructuringJobUnitOfWorkFactory(runtime.session_factory),
            logger,
            ExplicitSyntheticContextStructuringProjects(approved),
        )
        first = await context_scheduler.execute(
            context,
            ScheduleContextStructuringCommand(
                project_id=project_id,
                correlation_id=uuid4(),
                idempotency_key="controlled-0077-context",
            ),
        )
        async with runtime.engine.connect() as connection:
            first_event_id = await connection.scalar(
                text(
                    "SELECT id FROM outbox_events WHERE event_type="
                    "'context.structuring_requested.v1' AND payload->>'jobId'=:job"
                ),
                {"job": str(first.job_id)},
            )
        if not isinstance(first_event_id, UUID):
            raise TypeError("AI-01 Outbox event missing")
        await run_worker(
            "context",
            context=context,
            project_id=project_id,
            job_id=first.job_id,
            event_id=first_event_id,
        )
        async with runtime.engine.connect() as connection:
            version = await connection.scalar(
                text("SELECT current_context_version FROM projects WHERE id=:id"),
                {"id": project_id},
            )
        if not isinstance(version, int) or version < 1:
            raise AssertionError("AI-01 did not establish Context Version N")

        req_scheduler = ScheduleRequirementGenerationUseCase(
            snapshot_reader=SqlAlchemyRequirementContextSnapshotReader(
                runtime.session_factory
            ),
            unit_of_work_factory=SqlAlchemyRequirementGenerationJobUnitOfWorkFactory(
                runtime.session_factory
            ),
            synthetic_authorizer=ExplicitSyntheticRequirementGenerationProjects(
                approved
            ),
            event_logger=logger,
        )
        requirement = await req_scheduler.execute(
            ScheduleRequirementGenerationCommand(
                context.account_id,
                project_id,
                version,
                uuid4(),
            )
        )
        await run_worker(
            "requirement",
            context=context,
            project_id=project_id,
            job_id=requirement.job_id,
            event_id=requirement.outbox_event_id,
            context_version=version,
        )

        edited_requirement_id: UUID | None = None
        original_title: str | None = None
        edited_updated_at: str | None = None
        if requirement_edit:
            async with runtime.engine.connect() as connection:
                original = (
                    (
                        await connection.execute(
                            text(
                                "SELECT id, title, updated_at, status FROM public.requirements "
                                "WHERE account_id=:account AND project_id=:project "
                                "AND context_version=:version"
                            ),
                            {
                                "account": context.account_id,
                                "project": project_id,
                                "version": version,
                            },
                        )
                    )
                    .mappings()
                    .one()
                )
            if original["status"] != "draft":
                raise AssertionError("Synthetic Requirement is not editable draft")
            original_title = str(original["title"])
            requirement_service = RequirementCrudService(
                SqlAlchemyRequirementCrudUnitOfWorkFactory(runtime.session_factory),
                logger,
            )
            edited = await requirement_service.update(
                context,
                project_id=project_id,
                requirement_id=original["id"],
                command=UpdateRequirementCommand(
                    expected_updated_at=original["updated_at"],
                    title=EDIT_FIXTURE["edited_requirement_title"],
                ),
            )
            if (
                edited.id != original["id"]
                or edited.context_version != version
                or edited.status != "draft"
                or edited.title != EDIT_FIXTURE["edited_requirement_title"]
                or edited.updated_at == original["updated_at"]
            ):
                raise AssertionError("Authorized Requirement edit did not persist a new revision")
            try:
                await requirement_service.update(
                    context,
                    project_id=project_id,
                    requirement_id=original["id"],
                    command=UpdateRequirementCommand(
                        expected_updated_at=original["updated_at"],
                        title=original_title,
                    ),
                )
            except RequirementVersionConflict:
                pass
            else:
                raise AssertionError("Stale Requirement edit did not fail closed")
            edited_requirement_id = edited.id
            edited_updated_at = edited.updated_at.isoformat()

        gap_scheduler = ScheduleGapDetectionUseCase(
            snapshot_reader=SqlAlchemyGapDetectionSnapshotReader(
                runtime.session_factory
            ),
            unit_of_work_factory=SqlAlchemyGapDetectionJobUnitOfWorkFactory(
                runtime.session_factory
            ),
            synthetic_authorizer=ExplicitSyntheticGapDetectionProjects(approved),
            event_logger=logger,
        )
        gap_job = await gap_scheduler.execute(
            ScheduleGapDetectionCommand(
                context.account_id,
                project_id,
                version,
                uuid4(),
            )
        )
        await run_worker(
            "gap",
            context=context,
            project_id=project_id,
            job_id=gap_job.job_id,
            event_id=gap_job.outbox_event_id,
            context_version=version,
        )

        scope_scheduler = ScheduleScopeGenerationUseCase(
            preflight_reader=SqlAlchemyScopeGenerationPreflightReader(
                runtime.session_factory
            ),
            unit_of_work_factory=SqlAlchemyScopeGenerationJobUnitOfWorkFactory(
                runtime.session_factory
            ),
            synthetic_authorizer=ExplicitSyntheticScopeProjects(approved),
            event_logger=logger,
        )
        scope_command = ScheduleScopeGenerationCommand(
            context.account_id, project_id, version, uuid4()
        )
        before = await job_count(
            runtime, project_id=project_id, job_type="scope_generation"
        )
        try:
            await scope_scheduler.execute(scope_command)
        except ScopeGenerationBlocked:
            pass
        else:
            raise AssertionError("Open Critical Gap did not block AI-05")
        if (
            await job_count(runtime, project_id=project_id, job_type="scope_generation")
            != before
        ):
            raise AssertionError("Blocked AI-05 created a Job")

        async with runtime.engine.connect() as connection:
            gaps = (
                (
                    await connection.execute(
                        text(
                            "SELECT id FROM gaps WHERE account_id=:account AND project_id=:project "
                            "AND context_version=:version AND status='open' AND severity='critical'"
                        ),
                        {
                            "account": context.account_id,
                            "project": project_id,
                            "version": version,
                        },
                    )
                )
                .scalars()
                .all()
            )
        if not gaps:
            raise AssertionError("AI-03 did not produce an open Critical Gap")
        clarification = ClarificationService(
            SqlAlchemyClarificationUnitOfWorkFactory(runtime.session_factory),
            logger,
        )
        for gap_id in gaps:
            await clarification.dismiss_gap(
                context,
                project_id=project_id,
                gap_id=gap_id,
                command=DismissGapCommand(f"controlled-0077-dismiss-{gap_id}"),
            )
        scope = await scope_scheduler.execute(scope_command)
        if requirement_edit:
            async with runtime.engine.connect() as connection:
                scope_job_payload = await connection.scalar(
                    text(
                        "SELECT payload_ref FROM public.jobs "
                        "WHERE id=:job AND account_id=:account AND project_id=:project"
                    ),
                    {
                        "job": scope.job_id,
                        "account": context.account_id,
                        "project": project_id,
                    },
                )
            if not isinstance(scope_job_payload, dict) or scope_job_payload.get(
                "requirement_revisions"
            ) != [{"id": str(edited_requirement_id), "updated_at": edited_updated_at}]:
                raise AssertionError("AI-05 did not pin the edited Requirement revision")
        await run_worker(
            "scope",
            context=context,
            project_id=project_id,
            job_id=scope.job_id,
            event_id=scope.outbox_event_id,
            context_version=version,
        )
        if requirement_edit:
            async with runtime.engine.connect() as connection:
                draft_content = await connection.scalar(
                    text(
                        "SELECT content FROM public.scope_drafts "
                        "WHERE account_id=:account AND project_id=:project "
                        "AND context_version=:version"
                    ),
                    {
                        "account": context.account_id,
                        "project": project_id,
                        "version": version,
                    },
                )
            if not isinstance(draft_content, dict):
                raise AssertionError("AI-05 did not persist a Scope Draft")
            requirement_sections = [
                section
                for section in draft_content.get("sections", [])
                if isinstance(section, dict) and section.get("section_id") == "requirements"
            ]
            if len(requirement_sections) != 1:
                raise AssertionError("Scope Draft has no unique Requirements section")
            section = requirement_sections[0]
            if section.get("value") != [
                {
                    "item_id": str(edited_requirement_id),
                    "text": EDIT_FIXTURE["edited_requirement_title"],
                    "priority": "must",
                }
            ] or section.get("trace", {}).get("requirement_ids") != [
                str(edited_requirement_id)
            ]:
                raise AssertionError("Scope Draft did not use the persisted human edit")
            if original_title == EDIT_FIXTURE["edited_requirement_title"]:
                raise AssertionError("Synthetic edit did not change the Requirement title")
        try:
            await scope_scheduler.execute(scope_command)
        except ScopeDraftAlreadyExistsError:
            pass
        else:
            raise AssertionError("Existing Scope Draft did not reject regeneration")
        async with runtime.engine.connect() as connection:
            state = (
                (
                    await connection.execute(
                        text(
                            "SELECT (SELECT count(*) FROM requirements WHERE account_id=:account "
                            "AND project_id=:project AND context_version=:version) AS requirements, "
                            "(SELECT count(*) FROM gaps WHERE account_id=:account AND project_id=:project "
                            "AND context_version=:version AND status='dismissed') AS dismissed, "
                            "(SELECT count(*) FROM scope_drafts WHERE account_id=:account "
                            "AND project_id=:project AND context_version=:version) AS drafts, "
                            "(SELECT status FROM jobs WHERE id=:job) AS job_status"
                        ),
                        {
                            "account": context.account_id,
                            "project": project_id,
                            "version": version,
                            "job": scope.job_id,
                        },
                    )
                )
                .mappings()
                .one()
            )
        if (
            state["requirements"] < 1
            or state["dismissed"] != len(gaps)
            or state["drafts"] != 1
            or state["job_status"] != "succeeded"
        ):
            raise AssertionError(f"0077 state assertions failed: {state!r}")
        if any(fragment in stream.getvalue() for fragment in SENSITIVE_SYNTHETIC_TEXT):
            raise AssertionError("Synthetic fixture content leaked into API logs")
        print(
            "CONTROLLED_0078_E2E=PASS"
            if requirement_edit
            else "CONTROLLED_0077_E2E=PASS"
        )
    finally:
        trace_scope.__exit__(None, None, None)
        await runtime.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirement-edit", action="store_true")
    arguments = parser.parse_args()
    try:
        os.environ["DATABASE_URL"] = database_url()
        command.upgrade(Config(str(API / "alembic.ini")), "head")
        asyncio.run(main_async(requirement_edit=arguments.requirement_edit))
    except Exception as error:  # noqa: BLE001 - diagnostic boundary redacts data
        print(f"SAFE_API_ERROR_CLASS={type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
