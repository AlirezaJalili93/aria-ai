from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast

from aria_observability import StructuredEventLogger

from app.modules.scope.domain.scope_draft import (
    ScopeDraftValidationError,
    validate_scope_content,
)
from app.modules.sharing.application.ports import (
    ResolvedPublicScope,
    ScopeShareLinkRepositoryError,
    ScopeShareLinkUnitOfWorkFactory,
    ScopeShareTokenHasher,
)


class PublicScopeShareNotFound(Exception):
    """The capability is malformed, unavailable, expired, revoked, or inaccessible."""


class PublicScopeShareResolver:
    def __init__(
        self,
        unit_of_work_factory: ScopeShareLinkUnitOfWorkFactory,
        token_hasher: ScopeShareTokenHasher,
        event_logger: StructuredEventLogger,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._token_hasher = token_hasher
        self._event_logger = event_logger
        self._clock = clock

    async def resolve(self, *, token: str) -> ResolvedPublicScope:
        started_at = perf_counter()
        if not is_canonical_public_token(token):
            self._emit_not_found(started_at)
            raise PublicScopeShareNotFound
        token_hash = self._token_hasher.hash_public_token(token)
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                resolved = await unit_of_work.repository.resolve_public(
                    token_hash=token_hash,
                    now=self._clock(),
                )
        except ScopeShareLinkRepositoryError:
            self._event_logger.emit(
                "scope_share.resolve_failed",
                level="ERROR",
                operation="resolve",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
                error_code="SCOPE_SHARE_RESOLUTION_FAILURE",
            )
            raise
        if resolved is None:
            self._emit_not_found(started_at)
            raise PublicScopeShareNotFound
        try:
            resolved = replace(
                resolved,
                snapshot_data=project_public_scope_content(resolved.snapshot_data),
            )
        except ScopeDraftValidationError:
            self._event_logger.emit(
                "scope_share.resolve_failed",
                level="ERROR",
                operation="resolve",
                duration_ms=(perf_counter() - started_at) * 1000,
                status="failed",
                error_code="PUBLIC_SCOPE_PROJECTION_FAILURE",
            )
            raise ScopeShareLinkRepositoryError from None
        self._event_logger.emit(
            "scope_share.resolve_succeeded",
            scope_share_link_id=str(resolved.share_link_id),
            scope_version_id=str(resolved.scope_version_id),
            version_no=resolved.version_no,
            operation="resolve",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="succeeded",
        )
        return resolved

    def _emit_not_found(self, started_at: float) -> None:
        self._event_logger.emit(
            "scope_share.resolve_not_found",
            level="WARNING",
            operation="resolve",
            reason_code="not_resolvable",
            duration_ms=(perf_counter() - started_at) * 1000,
            status="not_found",
            error_code="RESOURCE_NOT_FOUND",
        )


def is_canonical_public_token(token: str) -> bool:
    if len(token) != 43 or not token.isascii():
        return False
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (binascii.Error, UnicodeEncodeError, ValueError):
        return False
    if len(decoded) != 32:
        return False
    canonical = base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii")
    return canonical == token


def project_public_scope_content(snapshot_data: dict[str, object]) -> dict[str, object]:
    """Return the recursive public allowlist; internal lineage never crosses this boundary."""
    validated = validate_scope_content(snapshot_data)
    sections: list[dict[str, object]] = []
    for section in validated["sections"]:
        section_id = section["section_id"]
        sections.append(
            {
                "section_id": section_id,
                "value": _project_public_section_value(section_id, section["value"]),
            }
        )
    return {"schema_version": "scope_content_schema_v1", "sections": sections}


def _project_public_section_value(section_id: str, value: object) -> object:
    if section_id in {"summary", "visual_direction"}:
        return value
    if section_id in {
        "goals",
        "constraints",
        "assumptions",
        "out_of_scope",
        "acceptance_notes",
    }:
        return list(cast(list[str], value))
    if section_id == "pages_sections":
        pages = cast(list[dict[str, Any]], value)
        return [
            {
                "page_name": page["page_name"],
                "sections": [{"name": item["name"]} for item in page["sections"]],
            }
            for page in pages
        ]
    allowed_keys = {
        "requirements": ("text", "priority"),
        "content": ("description",),
        "resolved_gaps": ("text", "resolution_type"),
        "remaining_non_blocking_gaps": ("text", "severity"),
    }[section_id]
    items = cast(list[dict[str, Any]], value)
    return [
        {key: item[key] for key in allowed_keys}
        for item in items
    ]
