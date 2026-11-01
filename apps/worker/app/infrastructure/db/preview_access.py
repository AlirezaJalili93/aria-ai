from __future__ import annotations

import re
from uuid import UUID

from aria_backend_application.preview_delivery import PreviewBinding
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.preview_access import AuthorizedPreview


class PostgresPreviewCapabilityResolver:
    """Read-only use of the already reviewed resolver; no anonymous table access."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def resolve(self, token_hash: str) -> AuthorizedPreview | None:
        if not re.fullmatch(r"[0-9a-f]{64}", token_hash):
            return None
        try:
            # Revoke/read ordering ends here; authorized in-flight reads may finish after
            # revoke. The transaction does not stay open while reading private file bytes.
            async with self._engine.begin() as connection:
                value = await connection.scalar(
                    text("SELECT aria_internal.resolve_preview(:token_hash)"),
                    {"token_hash": token_hash},
                )
            return _authorization(value)
        except SQLAlchemyError:
            return None


def _authorization(value: object) -> AuthorizedPreview | None:
    try:
        if not isinstance(value, dict) or set(value) != {
            "account_id",
            "project_id",
            "artifact_id",
            "artifact_version_id",
            "representation_id",
            "version_no",
            "source_hash",
            "source_ref",
            "manifest_ref",
            "manifest_hash",
        }:
            return None
        if type(value["version_no"]) is not int or value["version_no"] < 1:
            return None
        for field in ("source_hash", "manifest_hash"):
            if not isinstance(value[field], str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", value[field]
            ):
                return None
        for field in ("source_ref", "manifest_ref"):
            if not isinstance(value[field], str) or not value[field]:
                return None
        return AuthorizedPreview(
            binding=PreviewBinding(
                account_id=UUID(str(value["account_id"])),
                project_id=UUID(str(value["project_id"])),
                artifact_id=UUID(str(value["artifact_id"])),
                artifact_version_id=UUID(str(value["artifact_version_id"])),
                representation_id=UUID(str(value["representation_id"])),
                version_no=value["version_no"],
                source_hash=value["source_hash"],
                source_ref=value["source_ref"],
            ),
            manifest_ref=value["manifest_ref"],
            manifest_hash=value["manifest_hash"],
        )
    except (ValueError, KeyError, TypeError):
        return None
