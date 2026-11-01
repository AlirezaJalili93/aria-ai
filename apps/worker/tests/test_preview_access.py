from __future__ import annotations

import asyncio
import base64
from dataclasses import replace

import pytest
from aria_backend_application.preview_delivery import digest, prepare_preview
from test_preview_manifest import fixture
from test_preview_publication_runtime import Storage

from app.application.preview_access import AuthorizedPreview, PreviewAccessService
from app.application.preview_publication_runtime import preview_prefix


class Resolver:
    def __init__(self, authorization):
        self.authorization = authorization
        self.calls = []
        self.fail = False

    async def resolve(self, token_hash):
        self.calls.append(token_hash)
        if self.fail:
            raise RuntimeError("prohibited token diagnostic")
        return self.authorization


def setup_access():
    binding, manifest, files, transformer = fixture()
    prepared = prepare_preview(
        binding,
        manifest,
        files,
        lambda p, v, pages, paths: transformer.file(p, v, pages=pages, files=paths),
    )
    prefix = preview_prefix(binding)
    authorized = AuthorizedPreview(
        binding=binding,
        manifest_ref=prefix + "/delivery-manifest.json",
        manifest_hash=digest(prepared.manifest),
    )
    storage = Storage({authorized.manifest_ref: prepared.manifest})
    storage.values.update({prefix + "/files/" + f.path: f.content for f in prepared.files})
    resolver = Resolver(authorized)
    host = f"v-{binding.artifact_version_id}.aria-preview.test:8181"
    service = PreviewAccessService(
        host=host,
        core_origin="http://core.aria-core.test:8182",
        binding=binding,
        resolver=resolver,
        storage=storage,
        synthetic_sources=frozenset({(binding.artifact_version_id, binding.source_hash)}),
    )
    token = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
    return service, resolver, storage, authorized, host, token


@pytest.mark.parametrize(
    "path", ["index.html", "assets/styles.css", "generation-fixtures/media.svg"]
)
def test_get_head_authorize_each_file_and_head_verifies_same_bytes(path):
    async def scenario():
        service, resolver, storage, auth, host, token = setup_access()
        target = f"/p/{token}/{path}"
        get = await service.read(host=host, raw_target=target, method="GET")
        head = await service.read(host=host, raw_target=target, method="HEAD")
        assert get.status == head.status == 200 and head.body == b""
        assert get.body == storage.values[preview_prefix(auth.binding) + "/files/" + path]
        assert get.headers == head.headers and len(resolver.calls) == 2
        assert get.headers["Cache-Control"] == "no-store"
        assert get.headers["Referrer-Policy"] == "no-referrer"
        assert get.headers["Cross-Origin-Resource-Policy"] == "cross-origin"
        assert "Access-Control-Allow-Origin" not in get.headers
        assert "font-src 'none'" in get.headers["Content-Security-Policy"]
        assert (
            "frame-ancestors http://core.aria-core.test:8182"
            in get.headers["Content-Security-Policy"]
        )
        assert token not in repr(get) and auth.manifest_hash not in repr(auth)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "change",
    [
        "unknown",
        "resolver_error",
        "wrong_host",
        "wrong_version",
        "traversal",
        "encoded",
        "query",
        "manifest",
        "missing",
        "bad_file",
        "bad_manifest",
        "rebind",
    ],
)
def test_capability_host_manifest_and_storage_denials_are_uniform(change):
    async def scenario():
        service, resolver, storage, auth, host, token = setup_access()
        target = f"/p/{token}/index.html"
        if change == "unknown":
            resolver.authorization = None
        elif change == "resolver_error":
            resolver.fail = True
        elif change == "wrong_host":
            host = "other.aria-preview.test:8181"
        elif change == "wrong_version":
            from uuid import uuid4

            resolver.authorization = replace(
                auth, binding=replace(auth.binding, artifact_version_id=uuid4())
            )
        elif change in {"traversal", "encoded", "query", "manifest"}:
            target = (
                f"/p/{token}/"
                + {
                    "traversal": "../index.html",
                    "encoded": "%69ndex.html",
                    "query": "index.html?x=1",
                    "manifest": "delivery-manifest.json",
                }[change]
            )
        elif change == "missing":
            storage.values.pop(preview_prefix(auth.binding) + "/files/index.html")
        elif change == "bad_file":
            storage.values[preview_prefix(auth.binding) + "/files/index.html"] += b"!"
        elif change == "bad_manifest":
            storage.values[auth.manifest_ref] += b"!"
        else:
            resolver.authorization = replace(auth, manifest_ref="different/private/manifest.json")
        for method in ("GET", "HEAD"):
            result = await service.read(host=host, raw_target=target, method=method)
            assert result.status == 404 and result.error_code == "RESOURCE_NOT_FOUND"
            assert result.body == b""
            assert result.headers["Cache-Control"] == "no-store"
            assert result.headers["Referrer-Policy"] == "no-referrer"
            assert "Cross-Origin-Resource-Policy" not in result.headers
            assert token not in repr(result) and "prohibited" not in repr(result)

    asyncio.run(scenario())


def test_revocation_is_rechecked_on_subresource_after_document_read():
    async def scenario():
        service, resolver, _, _, host, token = setup_access()
        assert (
            await service.read(host=host, raw_target=f"/p/{token}/index.html", method="GET")
        ).status == 200
        resolver.authorization = None
        assert (
            await service.read(host=host, raw_target=f"/p/{token}/assets/styles.css", method="GET")
        ).status == 404
        assert len(resolver.calls) == 2

    asyncio.run(scenario())


def test_other_methods_do_not_resolve_capability_or_touch_storage():
    async def scenario():
        service, resolver, _, _, host, token = setup_access()
        for method in ("POST", "PUT", "DELETE", "OPTIONS"):
            result = await service.read(
                host=host, raw_target=f"/p/{token}/index.html", method=method
            )
            assert result.status == 405 and result.headers["Allow"] == "GET, HEAD"
        assert not resolver.calls

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["customer", "core_site", "host_version", "origin_injection"])
def test_configuration_cannot_replace_synthetic_or_separate_site_boundary(change):
    from aria_backend_application.preview_delivery import PreviewError

    _, resolver, storage, auth, host, _ = setup_access()
    origin = "http://core.aria-core.test:8182"
    allowed = frozenset({(auth.binding.artifact_version_id, auth.binding.source_hash)})
    if change == "customer":
        allowed = frozenset()
    elif change == "core_site":
        origin = "http://core.aria-preview.test:8182"
    elif change == "host_version":
        host = "v-other.aria-preview.test:8181"
    else:
        origin += "; script-src *"
    with pytest.raises(PreviewError):
        PreviewAccessService(
            host=host,
            core_origin=origin,
            binding=auth.binding,
            resolver=resolver,
            storage=storage,
            synthetic_sources=allowed,
        )
