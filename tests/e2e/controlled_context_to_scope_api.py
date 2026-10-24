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
    ClarificationNotFound,
    ClarificationService,
    CreateClarificationQuestionCommand,
    DismissGapCommand,
    ResolveClarificationCommand,
)
from app.modules.gaps.application.detection_jobs import (
    ExplicitSyntheticGapDetectionProjects,
    ScheduleGapDetectionCommand,
    ScheduleGapDetectionUseCase,
)
from app.modules.gaps.domain.clarification import (
    Clarification,
    ClarificationValidationError,
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
CLARIFICATION_QUESTION_1 = "برای رفع ابهام مصنوعی، مخاطب اصلی چیست؟"
CLARIFICATION_QUESTION_2 = "برای رفع ابهام مصنوعی، اقدام اصلی چیست؟"
CLARIFICATION_ANSWER_1 = "مخاطب مصنوعی، تیم‌های کوچک خدماتی هستند."
CLARIFICATION_ANSWER_2 = "اقدام مصنوعی اصلی، ثبت درخواست مشاوره است."
SENSITIVE_SYNTHETIC_TEXT = (
    MARKER,
    "مرجع ساختاریافتهٔ مصنوعی",
    "نیازمندی مصنوعی کنترل‌شده",
    "این خروجی فقط برای آزمون",
    EDIT_FIXTURE["edited_requirement_title"],
    CLARIFICATION_QUESTION_1,
    CLARIFICATION_QUESTION_2,
    CLARIFICATION_ANSWER_1,
    CLARIFICATION_ANSWER_2,
)
DEDICATED_NAME = re.compile(r"aria_0077_test(?:_[A-Za-z0-9]+)*")
SAFE_STAGE = "startup"


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


async def seed(
    runtime: DatabaseRuntime, *, provider_timeout_retry: bool = False
) -> tuple[TenantContext, UUID]:
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
        if provider_timeout_retry:
            await connection.execute(
                text(
                    "INSERT INTO provider_price_versions "
                    "(provider, model, pricing_version, currency, input_rate_per_1m, "
                    "cached_input_rate_per_1m, output_rate_per_1m, effective_from) "
                    "VALUES ('synthetic', 'context-structuring-fake-v1', "
                    "'synthetic-zero-v1', 'USD', 0, 0, 0, '2026-01-01T00:00:00Z') "
                    "ON CONFLICT (provider, model, pricing_version) DO NOTHING"
                )
            )
            matching_price = await connection.scalar(
                text(
                    "SELECT count(*) FROM provider_price_versions "
                    "WHERE provider='synthetic' AND model='context-structuring-fake-v1' "
                    "AND pricing_version='synthetic-zero-v1' AND currency='USD' "
                    "AND input_rate_per_1m=0 AND cached_input_rate_per_1m=0 "
                    "AND output_rate_per_1m=0 "
                    "AND effective_from='2026-01-01T00:00:00Z'"
                )
            )
            if matching_price != 1:
                raise AssertionError("Synthetic price fixture does not match its frozen identity")
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=membership_id,
        role="owner",
        membership_status="active",
    ), project_id


async def seed_other_tenant(runtime: DatabaseRuntime) -> TenantContext:
    user_id, account_id, membership_id = (uuid4() for _ in range(3))
    async with runtime.engine.begin() as connection:
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
    return TenantContext(
        subject_id=user_id,
        account_id=account_id,
        membership_id=membership_id,
        role="owner",
        membership_status="active",
    )


async def scope_effect_counts(
    runtime: DatabaseRuntime, *, account_id: UUID, project_id: UUID
) -> tuple[int, int, int, int]:
    async with runtime.engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM jobs WHERE account_id=:account "
                        "AND project_id=:project AND job_type='scope_generation') AS jobs, "
                        "(SELECT count(*) FROM outbox_events WHERE account_id=:account "
                        "AND event_type='scope.generation_requested.v1' "
                        "AND payload->>'projectId'=:project_text) AS events, "
                        "(SELECT count(*) FROM usage_records u JOIN jobs j ON j.id=u.job_id "
                        "WHERE j.account_id=:account AND j.project_id=:project "
                        "AND j.job_type='scope_generation') AS usage, "
                        "(SELECT count(*) FROM scope_drafts WHERE account_id=:account "
                        "AND project_id=:project) AS drafts"
                    ),
                    {
                        "account": account_id,
                        "project": project_id,
                        "project_text": str(project_id),
                    },
                )
            )
            .mappings()
            .one()
        )
    return tuple(int(row[key]) for key in ("jobs", "events", "usage", "drafts"))


async def semantic_state_snapshot(
    runtime: DatabaseRuntime,
    *,
    account_id: UUID,
    project_id: UUID,
    context_version: int,
) -> tuple[object, ...]:
    async with runtime.engine.connect() as connection:
        project_version = await connection.scalar(
            text(
                "SELECT current_context_version FROM projects "
                "WHERE id=:project AND account_id=:account"
            ),
            {"account": account_id, "project": project_id},
        )
        context_rows = (
            (
                await connection.execute(
                    text(
                        "SELECT id, status, updated_at FROM context_items "
                        "WHERE account_id=:account AND project_id=:project "
                        "AND context_version=:version ORDER BY id"
                    ),
                    {
                        "account": account_id,
                        "project": project_id,
                        "version": context_version,
                    },
                )
            )
            .tuples()
            .all()
        )
        requirement_rows = (
            (
                await connection.execute(
                    text(
                        "SELECT id, status, updated_at FROM requirements "
                        "WHERE account_id=:account AND project_id=:project "
                        "AND context_version=:version ORDER BY id"
                    ),
                    {
                        "account": account_id,
                        "project": project_id,
                        "version": context_version,
                    },
                )
            )
            .tuples()
            .all()
        )
        source_counts = (
            (
                await connection.execute(
                    text(
                        "SELECT "
                        "(SELECT count(*) FROM context_sources WHERE account_id=:account "
                        "AND project_id=:project) AS sources, "
                        "(SELECT count(*) FROM context_source_versions WHERE account_id=:account "
                        "AND project_id=:project) AS versions"
                    ),
                    {"account": account_id, "project": project_id},
                )
            )
            .tuples()
            .one()
        )
    return (
        project_version,
        tuple(context_rows),
        tuple(requirement_rows),
        tuple(source_counts),
    )


async def run_worker(
    stage: str,
    *,
    context: TenantContext,
    project_id: UUID,
    job_id: UUID,
    event_id: UUID,
    context_version: int | None = None,
    provider_timeout_retry: bool = False,
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
    if provider_timeout_retry:
        if stage != "context":
            raise ValueError("Provider timeout scenario is AI-01 only")
        arguments.append("--provider-timeout-retry")
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


async def main_async(
    *,
    requirement_edit: bool = False,
    provider_timeout_retry: bool = False,
    clarification_resolution: bool = False,
) -> None:
    global SAFE_STAGE
    if sum((requirement_edit, provider_timeout_retry, clarification_resolution)) > 1:
        raise ValueError("Controlled scenarios must run independently")
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
        context, project_id = await seed(
            runtime, provider_timeout_retry=provider_timeout_retry
        )
        other_context = (
            await seed_other_tenant(runtime) if clarification_resolution else None
        )
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
            provider_timeout_retry=provider_timeout_retry,
        )
        if provider_timeout_retry:
            async with runtime.engine.connect() as connection:
                attempts = (
                    (
                        await connection.execute(
                            text(
                                "SELECT provider_attempt_id, status, accounting_status, "
                                "input_tokens, cached_input_tokens, output_tokens, "
                                "estimated_cost, retry_no, account_id, project_id, job_id "
                                "FROM usage_records WHERE account_id=:account "
                                "AND project_id=:project AND job_id=:job ORDER BY retry_no"
                            ),
                            {
                                "account": context.account_id,
                                "project": project_id,
                                "job": first.job_id,
                            },
                        )
                    )
                    .mappings()
                    .all()
                )
            if len(attempts) != 2 or len({row["provider_attempt_id"] for row in attempts}) != 2:
                raise AssertionError("Two invocations must persist exactly two UsageRecords")
            failed, succeeded = attempts
            if (
                failed["retry_no"] != 0
                or failed["status"] != "failed"
                or failed["accounting_status"] != "unavailable"
                or any(
                    failed[field] is not None
                    for field in (
                        "input_tokens", "cached_input_tokens", "output_tokens", "estimated_cost"
                    )
                )
                or succeeded["retry_no"] != 1
                or succeeded["status"] != "success"
                or succeeded["accounting_status"] != "complete"
                or any(row["job_id"] != first.job_id for row in attempts)
            ):
                raise AssertionError("Synthetic timeout Usage or Job lineage is invalid")
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
        blocked_scope_command = ScheduleScopeGenerationCommand(
            context.account_id, project_id, version, uuid4()
        )
        before = await scope_effect_counts(
            runtime, account_id=context.account_id, project_id=project_id
        )
        try:
            await scope_scheduler.execute(blocked_scope_command)
        except ScopeGenerationBlocked:
            pass
        else:
            raise AssertionError("Open Critical Gap did not block AI-05")
        if await scope_effect_counts(
            runtime, account_id=context.account_id, project_id=project_id
        ) != before:
            raise AssertionError("Blocked AI-05 created a side effect")

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
        if clarification_resolution:
            if other_context is None:
                raise AssertionError("Cross-tenant fixture is missing")
            questions: dict[UUID, tuple[Clarification, Clarification]] = {}
            for gap_index, gap_id in enumerate(gaps, start=1):
                SAFE_STAGE = f"create_question_1_gap_{gap_index}"
                first_question = await clarification.create_question(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    command=CreateClarificationQuestionCommand(
                        CLARIFICATION_QUESTION_1,
                        f"controlled-0082-question-1-{gap_id}",
                    ),
                )
                SAFE_STAGE = f"create_question_2_gap_{gap_index}"
                second_question = await clarification.create_question(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    command=CreateClarificationQuestionCommand(
                        CLARIFICATION_QUESTION_2,
                        f"controlled-0082-question-2-{gap_id}",
                    ),
                )
                questions[gap_id] = (first_question, second_question)

            semantic_before_answers = await semantic_state_snapshot(
                runtime,
                account_id=context.account_id,
                project_id=project_id,
                context_version=version,
            )
            first_gap = gaps[0]
            first_question = questions[first_gap][0]
            try:
                await clarification.resolve_question(
                    context,
                    project_id=project_id,
                    gap_id=first_gap,
                    clarification_id=first_question.id,
                    command=ResolveClarificationCommand(
                        "provided_information", "   ", "user", "controlled-0082-empty"
                    ),
                )
            except ClarificationValidationError:
                pass
            else:
                raise AssertionError("Empty Clarification answer did not fail closed")
            try:
                await clarification.create_question(
                    other_context,
                    project_id=project_id,
                    gap_id=first_gap,
                    command=CreateClarificationQuestionCommand(
                        "سؤال مصنوعی tenant دیگر",
                        "controlled-0082-cross-tenant-question",
                    ),
                )
            except ClarificationNotFound:
                pass
            else:
                raise AssertionError("Cross-tenant Clarification create did not fail closed")
            try:
                await clarification.resolve_question(
                    other_context,
                    project_id=project_id,
                    gap_id=first_gap,
                    clarification_id=first_question.id,
                    command=ResolveClarificationCommand(
                        "provided_information",
                        "پاسخ مصنوعی tenant دیگر",
                        "user",
                        "controlled-0082-cross-tenant-answer",
                    ),
                )
            except ClarificationNotFound:
                pass
            else:
                raise AssertionError("Cross-tenant Clarification answer did not fail closed")

            for gap_id, (question_1, _) in questions.items():
                answer_command = ResolveClarificationCommand(
                    "provided_information",
                    CLARIFICATION_ANSWER_1,
                    "user",
                    f"controlled-0082-answer-1-{gap_id}",
                )
                first_resolution = await clarification.resolve_question(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=question_1.id,
                    command=answer_command,
                )
                replayed = await clarification.resolve_question(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=question_1.id,
                    command=answer_command,
                )
                if first_resolution.id != replayed.id:
                    raise AssertionError("Resolution replay created a second audit row")

            for gap_id in gaps:
                history = await clarification.list_clarifications(
                    context, project_id=project_id, gap_id=gap_id
                )
                if (
                    len(history) != 2
                    or [entry.question.status for entry in history] != ["answered", "open"]
                    or sum(entry.resolution is not None for entry in history) != 1
                    or history[0].resolution is None
                    or history[0].resolution.author_type != "user"
                    or history[0].resolution.author_id != context.subject_id
                    or history[0].resolution.actor_id != context.subject_id
                ):
                    raise AssertionError("First answer did not preserve the open Gap sequence")
            async with runtime.engine.connect() as connection:
                still_open = await connection.scalar(
                    text(
                        "SELECT count(*) FROM gaps WHERE account_id=:account "
                        "AND project_id=:project AND id=ANY(:gaps) "
                        "AND status='open' AND resolved_at IS NULL"
                    ),
                    {
                        "account": context.account_id,
                        "project": project_id,
                        "gaps": list(gaps),
                    },
                )
            if still_open != len(gaps):
                raise AssertionError("Gap resolved before all upfront questions were answered")
            mid_effects = await scope_effect_counts(
                runtime, account_id=context.account_id, project_id=project_id
            )
            try:
                await scope_scheduler.execute(
                    ScheduleScopeGenerationCommand(
                        context.account_id, project_id, version, uuid4()
                    )
                )
            except ScopeGenerationBlocked:
                pass
            else:
                raise AssertionError("AI-05 was not blocked after the first answer")
            if await scope_effect_counts(
                runtime, account_id=context.account_id, project_id=project_id
            ) != mid_effects:
                raise AssertionError("Mid-clarification AI-05 created a side effect")

            for gap_id, (_, question_2) in questions.items():
                await clarification.resolve_question(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    clarification_id=question_2.id,
                    command=ResolveClarificationCommand(
                        "provided_information",
                        CLARIFICATION_ANSWER_2,
                        "user",
                        f"controlled-0082-answer-2-{gap_id}",
                    ),
                )
                history = await clarification.list_clarifications(
                    context, project_id=project_id, gap_id=gap_id
                )
                if (
                    len(history) != 2
                    or any(entry.question.status != "answered" for entry in history)
                    or any(entry.resolution is None for entry in history)
                    or any(
                        entry.resolution is not None
                        and (
                            entry.resolution.author_type != "user"
                            or entry.resolution.author_id != context.subject_id
                            or entry.resolution.actor_id != context.subject_id
                        )
                        for entry in history
                    )
                ):
                    raise AssertionError("Second answer did not complete Clarification history")
            if await semantic_state_snapshot(
                runtime,
                account_id=context.account_id,
                project_id=project_id,
                context_version=version,
            ) != semantic_before_answers:
                raise AssertionError("Clarification answers mutated canonical semantic input")
        else:
            for gap_id in gaps:
                await clarification.dismiss_gap(
                    context,
                    project_id=project_id,
                    gap_id=gap_id,
                    command=DismissGapCommand(f"controlled-0077-dismiss-{gap_id}"),
                )
        scope_command = ScheduleScopeGenerationCommand(
            context.account_id, project_id, version, uuid4()
        )
        scope = await scope_scheduler.execute(scope_command)
        if requirement_edit or clarification_resolution:
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
            if not isinstance(scope_job_payload, dict):
                raise AssertionError("AI-05 Job payload is invalid")
            if requirement_edit and scope_job_payload.get("requirement_revisions") != [
                {"id": str(edited_requirement_id), "updated_at": edited_updated_at}
            ]:
                raise AssertionError("AI-05 did not pin the edited Requirement revision")
            if clarification_resolution and any(
                fragment in json.dumps(scope_job_payload, ensure_ascii=False)
                for fragment in SENSITIVE_SYNTHETIC_TEXT[-4:]
            ):
                raise AssertionError("Clarification text leaked into AI-05 Job input")
        await run_worker(
            "scope",
            context=context,
            project_id=project_id,
            job_id=scope.job_id,
            event_id=scope.outbox_event_id,
            context_version=version,
        )
        if requirement_edit or clarification_resolution:
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
            if clarification_resolution and any(
                fragment in json.dumps(draft_content, ensure_ascii=False)
                for fragment in SENSITIVE_SYNTHETIC_TEXT[-4:]
            ):
                raise AssertionError("Clarification text leaked into the Scope Draft")
        if requirement_edit:
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
                            "(SELECT count(*) FROM gaps WHERE account_id=:account AND project_id=:project "
                            "AND context_version=:version AND status='resolved' "
                            "AND resolved_at IS NOT NULL) AS resolved, "
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
        expected_dismissed = 0 if clarification_resolution else len(gaps)
        expected_resolved = len(gaps) if clarification_resolution else 0
        if (
            state["requirements"] < 1
            or state["dismissed"] != expected_dismissed
            or state["resolved"] != expected_resolved
            or state["drafts"] != 1
            or state["job_status"] != "succeeded"
        ):
            raise AssertionError("Controlled Context-to-Scope state assertions failed")
        if any(fragment in stream.getvalue() for fragment in SENSITIVE_SYNTHETIC_TEXT):
            raise AssertionError("Synthetic fixture content leaked into API logs")
        print(
            "CONTROLLED_0082_E2E=PASS"
            if clarification_resolution
            else "CONTROLLED_0079_E2E=PASS"
            if provider_timeout_retry
            else "CONTROLLED_0078_E2E=PASS"
            if requirement_edit
            else "CONTROLLED_0077_E2E=PASS"
        )
    finally:
        trace_scope.__exit__(None, None, None)
        await runtime.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirement-edit", action="store_true")
    parser.add_argument("--provider-timeout-retry", action="store_true")
    parser.add_argument("--clarification-resolution", action="store_true")
    arguments = parser.parse_args()
    try:
        os.environ["DATABASE_URL"] = database_url()
        command.upgrade(Config(str(API / "alembic.ini")), "head")
        asyncio.run(
            main_async(
                requirement_edit=arguments.requirement_edit,
                provider_timeout_retry=arguments.provider_timeout_retry,
                clarification_resolution=arguments.clarification_resolution,
            )
        )
    except Exception as error:  # noqa: BLE001 - diagnostic boundary redacts data
        print(f"SAFE_API_STAGE={SAFE_STAGE}", file=sys.stderr)
        print(f"SAFE_API_ERROR_CLASS={type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
