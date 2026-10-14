from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from aria_backend_application.preview_delivery import PreviewError
from test_preview_manifest import fixture

from app.application.preview_publication_runtime import preview_prefix
from app.infrastructure.preview_storage import LocalSyntheticPreviewStorage


def test_private_namespace_create_verify_readback_and_conflict(tmp_path):
    async def scenario():
        binding, *_ = fixture()
        storage = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)
        key = preview_prefix(binding) + "/files/contact/index.html"
        assert await storage.read(key) is None
        await storage.create_or_verify(key, b"synthetic bytes")
        await storage.create_or_verify(key, b"synthetic bytes")
        assert await storage.read(key) == b"synthetic bytes"
        with pytest.raises(PreviewError, match="PREVIEW_DELIVERY_CONFLICT"):
            await storage.create_or_verify(key, b"different")
        assert await storage.read(key) == b"synthetic bytes"
        assert not list(tmp_path.rglob("*.partial"))

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "suffix",
    [
        "../index.html",
        "%2e/index.html",
        "//index.html",
        "files/../index.html",
        "files/index.html?x=1",
        "files/a.js",
        "secret.json",
        "files/a\\b.html",
    ],
)
def test_paths_outside_closed_namespace_rejected_before_file_access(tmp_path, suffix):
    async def scenario():
        binding, *_ = fixture()
        storage = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)
        with pytest.raises(PreviewError):
            await storage.create_or_verify(preview_prefix(binding) + "/" + suffix, b"secret")
        with pytest.raises(PreviewError):
            await storage.read("other-tenant/" + suffix)
        assert list(tmp_path.iterdir()) == []

    asyncio.run(scenario())


def test_atomic_concurrent_create_does_not_expose_partial_or_overwrite(tmp_path):
    binding, *_ = fixture()
    storage = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)
    key = preview_prefix(binding) + "/files/index.html"

    def write(value):
        try:
            asyncio.run(storage.create_or_verify(key, value))
            return "ok"
        except PreviewError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(write, [b"first", b"second"]))
    assert sorted(outcomes) == ["PREVIEW_DELIVERY_CONFLICT", "ok"]
    assert asyncio.run(storage.read(key)) in {b"first", b"second"}
    assert not list(tmp_path.rglob("*.partial"))


def test_manifest_uses_its_exact_private_name(tmp_path):
    async def scenario():
        binding, *_ = fixture()
        storage = LocalSyntheticPreviewStorage(root=tmp_path, binding=binding)
        key = preview_prefix(binding) + "/delivery-manifest.json"
        await storage.create_or_verify(key, b"private synthetic manifest")
        assert await storage.read(key) == b"private synthetic manifest"

    asyncio.run(scenario())
