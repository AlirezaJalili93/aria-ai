"""Execute one 0077 synthetic Job through the accepted Relay/Worker boundaries."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit
from uuid import UUID

ROOT = Path(__file__).parents[2]
WORKER = ROOT / "apps" / "worker"
for source in (
    WORKER,
    ROOT / "packages" / "backend-application" / "src",
    ROOT / "packages" / "observability" / "src",
):
    sys.path.insert(0, str(source))

from app.application.context_structuring_consumer import (
    ContextStructuringConsumer,
    ContextStructuringJobMessage,
)
from app.application.gap_detection_consumer import (
    GapDetectionConsumer,
    GapDetectionJobMessage,
)
from app.application.gap_detection_runtime import SyntheticGapDetectionCommandFactory
from app.application.outbox_delivery import DurableOutboxRelay
from app.application.provider_adapter import ProviderAdapterError, ProviderResult
from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import (
    ProviderExecutionMetadata,
    ProviderFailureCoordinator,
)
from app.application.requirement_generation_consumer import (
    RequirementGenerationConsumer,
    RequirementGenerationJobMessage,
)
from app.application.requirement_generation_runtime import (
    SyntheticRequirementGenerationCommandFactory,
)
from app.application.scope_generation_consumer import (
    ExplicitSyntheticScopeProjects,
    ScopeGenerationConsumer,
    ScopeGenerationJobMessage,
)
from app.application.scope_generation_runtime import (
    SyntheticScopeGenerationCommandFactory,
)
from app.infrastructure.ai.synthetic_context_structuring import (
    SyntheticContextStructuringAI,
)
from app.infrastructure.ai.synthetic_gap_detection import SyntheticGapDetectionAI
from app.infrastructure.ai.synthetic_requirement_generation import (
    SyntheticRequirementGenerationAI,
)
from app.infrastructure.ai.synthetic_scope_generation import SyntheticScopeGenerationAI
from app.infrastructure.db.context_structuring_runtime import (
    PostgresContextStructuringSnapshotReader,
    PostgresContextStructuringUnitOfWorkFactory,
    SqlAlchemyContextStructuringJobStore,
)
from app.infrastructure.db.gap_detection_runtime import (
    PostgresGapDetectionSnapshotReader,
    PostgresGapDetectionUnitOfWorkFactory,
    SqlAlchemyGapDetectionJobStore,
)
from app.infrastructure.db.outbox_delivery import PostgresOutboxDeliveryRepository
from app.infrastructure.db.provider_pricing import PostgresProviderPriceCatalog
from app.infrastructure.db.requirement_generation_runtime import (
    PostgresRequirementContextSnapshotReader,
    PostgresRequirementGenerationUnitOfWorkFactory,
    SqlAlchemyRequirementGenerationJobStore,
)
from app.infrastructure.db.scope_generation_runtime import (
    PostgresScopeGenerationFinalizer,
    PostgresScopeGenerationSnapshotReader,
    SqlAlchemyScopeGenerationJobStore,
)
from app.infrastructure.db.txt_parser_runtime import PostgresJobExecutionGuard
from app.infrastructure.db.usage_ledger import SqlAlchemyUsageLedger
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.context_structuring import (
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringUseCase,
)
from aria_backend_application.gap_detection import (
    DetectGapsUseCase,
    VersionedCriticalGapRuleEvaluator,
)
from aria_backend_application.requirements_generation import GenerateRequirementsUseCase
from aria_backend_application.scope_content import validate_scope_content
from aria_backend_application.scope_generation import ScopeGenerationUseCase
from aria_observability import create_event_logger
from celery import Celery
from kombu import Connection, Queue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

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
):
    raise RuntimeError("0078 fixture identity changed without a versioned contract")
MARKER = FIXTURE["source_text"]
SENSITIVE_SYNTHETIC_TEXT = (
    MARKER,
    "مرجع ساختاریافتهٔ مصنوعی",
    "نیازمندی مصنوعی کنترل‌شده",
    "این خروجی فقط برای آزمون",
    EDIT_FIXTURE["edited_requirement_title"],
)
DEDICATED_NAME = re.compile(r"aria_0077_test(?:_[A-Za-z0-9]+)*")
TASKS = {
    "context": "aria.context.structure.v1",
    "requirement": "aria.requirements.generate.v1",
    "gap": "aria.gaps.detect.v1",
    "scope": "aria.scope.generate.v1",
}


def database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL", "")
    if (
        not value
        or DEDICATED_NAME.fullmatch(urlsplit(value).path.removeprefix("/")) is None
    ):
        raise RuntimeError("0077 requires a dedicated aria_0077_test... database")
    value = value.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def redis_url() -> str:
    value = os.environ.get("TEST_REDIS_URL", "")
    parts = urlsplit(value)
    if (
        parts.scheme != "redis"
        or parts.hostname not in {"127.0.0.1", "localhost"}
        or parts.port != 6379
        or parts.path != "/15"
    ):
        raise RuntimeError("0077 requires local Redis database 15")
    return value


class UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


class NoWallClockSleep:
    def __init__(self) -> None:
        self.calls = 0

    async def sleep(self, delay_seconds: float) -> None:
        if delay_seconds != 0:
            raise AssertionError("Synthetic retry must not sleep in real time")
        self.calls += 1


class ZeroJitter:
    def random(self) -> float:
        return 0.0


class TimeoutThenSyntheticContextAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self._synthetic = SyntheticContextStructuringAI()

    async def execute(self, request: Mapping[str, object]) -> ProviderResult:
        self.calls += 1
        if self.calls == 1:
            raise ProviderAdapterError("timeout", retryable=True)
        if self.calls != 2:
            raise AssertionError("Provider invocation budget exceeded")
        response = await self._synthetic.execute_structured(
            task_type=cast(str, request["task_type"]),
            workflow_version=cast(str, request["workflow_version"]),
            prompt_version=cast(str, request["prompt_version"]),
            output_schema=cast(Mapping[str, object], request["output_schema"]),
            input_context=cast(Mapping[str, object], request["input_context"]),
            routing_policy=cast(Mapping[str, object], request["routing_policy"]),
            cost_budget=cast(Mapping[str, object], request["cost_budget"]),
            timeout_policy=cast(Mapping[str, object], request["timeout_policy"]),
            metadata=cast(Mapping[str, object], request["metadata"]),
        )
        return ProviderResult(
            data=response.data,
            provider=response.provider,
            model=response.model,
            provider_request_id=response.provider_request_id,
            input_tokens=response.input_tokens,
            cached_input_tokens=response.cached_input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
            status=response.status,
        )


class CoordinatorManagedSyntheticContextAI:
    usage_owner = "coordinator"

    def __init__(self, *, engine: object, logger: object) -> None:
        self.adapter = TimeoutThenSyntheticContextAdapter()
        self.sleeper = NoWallClockSleep()
        self._coordinator = ProviderFailureCoordinator(
            catalog=PostgresProviderPriceCatalog(engine),  # type: ignore[arg-type]
            usage_ledger=SqlAlchemyUsageLedger(engine),  # type: ignore[arg-type]
            sleeper=self.sleeper,
            random_source=ZeroJitter(),
            utc_clock=lambda: datetime.now(UTC),
            event_logger=logger,  # type: ignore[arg-type]
        )

    async def execute_structured(
        self,
        task_type: str,
        workflow_version: str,
        prompt_version: str,
        output_schema: Mapping[str, object],
        input_context: Mapping[str, object],
        routing_policy: Mapping[str, object],
        cost_budget: Mapping[str, object],
        timeout_policy: Mapping[str, object],
        metadata: Mapping[str, object],
    ) -> StructuredAIResponse:
        request = {
            "task_type": task_type,
            "workflow_version": workflow_version,
            "prompt_version": prompt_version,
            "output_schema": output_schema,
            "input_context": input_context,
            "routing_policy": routing_policy,
            "cost_budget": cost_budget,
            "timeout_policy": timeout_policy,
            "metadata": metadata,
        }
        execution = await self._coordinator.execute(
            primary=ProviderCandidate(
                "synthetic", "context-structuring-fake-v1", self.adapter
            ),
            request=request,
            metadata=ProviderExecutionMetadata(
                account_id=UUID(str(metadata["account_id"])),
                project_id=UUID(str(metadata["project_id"])),
                job_id=UUID(str(metadata["job_id"])),
                task_type=task_type,
                workflow_version=workflow_version,
                prompt_version=prompt_version,
                repair_no=0,
                correlation_id=UUID(str(metadata["correlation_id"])),
            ),
        )
        result = execution.result
        return StructuredAIResponse(
            data=result.data,
            provider_attempt_id=execution.provider_attempt_id,
            provider=result.provider,
            model=result.model,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens,
            cached_input_tokens=result.cached_input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            retry_no=execution.retry_no,
            workflow_version=workflow_version,
            prompt_version=prompt_version,
            estimated_cost=0,
            status=result.status,
        )


class SupportValidator:
    async def validate(self, *, batch: object, snapshot: object) -> None:
        del batch, snapshot


class ContextCommandFactory:
    def build(self, job: object) -> ContextStructuringCommand:
        return ContextStructuringCommand(
            account_id=job.account_id,
            project_id=job.project_id,
            job_id=job.job_id,
            correlation_id=job.correlation_id,
            task_type="context_structuring",
            workflow_version="controlled-synthetic-ai-01-v1",
            prompt_version="controlled-synthetic-prompt-v1",
            output_schema_version="context-structuring-output-v1",
            repair_prompt_version="controlled-synthetic-repair-v1",
            repair_policy=ContextRepairPolicy(
                policy_version="controlled-synthetic-no-repair-v1",
                max_repairs=0,
            ),
            pricing_version="synthetic-zero-v1",
            output_schema={"synthetic": True},
            routing_policy={"tier": "standard", "synthetic": True},
            cost_budget={"paid_calls_allowed": False},
            timeout_policy={"synthetic": True},
        )


class ScopeValidator:
    def validate(self, content: object) -> dict[str, object]:
        return validate_scope_content(content)


async def execute(args: argparse.Namespace) -> None:
    if args.provider_timeout_retry and args.stage != "context":
        raise ValueError("Provider timeout scenario is AI-01 only")
    broker = redis_url()
    engine = create_async_engine(
        database_url(),
        poolclass=NullPool,
        connect_args={"server_settings": {"role": "aria_worker"}},
    )
    queue_name = f"aria_0077_{args.job_id.hex}"
    celery_app = Celery("aria-0077-controlled", broker=broker)
    logs = StringIO()
    logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=logs,
    )
    try:
        relay = DurableOutboxRelay(
            repository=PostgresOutboxDeliveryRepository(engine),
            publisher=CeleryOutboxPublisher(celery_app, queue_name=queue_name),
            event_logger=logger,
        )
        outcome = await relay.run_once()
        if outcome.published != 1:
            raise AssertionError("Durable Relay did not publish exactly one Job")
        with Connection(broker) as connection:
            queue = connection.SimpleQueue(queue_name)
            try:
                queued = queue.get(block=True, timeout=5)
                task_name = queued.headers.get("task")
                body = queued.payload
                queued.ack()
            finally:
                queue.close()
        if (
            task_name != TASKS[args.stage]
            or not isinstance(body, list)
            or len(body) != 3
        ):
            raise AssertionError("Local Redis/Celery task routing changed")
        task_args = body[0]
        if not isinstance(task_args, list) or len(task_args) != 1:
            raise AssertionError("Celery task arguments changed")
        payload = task_args[0]
        if not isinstance(payload, dict) or set(payload) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise AssertionError("Queue envelope is not identifier-only")
        if (
            UUID(str(payload["job_id"])) != args.job_id
            or UUID(str(payload["outbox_event_id"])) != args.event_id
        ):
            raise AssertionError("Durable message identity changed")

        ledger = UsageLedger()
        guard = PostgresJobExecutionGuard(engine)
        if args.stage == "context":
            coordinator_ai = (
                CoordinatorManagedSyntheticContextAI(engine=engine, logger=logger)
                if args.provider_timeout_retry
                else None
            )
            message = ContextStructuringJobMessage.from_payload(payload)
            consumer = ContextStructuringConsumer(
                guard=guard,
                store=SqlAlchemyContextStructuringJobStore(engine),
                command_factory=ContextCommandFactory(),
                use_case=ContextStructuringUseCase(
                    snapshot_reader=PostgresContextStructuringSnapshotReader(engine),
                    ai_execution=coordinator_ai or SyntheticContextStructuringAI(),
                    usage_ledger=None if coordinator_ai else ledger,  # type: ignore[arg-type]
                    coordinator_managed=coordinator_ai is not None,
                    unsupported_claim_validator=SupportValidator(),  # type: ignore[arg-type]
                    unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(
                        engine
                    ),
                    event_logger=logger,
                ),
                event_logger=logger,
            )
        elif args.stage == "requirement":
            message = RequirementGenerationJobMessage.from_payload(payload)
            consumer = RequirementGenerationConsumer(
                guard=guard,
                store=SqlAlchemyRequirementGenerationJobStore(engine),
                command_factory=SyntheticRequirementGenerationCommandFactory(),
                use_case=GenerateRequirementsUseCase(
                    snapshot_reader=PostgresRequirementContextSnapshotReader(engine),
                    ai_execution=SyntheticRequirementGenerationAI(),
                    usage_ledger=ledger,  # type: ignore[arg-type]
                    support_validator=SupportValidator(),  # type: ignore[arg-type]
                    unit_of_work_factory=PostgresRequirementGenerationUnitOfWorkFactory(
                        engine
                    ),
                    event_logger=logger,
                ),
                event_logger=logger,
            )
        elif args.stage == "gap":
            message = GapDetectionJobMessage.from_payload(payload)
            consumer = GapDetectionConsumer(
                guard=guard,
                store=SqlAlchemyGapDetectionJobStore(engine),
                command_factory=SyntheticGapDetectionCommandFactory(),
                use_case=DetectGapsUseCase(
                    snapshot_reader=PostgresGapDetectionSnapshotReader(engine),
                    ai_execution=SyntheticGapDetectionAI(),
                    usage_ledger=ledger,  # type: ignore[arg-type]
                    critical_rule_evaluator=VersionedCriticalGapRuleEvaluator(),
                    unit_of_work_factory=PostgresGapDetectionUnitOfWorkFactory(engine),
                    event_logger=logger,
                ),
                event_logger=logger,
            )
        else:
            message = ScopeGenerationJobMessage.from_payload(payload)
            consumer = ScopeGenerationConsumer(
                guard=guard,
                store=SqlAlchemyScopeGenerationJobStore(engine),
                command_factory=SyntheticScopeGenerationCommandFactory(),
                use_case=ScopeGenerationUseCase(
                    snapshot_reader=PostgresScopeGenerationSnapshotReader(engine),
                    ai_execution=SyntheticScopeGenerationAI(),
                    usage_ledger=ledger,  # type: ignore[arg-type]
                    content_validator=ScopeValidator(),
                    finalizer=PostgresScopeGenerationFinalizer(engine),
                    event_logger=logger,
                ),
                synthetic_authorizer=ExplicitSyntheticScopeProjects(
                    frozenset({(args.account_id, args.project_id)})
                ),
                event_logger=logger,
            )
        result = await consumer.execute(message)
        duplicate = await consumer.execute(message)
        if result.status != "succeeded" or duplicate.status != "already_completed":
            raise AssertionError("Synthetic Job or duplicate suppression failed")
        if args.provider_timeout_retry:
            assert coordinator_ai is not None
            if (
                coordinator_ai.adapter.calls != 2
                or coordinator_ai.sleeper.calls != 1
                or ledger.records
            ):
                raise AssertionError("Coordinator retry or single Usage owner failed")
        elif len(ledger.records) != 1:
            raise AssertionError("One actual Fake invocation must have one usage record")
        async with engine.connect() as connection:
            state = (
                (
                    await connection.execute(
                        text(
                            "SELECT status, account_id, project_id, payload_ref FROM jobs WHERE id=:id"
                        ),
                        {"id": args.job_id},
                    )
                )
                .mappings()
                .one()
            )
        if (
            state["status"] != "succeeded"
            or state["account_id"] != args.account_id
            or state["project_id"] != args.project_id
        ):
            raise AssertionError("Job finalization or tenant binding failed")
        if (
            args.stage != "context"
            and state["payload_ref"]["context_version"] != args.context_version
        ):
            raise AssertionError("Downstream Job lost exact Context Version N")
        if any(fragment in logs.getvalue() for fragment in SENSITIVE_SYNTHETIC_TEXT):
            raise AssertionError("Synthetic fixture content leaked to Worker logs")
        print("CONTROLLED_0077_STAGE=PASS")
    finally:
        try:
            with Connection(broker) as connection, connection.channel() as channel:
                Queue(queue_name).bind(channel).delete()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=TASKS)
    parser.add_argument("account_id", type=UUID)
    parser.add_argument("project_id", type=UUID)
    parser.add_argument("job_id", type=UUID)
    parser.add_argument("event_id", type=UUID)
    parser.add_argument("--context-version", type=int)
    parser.add_argument("--provider-timeout-retry", action="store_true")
    try:
        asyncio.run(execute(parser.parse_args()))
    except Exception as error:  # noqa: BLE001 - diagnostic boundary must redact all failures
        # Never print exception messages: drivers may embed SQL, credentials or content.
        print(f"SAFE_WORKER_ERROR_CLASS={type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
