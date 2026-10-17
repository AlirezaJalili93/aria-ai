from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from aria_observability import NoOpOperationalMetrics
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.provider_execution import ProviderCandidate
from app.application.provider_failure_policy import (
    EVALUATION_INVOCATION_POLICY,
    ProviderFailureCoordinator,
    RetryRandomSource,
    RetrySleeper,
)
from app.application.provider_quality_evaluation import (
    ControlledProviderQualityEvaluation,
    FailureCoordinatorSingleInvocation,
)
from app.infrastructure.ai.gemini_generate_content import (
    GEMINI_EVALUATION_MODEL,
    GEMINI_PROVIDER,
    GeminiGenerateContentAdapter,
    create_gemini_client,
)
from app.infrastructure.ai.openai_responses import (
    OPENAI_EVALUATION_MODEL,
    OPENAI_PROVIDER,
    OpenAIResponsesAdapter,
    create_openai_client,
)
from app.infrastructure.ai.provider_model_preflight import (
    ApprovedCandidateModelPreflight,
)
from app.infrastructure.ai.provider_quality_prompt_package import (
    ApprovedPromptSchemaPackageV1,
)
from app.infrastructure.db.provider_pricing import PostgresProviderPriceCatalog
from app.infrastructure.db.usage_ledger import SqlAlchemyUsageLedger


class _RetryProhibitedSleeper(RetrySleeper):
    async def sleep(self, delay_seconds: float) -> None:
        raise RuntimeError(f"evaluation_retry_prohibited:{delay_seconds}")


class _UnusedRandomSource(RetryRandomSource):
    def random(self) -> float:
        return 0.0


@dataclass(frozen=True, slots=True)
class ControlledEvaluationComposition:
    """Manual-only 0086 composition. Construction performs no network or Provider call."""

    evaluation: ControlledProviderQualityEvaluation
    request_factory: ApprovedPromptSchemaPackageV1
    candidates: tuple[ProviderCandidate, ...]
    engine: AsyncEngine

    async def dispose(self) -> None:
        await self.engine.dispose()


def compose_controlled_provider_evaluation(
    *,
    database_url: str,
    openai_api_key: str,
    gemini_api_key: str,
) -> ControlledEvaluationComposition:
    """Wire real candidates behind explicit preflight; never starts an Eval Run."""

    if not database_url.strip():
        raise ValueError("evaluation_database_url_required")
    openai_client = create_openai_client(openai_api_key)
    gemini_client = create_gemini_client(gemini_api_key)
    gemini_async = cast(Any, gemini_client.aio)
    engine = create_async_engine(
        normalize_async_database_url(database_url),
        connect_args={"server_settings": {"role": "aria_worker"}},
        poolclass=NullPool,
    )
    catalog = PostgresProviderPriceCatalog(engine)
    ledger = SqlAlchemyUsageLedger(engine, NoOpOperationalMetrics())
    coordinator = ProviderFailureCoordinator(
        catalog=catalog,
        usage_ledger=ledger,
        sleeper=_RetryProhibitedSleeper(),
        random_source=_UnusedRandomSource(),
        utc_clock=lambda: datetime.now(UTC),
        policy=EVALUATION_INVOCATION_POLICY,
    )
    request_factory = ApprovedPromptSchemaPackageV1()
    evaluation = ControlledProviderQualityEvaluation(
        price_catalog=catalog,
        model_preflight=ApprovedCandidateModelPreflight(
            openai_client=cast(Any, openai_client),
            gemini_client=gemini_async,
        ),
        invocation=FailureCoordinatorSingleInvocation(coordinator),
        output_normalizer=request_factory,
    )
    candidates = (
        ProviderCandidate(
            provider=OPENAI_PROVIDER,
            model=OPENAI_EVALUATION_MODEL,
            adapter=OpenAIResponsesAdapter(
                client=cast(Any, openai_client),
                model=OPENAI_EVALUATION_MODEL,
            ),
        ),
        ProviderCandidate(
            provider=GEMINI_PROVIDER,
            model=GEMINI_EVALUATION_MODEL,
            adapter=GeminiGenerateContentAdapter(
                client=gemini_async,
                model=GEMINI_EVALUATION_MODEL,
            ),
        ),
    )
    return ControlledEvaluationComposition(
        evaluation=evaluation,
        request_factory=request_factory,
        candidates=candidates,
        engine=engine,
    )


def normalize_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        value = database_url
    elif database_url.startswith("postgres://"):
        value = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    else:
        value = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return re.sub(r"([?&])sslmode=", r"\1ssl=", value)
