from __future__ import annotations

import asyncio
import socket
from dataclasses import replace
from http.client import HTTPConnection

import pytest
from test_preview_access import setup_access

from app.application.preview_access import PreviewAccessService
from app.infrastructure.preview_http import controlled_preview_listener


def request(port, host, target, method="GET"):
    client = HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        client.request(method, target, headers={"Host": host})
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


def factory(resolver, storage, auth):
    def create(port):
        return PreviewAccessService(
            host=f"v-{auth.binding.artifact_version_id}.aria-preview.test:{port}",
            core_origin="http://core.aria-core.test:8182",
            binding=auth.binding,
            resolver=resolver,
            storage=storage,
            synthetic_sources=frozenset(
                {(auth.binding.artifact_version_id, auth.binding.source_hash)}
            ),
        )

    return create


@pytest.mark.parametrize(
    "path", ["index.html", "assets/styles.css", "generation-fixtures/media.svg"]
)
def test_http_get_head_delegate_per_file_and_preserve_headers(path, capsys):
    async def scenario():
        _, resolver, storage, auth, _, token = setup_access()
        async with controlled_preview_listener(factory(resolver, storage, auth)) as listener:
            host = f"v-{auth.binding.artifact_version_id}.aria-preview.test:{listener.port}"
            target = f"/p/{token}/{path}"
            get = await asyncio.to_thread(request, listener.port, host, target)
            head = await asyncio.to_thread(request, listener.port, host, target, "HEAD")
            assert get[0] == head[0] == 200
            assert head[2] == b"" and int(head[1]["Content-Length"]) == len(get[2])
            assert get[1] == head[1]
            assert get[1]["Cache-Control"] == "no-store"
            assert get[1]["Referrer-Policy"] == "no-referrer"
            assert get[1]["Cross-Origin-Resource-Policy"] == "cross-origin"
            assert "font-src 'none'" in get[1]["Content-Security-Policy"]
            assert "Access-Control-Allow-Origin" not in get[1]
            assert "Set-Cookie" not in get[1]
            assert len(resolver.calls) == 2
        with pytest.raises(OSError):
            await asyncio.to_thread(socket.create_connection, ("127.0.0.1", listener.port), 1)

    asyncio.run(scenario())
    output = capsys.readouterr()
    assert not output.out and not output.err


@pytest.mark.parametrize(
    "change",
    [
        "host",
        "unknown",
        "encoded",
        "traversal",
        "query",
        "manifest",
        "absolute",
        "double_slash",
        "wrong_version",
    ],
)
def test_http_raw_targets_never_normalize_into_authority(change, capsys):
    async def scenario():
        _, resolver, storage, auth, _, token = setup_access()
        async with controlled_preview_listener(factory(resolver, storage, auth)) as listener:
            host = f"v-{auth.binding.artifact_version_id}.aria-preview.test:{listener.port}"
            target = f"/p/{token}/index.html"
            if change == "host":
                host = "other.aria-preview.test"
            elif change == "unknown":
                resolver.authorization = None
            elif change == "wrong_version":
                resolver.authorization = replace(auth, binding=replace(auth.binding, version_no=2))
            elif change == "absolute":
                target = f"http://{host}{target}"
            elif change == "double_slash":
                target = "/" + target
            else:
                target = (
                    f"/p/{token}/"
                    + {
                        "encoded": "%69ndex.html",
                        "traversal": "../index.html",
                        "query": "index.html?x=1",
                        "manifest": "delivery-manifest.json",
                    }[change]
                )
            result = await asyncio.to_thread(request, listener.port, host, target)
            assert result[0] == 404 and result[2] == b""
            assert result[1]["Cache-Control"] == "no-store"
            assert result[1]["Referrer-Policy"] == "no-referrer"
            if token in repr(result):
                pytest.fail("Capability in denial response (value withheld)")

    asyncio.run(scenario())
    output = capsys.readouterr()
    assert not output.out and not output.err


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "OPTIONS", "CUSTOM"])
def test_http_other_methods_do_not_authorize_or_write(method):
    async def scenario():
        _, resolver, storage, auth, _, token = setup_access()
        async with controlled_preview_listener(factory(resolver, storage, auth)) as listener:
            host = f"v-{auth.binding.artifact_version_id}.aria-preview.test:{listener.port}"
            result = await asyncio.to_thread(
                request, listener.port, host, f"/p/{token}/index.html", method
            )
            assert result[0] == 405 and result[1]["Allow"] == "GET, HEAD"
            assert not resolver.calls

    asyncio.run(scenario())


def test_duplicate_host_and_malformed_protocol_are_not_logged(capsys):
    def raw(port, request_bytes):
        with socket.create_connection(("127.0.0.1", port), timeout=10) as client:
            client.sendall(request_bytes)
            client.shutdown(socket.SHUT_WR)
            chunks = []
            while value := client.recv(4096):
                chunks.append(value)
            return b"".join(chunks)

    async def scenario():
        _, resolver, storage, auth, _, token = setup_access()
        async with controlled_preview_listener(factory(resolver, storage, auth)) as listener:
            host = f"v-{auth.binding.artifact_version_id}.aria-preview.test:{listener.port}"
            target = f"/p/{token}/index.html"
            duplicate = f"GET {target} HTTP/1.1\r\nHost: {host}\r\nHost: {host}\r\n\r\n"
            malformed = f"GET {target} HTTP/synthetic-private-marker\r\nHost: {host}\r\n\r\n"
            for value in (duplicate, malformed):
                result = await asyncio.to_thread(raw, listener.port, value.encode())
                if token.encode() in result or b"synthetic-private-marker" in result:
                    pytest.fail("Raw request data in parser response (value withheld)")
                assert b"404 Not Found" in result
                assert b"Cache-Control: no-store" in result
            assert not resolver.calls

    asyncio.run(scenario())
    output = capsys.readouterr()
    assert not output.out and not output.err


def test_factory_failure_closes_bound_listener():
    from aria_backend_application.preview_delivery import PreviewError

    async def scenario():
        ports = []

        def rejected(port):
            ports.append(port)
            raise PreviewError("FEATURE_NOT_ENABLED")

        with pytest.raises(PreviewError):
            async with controlled_preview_listener(rejected):
                pytest.fail("Invalid synthetic configuration reached listener")
        assert len(ports) == 1
        with pytest.raises(OSError):
            await asyncio.to_thread(socket.create_connection, ("127.0.0.1", ports[0]), 1)

    asyncio.run(scenario())
