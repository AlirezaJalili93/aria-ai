from __future__ import annotations

import json
from pathlib import Path

from app.application.artifact_generation_runtime import ArtifactGenerationError

_FIXTURES = {
    "landing": "fa_gen_landing_001.json",
    "corporate": "fa_gen_corporate_001.json",
    "portfolio": "fa_gen_portfolio_001.json",
}


class VersionedSyntheticArtifactCandidateSource:
    def __init__(self, *, repository_root: Path) -> None:
        self._fixture_root = (
            repository_root
            / "evals"
            / "generation-output"
            / "fixtures"
            / "generation_ast_v1"
        ).resolve()

    async def load(self, *, project_type: str) -> object:
        filename = _FIXTURES.get(project_type)
        if filename is None:
            raise ArtifactGenerationError("SYNTHETIC_FIXTURE_REQUIRED")
        path = (self._fixture_root / filename).resolve()
        if self._fixture_root not in path.parents:
            raise ArtifactGenerationError("SYNTHETIC_FIXTURE_REQUIRED")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ArtifactGenerationError("SYNTHETIC_FIXTURE_REQUIRED") from None
