from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from aria_backend_application.preview_delivery import (
    PreviewError,
    parse_preview_route,
    relative_reference,
)

from app.infrastructure.preview_transformer import PreviewTransformer

ROOT = Path(__file__).parents[3]


def test_nested_references_never_contain_capability() -> None:
    for source, target, expected in (
        ("index.html", "assets/styles.css", "assets/styles.css"),
        ("contact/index.html", "assets/styles.css", "../assets/styles.css"),
        ("services/design/index.html", "assets/styles.css", "../../assets/styles.css"),
        ("contact/index.html", "index.html", "../index.html"),
    ):
        assert relative_reference(source, target) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/p/" + "a" * 43 + "/../index.html",
        "/p/" + "a" * 43 + "/%2e%2e/index.html",
        "/p/" + "a" * 43 + "/index.html?token=x",
        "/p/" + "a" * 43 + "/contact/",
        "/p/" + "a" * 43 + "/assets//styles.css",
        "/p/" + "a" * 43 + "/assets\\styles.css",
        "/p/not-a-token/index.html",
    ],
)
def test_noncanonical_routes_fail_closed_without_echo(path: str) -> None:
    with pytest.raises(PreviewError) as caught:
        parse_preview_route(path)
    assert str(caught.value) == "RESOURCE_NOT_FOUND"
    assert path not in repr(caught.value)


def test_only_hash_leaves_route_parser() -> None:
    import base64

    token = base64.urlsafe_b64encode(b"x" * 32).decode().rstrip("=")
    route = parse_preview_route(f"/p/{token}/contact/index.html")
    assert route.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert route.file_path == "contact/index.html"
    assert token not in repr(route)
    assert route.token_hash not in repr(route)


def test_transform_is_deterministic_and_preserves_source() -> None:
    transformer = PreviewTransformer(ROOT)
    html = (
        '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="/assets/styles.css"></head><body>'
        '<main class="aria-gen-page"><h1>نمونه فارسی</h1>'
        '<a href="/">خانه</a><img src="/generation-fixtures/media.svg" alt="آزمون">'
        "</main></body></html>"
    ).encode()
    css = transformer.source_css
    paths = {
        "index.html",
        "contact/index.html",
        "assets/styles.css",
        "generation-fixtures/media.svg",
    }
    output = transformer.html(
        html,
        file_path="contact/index.html",
        pages={"/": "index.html", "/contact": "contact/index.html"},
        files=paths,
    )
    assert output == transformer.html(
        html,
        file_path="contact/index.html",
        pages={"/": "index.html", "/contact": "contact/index.html"},
        files=paths,
    )
    assert b'href="../index.html"' in output
    assert b'href="../assets/styles.css"' in output
    assert b'src="../generation-fixtures/media.svg"' in output
    assert "نمونه فارسی" in output.decode()
    assert b'href="/assets/styles.css"' in html
    converted = transformer.css(css)
    assert b"@import" not in converted
    assert b"Vazirmatn" not in converted
    assert b"system-ui, sans-serif" in converted
    assert css == transformer.source_css


@pytest.mark.parametrize(
    "content",
    [
        '<script>fetch("https://outside.test")</script>',
        '<img src="//outside.test/x" alt="">',
        '<a href="/unknown">unknown</a>',
        '<a href="/" href="https://outside.test">duplicate</a>',
        '<base href="https://outside.test">',
        '<meta http-equiv="refresh" content="0;url=https://outside.test">',
        '<input onfocus="alert(1)">',
        '<form action="/">x</form>',
        '<img srcset="https://outside.test/a 2x">',
    ],
)
def test_unsupported_markup_is_rejected_not_repaired(content: str) -> None:
    transformer = PreviewTransformer(ROOT)
    with pytest.raises(PreviewError) as caught:
        transformer.html(
            content.encode(),
            file_path="index.html",
            pages={"/": "index.html"},
            files={"index.html"},
        )
    assert str(caught.value) == "PREVIEW_SOURCE_UNSUPPORTED"
    assert content not in str(caught.value)


def test_css_and_svg_must_match_verified_application_profile() -> None:
    transformer = PreviewTransformer(ROOT)
    for unsafe in (
        b"@font-face{src:url(x)}",
        b"@\\69mport 'https://outside.test/x';",
        transformer.source_css + b"body{background:url(x)}",
    ):
        with pytest.raises(PreviewError):
            transformer.css(unsafe)
    with pytest.raises(PreviewError):
        transformer.svg(b"<svg><script>bad()</script></svg>")
    assert transformer.svg(transformer.source_svg) == transformer.source_svg


def test_transformer_rejects_unknown_files() -> None:
    transformer = PreviewTransformer(ROOT)
    with pytest.raises(PreviewError):
        transformer.file(
            "runtime.js",
            b"console.log('not a supported 0100 bundle')",
            pages={"/": "index.html"},
            files={"runtime.js"},
        )


def test_only_verified_image_preload_is_removed() -> None:
    transformer = PreviewTransformer(ROOT)
    value = (
        b'<html><head><link rel="preload" as="image" '
        b'href="/generation-fixtures/media.svg"></head><body></body></html>'
    )
    output = transformer.html(
        value,
        file_path="index.html",
        pages={"/": "index.html"},
        files={"index.html", "generation-fixtures/media.svg"},
    )
    assert b"preload" not in output
    assert b"preload" in value
    for unsafe in (
        value.replace(b'"image"', b'"font"'),
        value.replace(b"/generation-fixtures/media.svg", b"//outside.test/x.svg"),
        value.replace(b"/generation-fixtures/media.svg", b"/unknown.svg"),
    ):
        with pytest.raises(PreviewError):
            transformer.html(
                unsafe,
                file_path="index.html",
                pages={"/": "index.html"},
                files={"index.html", "generation-fixtures/media.svg"},
            )
