"""Read-only Local/Synthetic file authorization; no listener or hosted composition."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, cast
from uuid import UUID

from aria_backend_application.preview_delivery import (
    PreviewBinding,
    PreviewError,
    digest,
    parse_preview_route,
    verified_delivery_manifest,
)

from app.application.preview_publication_runtime import PreviewSourceReader, preview_prefix


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthorizedPreview:
    binding: PreviewBinding = field(repr=False)
    manifest_ref: str = field(repr=False)
    manifest_hash: str = field(repr=False)


class PreviewCapabilityResolver(Protocol):
    async def resolve(self, token_hash: str) -> AuthorizedPreview | None: ...


@dataclass(frozen=True, slots=True)
class PreviewReadResult:
    status: int
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)
    error_code: str | None = None


class PreviewAccessService:
    def __init__(
        self,
        *,
        host: str,
        core_origin: str,
        binding: PreviewBinding,
        resolver: PreviewCapabilityResolver,
        storage: PreviewSourceReader,
        synthetic_sources: frozenset[tuple[UUID, str]],
    ) -> None:
        preview = re.fullmatch(
            re.escape(f"v-{binding.artifact_version_id}.aria-preview.test") + r":([1-9][0-9]{0,4})",
            host,
        )
        core = re.fullmatch(r"http://core\.aria-core\.test:([1-9][0-9]{0,4})", core_origin)
        if preview is None or core is None or any(int(m[1]) > 65535 for m in (preview, core)):
            raise PreviewError("VALIDATION_FAILED")
        if (binding.artifact_version_id, binding.source_hash) not in synthetic_sources:
            raise PreviewError("FEATURE_NOT_ENABLED")
        self._host = host
        self._binding = binding
        self._resolver = resolver
        self._storage = storage
        # This source profile prohibits all inline script/style. The frozen hash lists are
        # therefore empty, not replaced by unsafe-inline or hashes of guessed/re-rendered bytes.
        self._headers = {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
            "Content-Security-Policy": "; ".join(
                (
                    "default-src 'none'",
                    "base-uri 'none'",
                    "script-src 'self'",
                    "style-src 'self'",
                    "img-src 'self'",
                    "font-src 'none'",
                    "connect-src 'none'",
                    "form-action 'none'",
                    "object-src 'none'",
                    "frame-src 'none'",
                    "worker-src 'none'",
                    f"frame-ancestors {core_origin}",
                )
            ),
        }

    async def read(self, *, host: str, raw_target: str, method: str) -> PreviewReadResult:
        if method not in {"GET", "HEAD"}:
            return PreviewReadResult(405, {**self._headers, "Allow": "GET, HEAD"}, b"")
        try:
            if host != self._host:
                raise PreviewError("RESOURCE_NOT_FOUND")
            route = parse_preview_route(raw_target)
            authorized = await self._resolver.resolve(route.token_hash)
            if authorized is None or authorized.binding != self._binding:
                raise PreviewError("RESOURCE_NOT_FOUND")
            prefix = preview_prefix(self._binding)
            if authorized.manifest_ref != prefix + "/delivery-manifest.json":
                raise PreviewError("RESOURCE_NOT_FOUND")
            manifest_bytes = await self._storage.read(authorized.manifest_ref)
            if manifest_bytes is None:
                raise PreviewError("RESOURCE_NOT_FOUND")
            manifest = verified_delivery_manifest(
                manifest_bytes, binding=self._binding, expected_hash=authorized.manifest_hash
            )
            rows = cast(list[dict[str, object]], manifest["files"])
            row = next((r for r in rows if r["path"] == route.file_path), None)
            if row is None:
                raise PreviewError("RESOURCE_NOT_FOUND")
            value = await self._storage.read(prefix + "/files/" + route.file_path)
            if value is None or len(value) != row["size_bytes"] or digest(value) != row["sha256"]:
                raise PreviewError("RESOURCE_NOT_FOUND")
            headers = {
                **self._headers,
                "Content-Type": cast(str, row["media_type"]),
                "Content-Length": str(len(value)),
                "Cross-Origin-Resource-Policy": "cross-origin",
            }
            return PreviewReadResult(200, headers, value if method == "GET" else b"")
        except Exception:
            # The route is a capability oracle only for successfully authorized exact files.
            # Diagnostics, exceptions, URLs and hashes never enter outward failure data.
            return PreviewReadResult(404, dict(self._headers), b"", "RESOURCE_NOT_FOUND")
