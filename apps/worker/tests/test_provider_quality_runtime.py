from __future__ import annotations

import asyncio

import pytest

from app.application.provider_quality_evaluation import APPROVED_CANDIDATES
from app.runtime.provider_quality_evaluation import (
    compose_controlled_provider_evaluation,
)


def test_real_candidate_composition_has_no_construction_side_effects() -> None:
    composition = compose_controlled_provider_evaluation(
        database_url="postgresql+asyncpg://user:password@127.0.0.1:1/eval",
        openai_api_key="synthetic-openai-key-not-used",
        gemini_api_key="synthetic-gemini-key-not-used",
    )
    try:
        assert {
            (candidate.provider, candidate.model) for candidate in composition.candidates
        } == APPROVED_CANDIDATES
        assert composition.request_factory is not None
        assert composition.evaluation is not None
    finally:
        asyncio.run(composition.dispose())


@pytest.mark.parametrize(
    ("field", "values", "error"),
    (
        ("database_url", ("", "key", "key"), "evaluation_database_url_required"),
        ("openai_api_key", ("postgresql://unused", "", "key"), "openai_api_key_required"),
        ("gemini_api_key", ("postgresql://unused", "key", ""), "gemini_api_key_required"),
    ),
)
def test_composition_fails_closed_when_required_configuration_is_absent(
    field: str,
    values: tuple[str, str, str],
    error: str,
) -> None:
    del field
    with pytest.raises(ValueError, match=error):
        compose_controlled_provider_evaluation(
            database_url=values[0],
            openai_api_key=values[1],
            gemini_api_key=values[2],
        )
