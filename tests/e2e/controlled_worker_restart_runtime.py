"""Controlled 0080 Worker restart and broker-redelivery runtime gate."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from time import monotonic
from typing import NoReturn
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
    ContextStructuringJobInput,
    ContextStructuringJobMessage,
)
from app.application.outbox_delivery import DurableOutboxRelay
from app.core.config import QueueRuntimeConfiguration
from app.infrastructure.ai.synthetic_context_structuring import (
    SyntheticContextStructuringAI,
)
from app.infrastructure.db.context_structuring_runtime import (
    PostgresContextStructuringSnapshotReader,
    PostgresContextStructuringUnitOfWorkFactory,
    SqlAlchemyContextStructuringJobStore,
)
from app.infrastructure.db.outbox_delivery import PostgresOutboxDeliveryRepository
from app.infrastructure.db.txt_parser_runtime import PostgresJobExecutionGuard
from app.infrastructure.db.usage_ledger import SqlAlchemyUsageLedger
from app.infrastructure.queue.celery_runtime import create_celery_app
from app.infrastructure.queue.context_structuring_task import (
    CONTEXT_STRUCTURING_TASK_NAME,
    register_context_structuring_task,
)
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher
from aria_backend_application.ai_execution import StructuredAIResponse
from aria_backend_application.context_structuring import (
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringUseCase,
)
from aria_observability import create_event_logger
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

DEDICATED_DATABASE_PATTERN = re.compile(r"aria_00(?:72|77)_test(?:_[A-Za-z0-9]+)*")
QUEUE_PATTERN = re.compile(r"aria_0080_[0-9a-f]{32}")
SYNTHETIC_MARKER = "SYNTHETIC_0072_FIXTURE_ONLY"
VISIBILITY_TIMEOUT_SECONDS = 5


def _database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL", "")
    if DEDICATED_DATABASE_PATTERN.fullmatch(urlsplit(value).path.removeprefix("/")) is None:
        raise RuntimeError("0080 requires an approved dedicated synthetic E2E database")
    value = value.replace("postgres://", "postgresql+asyncpg://", 1)
    value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)


def _redis_url() -> str:
    value = os.environ.get("TEST_REDIS_URL", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "redis"
        or parsed.hostname not in {"127.0.0.1", "localhost"}
        or parsed.port != 6379
        or parsed.path != "/15"
    ):
        raise RuntimeError("0080 requires isolated local Redis database 15")
    return value


def _queue_name(value: str) -> str:
    if QUEUE_PATTERN.fullmatch(value) is None:
        raise ValueError("0080 Queue identity is invalid")
    return value


def _control_file(value: str) -> Path:
    path = Path(value).resolve()
    control_root = (ROOT / ".data").resolve()
    if not path.is_relative_to(control_root) or not path.parent.name.startswith("aria-0080-"):
        raise ValueError("0080 control file must be inside the repository .data boundary")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _engine(*, worker_role: bool) -> AsyncEngine:
    connect_args = {"server_settings": {"role": "aria_worker"}} if worker_role else {}
    return create_async_engine(
        _database_url(),
        poolclass=NullPool,
        connect_args=connect_args,
    )


def _queue_configuration(queue_name: str) -> QueueRuntimeConfiguration:
    return QueueRuntimeConfiguration(
        broker_url=SecretStr(_redis_url()),
        queue_name=_queue_name(queue_name),
        visibility_timeout_seconds=VISIBILITY_TIMEOUT_SECONDS,
        concurrency=1,
    )


class _UnsupportedClaimValidator:
    async def validate(self, *, batch: object, snapshot: object) -> None:
        del batch, snapshot


class _CommandFactory:
    def build(self, job: ContextStructuringJobInput) -> ContextStructuringCommand:
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


class _PreProviderFailpointStore:
    def __init__(
        self,
        inner: SqlAlchemyContextStructuringJobStore,
        *,
        checkpoint_file: Path | None,
        outbox_event_id: UUID,
    ) -> None:
        self._inner = inner
        self._checkpoint_file = checkpoint_file
        self._outbox_event_id = outbox_event_id

    async def prepare(
        self, message: ContextStructuringJobMessage
    ) -> ContextStructuringJobInput:
        job = await self._inner.prepare(message)
        if self._checkpoint_file is None:
            return job
        _write_json_atomic(
            self._checkpoint_file,
            {
                "checkpoint": "after_running_before_provider",
                "job_id": str(job.job_id),
                "outbox_event_id": str(self._outbox_event_id),
            },
        )
        await _block_until_process_death()

    async def finalize_failure(
        self,
        job: ContextStructuringJobInput,
        *,
        error_code: str,
    ) -> None:
        await self._inner.finalize_failure(job, error_code=error_code)


class _InvocationTrackingSyntheticAI:
    def __init__(self, invocation_file: Path) -> None:
        self._invocation_file = invocation_file
        self._inner = SyntheticContextStructuringAI()

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
        job_id = UUID(str(metadata["job_id"]))
        with self._invocation_file.open("a", encoding="ascii", newline="\n") as stream:
            stream.write(f"{job_id}\n")
            stream.flush()
        return await self._inner.execute_structured(
            task_type=task_type,
            workflow_version=workflow_version,
            prompt_version=prompt_version,
            output_schema=output_schema,
            input_context=input_context,
            routing_policy=routing_policy,
            cost_budget=cost_budget,
            timeout_policy=timeout_policy,
            metadata=metadata,
        )


async def _block_until_process_death() -> NoReturn:
    await asyncio.Future()
    raise AssertionError("0080 failpoint unexpectedly resumed")


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, separators=(",", ":"), sort_keys=True),
        encoding="ascii",
    )
    temporary.replace(path)


def _logger():
    return create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
    )


async def _relay(args: argparse.Namespace) -> None:
    engine = _engine(worker_role=True)
    celery_app = create_celery_app(_queue_configuration(args.queue_name))
    try:
        result = await DurableOutboxRelay(
            repository=PostgresOutboxDeliveryRepository(engine),
            publisher=CeleryOutboxPublisher(celery_app, queue_name=args.queue_name),
            event_logger=_logger(),
        ).run_once()
        if result.published != 1:
            raise AssertionError("0080 Relay did not publish exactly one event")
        async with engine.connect() as connection:
            state = (
                await connection.execute(
                    text(
                        "SELECT status, payload->>'jobId' AS job_id FROM outbox_events "
                        "WHERE id=:event_id"
                    ),
                    {"event_id": UUID(args.event_id)},
                )
            ).mappings().one()
        if state["status"] != "published" or state["job_id"] != args.job_id:
            raise AssertionError("0080 Outbox publication identity changed")
        print("CONTROLLED_0080_RELAY=PASS")
    finally:
        await engine.dispose()


def _worker(args: argparse.Namespace) -> None:
    engine = _engine(worker_role=True)
    checkpoint_file = (
        _control_file(args.checkpoint_file) if args.checkpoint_file is not None else None
    )
    invocation_file = _control_file(args.invocation_file)
    logger = _logger()
    job_store = _PreProviderFailpointStore(
        SqlAlchemyContextStructuringJobStore(engine),
        checkpoint_file=checkpoint_file,
        outbox_event_id=UUID(args.event_id),
    )
    consumer = ContextStructuringConsumer(
        guard=PostgresJobExecutionGuard(engine),
        store=job_store,
        command_factory=_CommandFactory(),
        use_case=ContextStructuringUseCase(
            snapshot_reader=PostgresContextStructuringSnapshotReader(engine),
            ai_execution=_InvocationTrackingSyntheticAI(invocation_file),
            usage_ledger=SqlAlchemyUsageLedger(engine),
            unsupported_claim_validator=_UnsupportedClaimValidator(),  # type: ignore[arg-type]
            unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(engine),
            event_logger=logger,
        ),
        event_logger=logger,
    )
    celery_app = create_celery_app(_queue_configuration(args.queue_name))
    register_context_structuring_task(celery_app, consumer)
    if celery_app.tasks[CONTEXT_STRUCTURING_TASK_NAME].autoretry_for != ():
        raise AssertionError("Celery automatic retry must remain disabled")
    celery_app.worker_main(
        [
            "worker",
            "--loglevel",
            "WARNING",
            "--queues",
            args.queue_name,
            "--pool",
            "solo",
            "--concurrency",
            "1",
            "--hostname",
            f"aria-0080-{args.worker_number}@%h",
        ]
    )


async def _probe_lock(args: argparse.Namespace) -> None:
    engine = _engine(worker_role=True)
    guard = PostgresJobExecutionGuard(engine)
    try:
        state = await guard.acquire(UUID(args.job_id))
        if state == "acquired":
            await guard.release(UUID(args.job_id))
            raise AssertionError("Worker #1 advisory lock was not held")
        if state != "already_in_progress":
            raise AssertionError("Unexpected pre-crash Job guard state")
        print("CONTROLLED_0080_CONCURRENT_GUARD=PASS")
    finally:
        await engine.dispose()


async def _state(engine: AsyncEngine, job_id: UUID, event_id: UUID) -> Mapping[str, object]:
    async with engine.connect() as connection:
        return (
            await connection.execute(
                text(
                    "SELECT j.status, j.attempt_count, j.project_id, "
                    "p.current_context_version, "
                    "(SELECT count(*) FROM jobs WHERE project_id=j.project_id "
                    "AND job_type='context_structuring') AS jobs, "
                    "(SELECT count(*) FROM outbox_events WHERE id=:event_id "
                    "AND payload->>'jobId'=:job_id_text) AS events, "
                    "(SELECT status FROM outbox_events WHERE id=:event_id) AS event_status, "
                    "(SELECT count(*) FROM usage_records WHERE job_id=j.id) AS usage_records, "
                    "(SELECT count(DISTINCT provider_attempt_id) FROM usage_records "
                    "WHERE job_id=j.id) AS provider_attempts, "
                    "(SELECT count(*) FROM context_items WHERE project_id=j.project_id) AS items, "
                    "(SELECT count(DISTINCT context_version) FROM context_items "
                    "WHERE project_id=j.project_id) AS context_versions "
                    "FROM jobs j JOIN projects p ON p.id=j.project_id WHERE j.id=:job_id"
                ),
                {
                    "job_id": job_id,
                    "job_id_text": str(job_id),
                    "event_id": event_id,
                },
            )
        ).mappings().one()


def _invocation_count(path: Path, job_id: UUID) -> int:
    if not path.exists():
        return 0
    values = [line for line in path.read_text(encoding="ascii").splitlines() if line]
    if any(value != str(job_id) for value in values):
        raise AssertionError("Provider invocation marker changed Job identity")
    return len(values)


async def _assert_before(args: argparse.Namespace) -> None:
    engine = _engine(worker_role=False)
    job_id = UUID(args.job_id)
    event_id = UUID(args.event_id)
    checkpoint_file = _control_file(args.checkpoint_file)
    invocation_file = _control_file(args.invocation_file)
    try:
        checkpoint = json.loads(checkpoint_file.read_text(encoding="ascii"))
        if checkpoint != {
            "checkpoint": "after_running_before_provider",
            "job_id": str(job_id),
            "outbox_event_id": str(event_id),
        }:
            raise AssertionError("0080 deterministic checkpoint identity changed")
        state = await _state(engine, job_id, event_id)
        expected = {
            "status": "running",
            "attempt_count": 1,
            "current_context_version": 0,
            "jobs": 1,
            "events": 1,
            "event_status": "published",
            "usage_records": 0,
            "provider_attempts": 0,
            "items": 0,
            "context_versions": 0,
        }
        if any(state[key] != value for key, value in expected.items()):
            raise AssertionError("0080 pre-crash durable state is invalid")
        if _invocation_count(invocation_file, job_id) != 0:
            raise AssertionError("Provider was invoked before the crash checkpoint")
        print("CONTROLLED_0080_PRE_CRASH=PASS")
    finally:
        await engine.dispose()


async def _wait_after(args: argparse.Namespace) -> None:
    engine = _engine(worker_role=False)
    job_id = UUID(args.job_id)
    event_id = UUID(args.event_id)
    invocation_file = _control_file(args.invocation_file)
    deadline = monotonic() + args.timeout_seconds
    try:
        state: Mapping[str, object] | None = None
        while monotonic() < deadline:
            state = await _state(engine, job_id, event_id)
            if state["status"] == "succeeded":
                break
            await asyncio.sleep(0.25)
        if state is None or state["status"] != "succeeded":
            raise AssertionError("0080 recovery did not complete the original Job")
        expected = {
            "attempt_count": 1,
            "current_context_version": 1,
            "jobs": 1,
            "events": 1,
            "event_status": "published",
            "usage_records": 1,
            "provider_attempts": 1,
            "items": 1,
            "context_versions": 1,
        }
        if any(state[key] != value for key, value in expected.items()):
            raise AssertionError("0080 recovered durable state or idempotency is invalid")
        if _invocation_count(invocation_file, job_id) != 1:
            raise AssertionError("Recovery must invoke the Fake Provider exactly once")
        print("CONTROLLED_0080_RECOVERY=PASS")
    finally:
        await engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    relay = commands.add_parser("relay")
    relay.add_argument("--queue-name", required=True, type=_queue_name)
    relay.add_argument("--job-id", required=True)
    relay.add_argument("--event-id", required=True)

    worker = commands.add_parser("worker")
    worker.add_argument("--queue-name", required=True, type=_queue_name)
    worker.add_argument("--event-id", required=True)
    worker.add_argument("--invocation-file", required=True)
    worker.add_argument("--checkpoint-file")
    worker.add_argument("--worker-number", choices=("1", "2"), required=True)

    probe = commands.add_parser("probe-lock")
    probe.add_argument("--job-id", required=True)

    before = commands.add_parser("assert-before")
    before.add_argument("--job-id", required=True)
    before.add_argument("--event-id", required=True)
    before.add_argument("--checkpoint-file", required=True)
    before.add_argument("--invocation-file", required=True)

    after = commands.add_parser("wait-after")
    after.add_argument("--job-id", required=True)
    after.add_argument("--event-id", required=True)
    after.add_argument("--invocation-file", required=True)
    after.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if hasattr(args, "job_id"):
        UUID(args.job_id)
    if hasattr(args, "event_id"):
        UUID(args.event_id)
    if args.command == "worker":
        _worker(args)
        return
    handler = {
        "relay": _relay,
        "probe-lock": _probe_lock,
        "assert-before": _assert_before,
        "wait-after": _wait_after,
    }[args.command]
    asyncio.run(handler(args))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - bounded diagnostic boundary
        print(f"SAFE_0080_ERROR_CLASS={type(error).__name__}", file=sys.stderr)
        if SYNTHETIC_MARKER in str(error):
            print("SAFE_0080_LEAKAGE_GUARD=FAIL", file=sys.stderr)
        raise SystemExit(1) from None
