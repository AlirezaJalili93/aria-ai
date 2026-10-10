from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.application.provider_quality_evaluation import EvaluationContractError
from app.infrastructure.ai.provider_model_preflight import ApprovedCandidateModelPreflight


class OpenAIModels:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def retrieve(self, model: str) -> object:
        self.calls.append(model)
        return SimpleNamespace(id=model)


class GeminiModels:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, *, model: str) -> object:
        self.calls.append(model)
        return SimpleNamespace(name=f"models/{model}")


class FailingModels:
    async def retrieve(self, model: str) -> object:
        raise RuntimeError("credential-or-model-detail-must-not-escape")

    async def get(self, *, model: str) -> object:
        raise RuntimeError("credential-or-model-detail-must-not-escape")


def test_preflight_uses_non_generation_model_retrieval_for_both_candidates() -> None:
    openai_models = OpenAIModels()
    gemini_models = GeminiModels()
    preflight = ApprovedCandidateModelPreflight(
        openai_client=SimpleNamespace(models=openai_models),
        gemini_client=SimpleNamespace(models=gemini_models),
    )

    asyncio.run(preflight.verify(provider="openai", model="gpt-5.6-terra"))
    asyncio.run(preflight.verify(provider="google", model="gemini-3.8-flash"))

    assert openai_models.calls == ["gpt-5.6-terra"]
    assert gemini_models.calls == ["gemini-3.8-flash"]


def test_preflight_rejects_unapproved_candidate_without_remote_call() -> None:
    openai_models = OpenAIModels()
    gemini_models = GeminiModels()
    preflight = ApprovedCandidateModelPreflight(
        openai_client=SimpleNamespace(models=openai_models),
        gemini_client=SimpleNamespace(models=gemini_models),
    )

    with pytest.raises(EvaluationContractError, match="evaluation_candidate_not_approved"):
        asyncio.run(preflight.verify(provider="openai", model="different-model"))

    assert openai_models.calls == []
    assert gemini_models.calls == []


@pytest.mark.parametrize(
    ("provider", "model", "error_code"),
    (
        ("openai", "gpt-5.6-terra", "openai_model_preflight_failed"),
        ("google", "gemini-3.8-flash", "gemini_model_preflight_failed"),
    ),
)
def test_preflight_reports_only_bounded_provider_specific_failure_codes(
    provider: str,
    model: str,
    error_code: str,
) -> None:
    failing_models = FailingModels()
    preflight = ApprovedCandidateModelPreflight(
        openai_client=SimpleNamespace(models=failing_models),
        gemini_client=SimpleNamespace(models=failing_models),
    )

    with pytest.raises(EvaluationContractError) as captured:
        asyncio.run(preflight.verify(provider=provider, model=model))

    assert captured.value.code == error_code
    assert "credential-or-model-detail" not in captured.value.code
