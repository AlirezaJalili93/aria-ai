from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).parents[2]
WORKER_ROOT = REPOSITORY_ROOT / "apps" / "worker"
for source_root in (
    WORKER_ROOT,
    REPOSITORY_ROOT / "packages" / "backend-application" / "src",
    REPOSITORY_ROOT / "packages" / "observability" / "src",
):
    sys.path.insert(0, str(source_root))

from app.application.context_structuring_consumer import (
    ContextStructuringConsumer,
    ContextStructuringJobInput,
    ContextStructuringJobMessage,
)
from app.application.outbox_delivery import DurableOutboxRelay
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
from app.infrastructure.queue.outbox_publisher import CeleryOutboxPublisher
from aria_backend_application.context_structuring import (
    ContextRepairPolicy,
    ContextStructuringCommand,
    ContextStructuringUseCase,
)
from aria_observability import create_event_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

SYNTHETIC_MARKER = "SYNTHETIC_0072_FIXTURE_ONLY"
DEDICATED_DATABASE_PATTERN = re.compile(r"aria_0072_test(?:_[A-Za-z0-9]+)*")


def _assert_dedicated_test_database(database_url: str) -> None:
    database_name = urlsplit(database_url).path.removeprefix("/")
    if DEDICATED_DATABASE_PATTERN.fullmatch(database_name) is None:
        raise RuntimeError(
            "Controlled 0072 E2E requires a dedicated aria_0072_test... database"
        )


class _UsageLedger:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def append(self, record: object) -> None:
        self.records.append(record)


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


@dataclass
class _CapturedDelivery:
    task_name: str | None = None
    payload: object | None = None
    queue: str | None = None
    retry: bool | None = None

    def send_task(
        self,
        task_name: str,
        *,
        args: list[object],
        queue: str,
        retry: bool,
    ) -> None:
        self.task_name = task_name
        self.payload = args[0]
        self.queue = queue
        self.retry = retry


def _database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError("TEST_DATABASE_URL is required")
    _assert_dedicated_test_database(value)
    if value.startswith("postgresql+asyncpg://"):
        result = value
    elif value.startswith("postgres://"):
        result = value.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        result = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", result)


async def _run(args: argparse.Namespace) -> None:
    engine: AsyncEngine = create_async_engine(_database_url(), poolclass=NullPool)
    stream = StringIO()
    event_logger = create_event_logger(
        service="aria-worker",
        environment="test",
        app_version="0.1.0",
        release_commit_sha=None,
        level="INFO",
        stream=stream,
    )
    delivery = _CapturedDelivery()
    relay = DurableOutboxRelay(
        repository=PostgresOutboxDeliveryRepository(engine),
        publisher=CeleryOutboxPublisher(delivery, queue_name="controlled-synthetic"),  # type: ignore[arg-type]
        event_logger=event_logger,
    )
    try:
        relay_result = await relay.run_once()
        if relay_result.published != 1:
            raise AssertionError("Controlled Relay did not publish exactly one event")
        if delivery.task_name != "aria.context.structure.v1" or delivery.retry is not False:
            raise AssertionError("Controlled Celery delivery contract changed")
        message = ContextStructuringJobMessage.from_payload(delivery.payload)
        if message.job_id != UUID(args.job_id):
            raise AssertionError("Relay changed the Job identity")
        if message.outbox_event_id != UUID(args.outbox_event_id):
            raise AssertionError("Relay changed the Outbox event identity")

        ledger = _UsageLedger()
        use_case = ContextStructuringUseCase(
            snapshot_reader=PostgresContextStructuringSnapshotReader(engine),
            ai_execution=SyntheticContextStructuringAI(),
            usage_ledger=ledger,  # type: ignore[arg-type]
            unsupported_claim_validator=_UnsupportedClaimValidator(),  # type: ignore[arg-type]
            unit_of_work_factory=PostgresContextStructuringUnitOfWorkFactory(engine),
            event_logger=event_logger,
        )
        consumer = ContextStructuringConsumer(
            guard=PostgresJobExecutionGuard(engine),
            store=SqlAlchemyContextStructuringJobStore(engine),
            command_factory=_CommandFactory(),
            use_case=use_case,
            event_logger=event_logger,
        )
        result = await consumer.execute(message)
        if result.status != "succeeded" or len(ledger.records) != 1:
            raise AssertionError("Controlled AI-01 execution did not succeed exactly once")
        async with engine.connect() as connection:
            state = (
                await connection.execute(
                    text(
                        "SELECT j.status, p.current_context_version, "
                        "(SELECT count(*) FROM context_items WHERE project_id=p.id) AS items "
                        "FROM jobs j JOIN projects p ON p.id=j.project_id "
                        "WHERE j.id=:job_id AND j.account_id=:account_id "
                        "AND p.id=:project_id"
                    ),
                    {
                        "job_id": UUID(args.job_id),
                        "account_id": UUID(args.account_id),
                        "project_id": UUID(args.project_id),
                    },
                )
            ).mappings().one()
        if state != {"status": "succeeded", "current_context_version": 1, "items": 1}:
            raise AssertionError(f"Atomic final state is invalid: {state!r}")
        if SYNTHETIC_MARKER in stream.getvalue():
            raise AssertionError("Synthetic fixture content leaked to logs")
        print("CONTROLLED_SYNTHETIC_E2E=PASS")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--outbox-event-id", required=True)
    args = parser.parse_args()
    if UUID(args.outbox_event_id) == UUID(int=0):
        raise AssertionError("Outbox identity is invalid")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
