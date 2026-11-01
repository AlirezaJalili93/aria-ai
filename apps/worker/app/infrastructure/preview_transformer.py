from __future__ import annotations

import html
from html.parser import HTMLParser
from pathlib import Path

from aria_backend_application.preview_delivery import PreviewError, file_path, relative_reference

_VOID = frozenset({"meta", "link", "img", "input", "br", "hr"})
_TAGS = _VOID | frozenset(
    {
        "html",
        "head",
        "body",
        "main",
        "header",
        "footer",
        "nav",
        "section",
        "article",
        "div",
        "span",
        "h1",
        "h2",
        "h3",
        "p",
        "a",
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        "label",
        "textarea",
        "button",
        "fieldset",
        "legend",
        "select",
        "option",
        "strong",
        "em",
        "figure",
        "blockquote",
        "figcaption",
    }
)
_ATTRIBUTES = frozenset(
    {
        "id",
        "class",
        "lang",
        "dir",
        "charset",
        "name",
        "content",
        "rel",
        "href",
        "src",
        "alt",
        "width",
        "height",
        "role",
        "type",
        "value",
        "required",
        "checked",
        "disabled",
        "readonly",
        "min",
        "max",
        "minlength",
        "maxlength",
        "pattern",
        "placeholder",
        "rows",
        "autocomplete",
        "for",
        "multiple",
        "selected",
        "data-page-id",
        "data-section-id",
        "data-protected-state",
        "data-component-type",
        "data-layout",
        "data-responsive-rule",
        "tabindex",
        "data-component",
        "data-protected",
        "data-project-type",
        "data-theme",
        "loading",
        "decoding",
        "as",
    }
)


class PreviewTransformer:
    """Only the exact Application-owned 0100 CSS/SVG profile; no generic CSS repair."""

    def __init__(self, repository_root: Path) -> None:
        self.source_css = (
            (repository_root / "packages/design-tokens/tokens.css").read_bytes()
            + b"\n"
            + (repository_root / "packages/generation-renderer/styles.css").read_bytes()
        )
        self.source_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 675" role="img" '
            'aria-label="دارایی مصنوعی آریا"><rect width="1200" height="675" fill="#e2e8f0"/></svg>'
        ).encode()

    def html(
        self, content: bytes, *, file_path: str, pages: dict[str, str], files: set[str]
    ) -> bytes:
        parser = _HtmlProjection(file_path, pages, files)
        try:
            parser.feed(content.decode("utf-8", errors="strict"))
            parser.close()
            if parser.stack or parser.html_count != 1:
                raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
            return "".join(parser.output).encode()
        except (UnicodeDecodeError, ValueError):
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED") from None

    def css(self, content: bytes) -> bytes:
        # Exact-byte profile verification rejects every alternate/escaped CSS fetch spelling.
        if content != self.source_css:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        import_rule = b'@import "@aria/design-tokens/tokens.css";'
        font_rule = b"--primitive-font-family-body: Vazirmatn, system-ui, sans-serif;"
        if content.count(import_rule) != 1 or content.count(font_rule) != 1:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        return content.replace(import_rule, b"", 1).replace(
            font_rule, b"--primitive-font-family-body: system-ui, sans-serif;", 1
        )

    def svg(self, content: bytes) -> bytes:
        if content != self.source_svg:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        return content

    def file(self, path: str, content: bytes, *, pages: dict[str, str], files: set[str]) -> bytes:
        file_path(path)
        if path in pages.values():
            return self.html(content, file_path=path, pages=pages, files=files)
        if path == "assets/styles.css":
            return self.css(content)
        if path == "generation-fixtures/media.svg":
            return self.svg(content)
        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")


class _HtmlProjection(HTMLParser):
    def __init__(self, source: str, pages: dict[str, str], files: set[str]) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.pages = pages
        self.files = files
        self.stack: list[str] = []
        self.output: list[str] = []
        self.html_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _TAGS or len({k for k, _ in attrs}) != len(attrs):
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        if tag == "html":
            self.html_count += 1
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "preload":
            target = values.get("href")
            if (
                set(values) != {"rel", "as", "href"}
                or values.get("as") != "image"
                or target is None
                or not target.startswith("/")
                or target[1:] not in self.files
                or not target.endswith(".svg")
            ):
                raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
            # Owner-approved omission of a verified image hint, never a font/remote hint.
            return
        rendered: list[str] = []
        for key, value in attrs:
            if key not in _ATTRIBUTES and not key.startswith("aria-"):
                raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
            if key in {"href", "src"}:
                if tag == "a" and key == "href" and value in self.pages:
                    target = self.pages[value]
                elif (
                    tag == "link"
                    and key == "href"
                    and values.get("rel") == "stylesheet"
                    and value == "/assets/styles.css"
                ):
                    target = "assets/styles.css"
                elif tag == "img" and key == "src" and value is not None:
                    target = value.removeprefix("/")
                    if (
                        value != "/" + target
                        or target not in self.files
                        or not target.endswith(".svg")
                    ):
                        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
                else:
                    raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
                if target not in self.files:
                    raise PreviewError("PREVIEW_SOURCE_INVALID")
                value = relative_reference(self.source, target)
            rendered.append(key if value is None else f'{key}="{html.escape(value, quote=True)}"')
        suffix = " " + " ".join(rendered) if rendered else ""
        self.output.append(f"<{tag}{suffix}>")
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _VOID:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or self.stack.pop() != tag:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.output.append(data)

    def handle_entityref(self, name: str) -> None:
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.output.append(f"&#{name};")

    def handle_decl(self, decl: str) -> None:
        if decl.lower() != "doctype html":
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        self.output.append("<!doctype html>")

    def handle_comment(self, data: str) -> None:
        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")

    def handle_pi(self, data: str) -> None:
        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")

    def unknown_decl(self, data: str) -> None:
        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
