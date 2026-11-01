from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from uuid import UUID

from aria_backend_application.generation_ast import (
    CANDIDATE_SCHEMA_VERSION,
    CANONICAL_SCHEMA_VERSION,
    GenerationAstValidationError,
    validate_generation_candidate,
)
from aria_backend_application.preview_delivery import PreviewError, canonical_json

from app.application.artifact_generation_runtime import _candidate_requirement_ids
from app.infrastructure.artifact_builder import BUILDER_TIMEOUT_SECONDS


class FixedNodePreviewCanonicalValidator:
    """Reuse the frozen 0095/0096 consumer validator without invoking the Renderer."""

    def __init__(self, *, repository_root: Path, node_executable: str = "node") -> None:
        self._root = repository_root.resolve()
        self._node = node_executable

    async def validate(self, ast: Mapping[str, object]) -> None:
        _validate_content_contract(ast)
        process: asyncio.subprocess.Process | None = None
        with tempfile.TemporaryDirectory(prefix="aria-0102-validation-") as temporary:
            try:
                target = Path(temporary) / "canonical-ast.json"
                target.write_bytes(canonical_json(ast))
                process = await asyncio.create_subprocess_exec(
                    self._node,
                    str(
                        self._root
                        / "scripts/artifact-generation/validate-preview-canonical-ast.mjs"
                    ),
                    str(target),
                    cwd=self._root,
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
                        "TEMP": temporary,
                        "TMP": temporary,
                        "NODE_ENV": "production",
                    },
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                # Inherit the fixed local 0100 Node-tool bound; no new policy/default introduced.
                code = await asyncio.wait_for(process.wait(), timeout=BUILDER_TIMEOUT_SECONDS)
                if code != 0:
                    raise PreviewError("PREVIEW_SOURCE_INVALID")
            except (OSError, TimeoutError, TypeError, ValueError):
                raise PreviewError("PREVIEW_SOURCE_INVALID") from None
            finally:
                if process is not None and process.returncode is None:
                    process.kill()
                    await process.wait()


def _validate_content_contract(ast: Mapping[str, object]) -> None:
    """Reuse 0095 content/closed-property validation on a copy, never repair stored source."""
    try:
        candidate = deepcopy(dict(ast))
        if candidate["schema_version"] != CANONICAL_SCHEMA_VERSION:
            raise ValueError
        candidate["schema_version"] = CANDIDATE_SCHEMA_VERSION
        pages = candidate["pages"]
        if not isinstance(pages, list):
            raise ValueError
        identities: set[UUID] = set()
        for page in pages:
            if not isinstance(page, dict):
                raise ValueError
            nodes = [(page, "page_id")]
            sections = page["sections"]
            if not isinstance(sections, list):
                raise ValueError
            for section in sections:
                if not isinstance(section, dict) or section.pop("protected_state") not in {
                    "unprotected",
                    "protected",
                }:
                    raise ValueError
                nodes.append((section, "section_id"))
            for node, field in nodes:
                identity = node.pop(field)
                if not isinstance(identity, str):
                    raise ValueError
                identifier = UUID(identity)
                if identifier in identities:
                    raise ValueError
                identities.add(identifier)
        validated = validate_generation_candidate(
            candidate, pinned_requirement_ids=_candidate_requirement_ids(candidate)
        )
        if validated != candidate:
            raise ValueError
    except (KeyError, TypeError, ValueError, GenerationAstValidationError):
        raise PreviewError("PREVIEW_SOURCE_INVALID") from None
