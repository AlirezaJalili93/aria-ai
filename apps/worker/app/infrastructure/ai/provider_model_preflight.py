from __future__ import annotations

from typing import Protocol

from app.application.provider_quality_evaluation import EvaluationContractError
from app.infrastructure.ai.gemini_generate_content import (
    GEMINI_EVALUATION_MODEL,
    GEMINI_PROVIDER,
)
from app.infrastructure.ai.openai_responses import (
    OPENAI_EVALUATION_MODEL,
    OPENAI_PROVIDER,
)


class _OpenAIModels(Protocol):
    async def retrieve(self, model: str) -> object: ...


class _OpenAIModelClient(Protocol):
    models: _OpenAIModels


class _GeminiModels(Protocol):
    async def get(self, *, model: str) -> object: ...


class _GeminiModelClient(Protocol):
    models: _GeminiModels


class ApprovedCandidateModelPreflight:
    """Authenticate and verify the two ADR-055 model identities without generation."""

    def __init__(
        self,
        *,
        openai_client: _OpenAIModelClient,
        gemini_client: _GeminiModelClient,
    ) -> None:
        self._openai_client = openai_client
        self._gemini_client = gemini_client

    async def verify(self, *, provider: str, model: str) -> None:
        try:
            if (provider, model) == (OPENAI_PROVIDER, OPENAI_EVALUATION_MODEL):
                result = await self._openai_client.models.retrieve(model)
                if getattr(result, "id", None) != model:
                    raise EvaluationContractError("provider_model_identity_mismatch")
                return
            if (provider, model) == (GEMINI_PROVIDER, GEMINI_EVALUATION_MODEL):
                result = await self._gemini_client.models.get(model=model)
                returned_name = getattr(result, "name", None)
                if returned_name not in {model, f"models/{model}"}:
                    raise EvaluationContractError("provider_model_identity_mismatch")
                return
        except EvaluationContractError:
            raise
        except Exception as error:
            raise EvaluationContractError("provider_model_preflight_failed") from error
        raise EvaluationContractError("evaluation_candidate_not_approved")
