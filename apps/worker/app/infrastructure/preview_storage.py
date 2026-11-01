"""Dedicated local proof storage, not a public filesystem or Hosted storage adapter."""

from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from aria_backend_application.preview_delivery import PreviewBinding, PreviewError, file_path

from app.application.preview_publication_runtime import preview_prefix


class LocalSyntheticPreviewStorage:
    def __init__(self, *, root: Path, binding: PreviewBinding) -> None:
        self._root = root.absolute()
        self._prefix = preview_prefix(binding) + "/"

    async def read(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self._read, key)

    async def create_or_verify(self, key: str, value: bytes) -> None:
        await asyncio.to_thread(self._create_or_verify, key, value)

    def _target(self, key: str) -> Path:
        if not key.startswith(self._prefix):
            raise PreviewError("PREVIEW_SOURCE_INVALID")
        suffix = key[len(self._prefix) :]
        if suffix != "delivery-manifest.json":
            if not suffix.startswith("files/"):
                raise PreviewError("PREVIEW_SOURCE_INVALID")
            file_path(suffix[6:])
        target = self._root.joinpath(*key.split("/"))
        # Local proof root is caller-owned. Reject links/junctions instead of resolving them.
        for item in (target, *target.parents):
            if item.is_symlink() or item.is_junction():
                raise PreviewError("PREVIEW_SOURCE_INVALID")
        if self._root not in target.parents:
            raise PreviewError("PREVIEW_SOURCE_INVALID")
        return target

    def _read(self, key: str) -> bytes | None:
        try:
            return self._target(key).read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            raise PreviewError("PREVIEW_STORAGE_ERROR", retryable=True) from None

    def _create_or_verify(self, key: str, value: bytes) -> None:
        temporary: Path | None = None
        try:
            target = self._target(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._target(key)
            # Publish a complete file atomically without replacing a racing writer's file.
            with tempfile.NamedTemporaryFile(
                dir=target.parent, prefix=".preview-", suffix=".partial", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            with suppress(FileExistsError):
                os.link(temporary, target)
            if self._target(key).read_bytes() != value:
                raise PreviewError("PREVIEW_DELIVERY_CONFLICT")
        except OSError:
            raise PreviewError("PREVIEW_STORAGE_ERROR", retryable=True) from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    raise PreviewError("PREVIEW_STORAGE_ERROR", retryable=True) from None
