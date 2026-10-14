from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

from app.application.artifact_generation_runtime import (
    ArtifactBuildFile,
    ArtifactGenerationError,
)

BUILDER_TIMEOUT_SECONDS = 60
_ALLOWED_SUFFIXES = frozenset({".html", ".css", ".svg"})


class FixedNodeArtifactBuilder:
    def __init__(self, *, repository_root: Path, node_executable: str = "node") -> None:
        self._repository_root = repository_root.resolve()
        self._node_executable = node_executable
        self._script = (
            self._repository_root / "scripts" / "artifact-generation" / "build-static-bundle.mjs"
        )

    async def build(
        self, canonical_ast: Mapping[str, object]
    ) -> tuple[ArtifactBuildFile, ...]:
        with tempfile.TemporaryDirectory(prefix="aria-0100-") as temporary:
            root = Path(temporary)
            input_path = root / "canonical-ast.json"
            output_root = root / "output"
            input_path.write_text(
                json.dumps(
                    canonical_ast,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                "TEMP": temporary,
                "TMP": temporary,
                "NODE_ENV": "production",
            }
            try:
                process = await asyncio.create_subprocess_exec(
                    self._node_executable,
                    str(self._script),
                    str(input_path),
                    str(output_root),
                    cwd=str(self._repository_root),
                    env=environment,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return_code = await asyncio.wait_for(
                    process.wait(), timeout=BUILDER_TIMEOUT_SECONDS
                )
            except (OSError, TimeoutError):
                raise ArtifactGenerationError("ARTIFACT_BUILD_FAILED") from None
            if return_code != 0:
                raise ArtifactGenerationError("ARTIFACT_BUILD_FAILED")
            return _read_validated_output(output_root)


def _read_validated_output(root: Path) -> tuple[ArtifactBuildFile, ...]:
    if not root.is_dir():
        raise ArtifactGenerationError("ARTIFACT_BUILD_INVALID")
    values: list[ArtifactBuildFile] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if root.resolve() not in resolved.parents or candidate.suffix not in _ALLOWED_SUFFIXES:
            raise ArtifactGenerationError("ARTIFACT_BUILD_INVALID")
        relative = candidate.relative_to(root).as_posix()
        content = candidate.read_bytes()
        values.append(ArtifactBuildFile(relative, _media_type(candidate.suffix), content))
    if not values or not any(value.path == "index.html" for value in values):
        raise ArtifactGenerationError("ARTIFACT_BUILD_INVALID")
    return tuple(values)


def _media_type(suffix: str) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".svg": "image/svg+xml",
    }[suffix]
