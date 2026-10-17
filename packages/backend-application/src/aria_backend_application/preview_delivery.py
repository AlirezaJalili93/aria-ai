"""Framework-free exact-version Preview contracts; secrets never enter diagnostics."""

from __future__ import annotations

import base64
import hashlib
import json
import posixpath
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

TRANSFORMER_VERSION = "preview_delivery_transformer_v1"
DELIVERY_POLICY_VERSION = "preview_delivery_policy_v1"
MANIFEST_VERSION = "preview_delivery_manifest/v1"
ERROR_CODES = frozenset(
    {
        "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED",
        "IDEMPOTENCY_CONFLICT",
        "FEATURE_NOT_ENABLED",
        "ARTIFACT_VERSION_NOT_READY",
        "PREVIEW_SOURCE_UNSUPPORTED",
        "PREVIEW_SOURCE_INVALID",
        "PREVIEW_PUBLICATION_IN_PROGRESS",
        "PREVIEW_DELIVERY_CONFLICT",
        "PREVIEW_STORAGE_ERROR",
        "PREVIEW_FINALIZATION_RECOVERABLE",
        "PREVIEW_PUBLICATION_REVOKED",
        "PREVIEW_CAPABILITY_ALREADY_ISSUED",
    }
)
MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}


class PreviewError(Exception):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        self.code = code if code in ERROR_CODES else "PREVIEW_SOURCE_INVALID"
        self.retryable = retryable
        super().__init__(self.code)


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def file_path(value: str) -> str:
    if (
        not value
        or not re.fullmatch(r"[a-z0-9./_-]+", value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or not value.endswith((".html", ".css", ".svg"))
    ):
        raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
    return value


def page_file(value: str) -> str:
    if not re.fullmatch(
        r"/|/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*", value
    ):
        raise PreviewError("PREVIEW_SOURCE_INVALID")
    return "index.html" if value == "/" else value[1:] + "/index.html"


def relative_reference(source: str, target: str) -> str:
    file_path(source)
    file_path(target)
    return posixpath.relpath(target, posixpath.dirname(source) or ".")


@dataclass(frozen=True, slots=True)
class PreviewRoute:
    token_hash: str = field(repr=False)
    file_path: str


def parse_preview_route(raw_path: str) -> PreviewRoute:
    try:
        parts = raw_path.split("/")
        if len(parts) < 4 or parts[:2] != ["", "p"]:
            raise ValueError
        token = parts[2]
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise ValueError
        decoded = base64.b64decode(token + "=", altchars=b"-_", validate=True)
        if (
            len(decoded) != 32
            or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
        ):
            raise ValueError
        target = file_path("/".join(parts[3:]))
        return PreviewRoute(hashlib.sha256(token.encode()).hexdigest(), target)
    except (ValueError, PreviewError):
        raise PreviewError("RESOURCE_NOT_FOUND") from None


@dataclass(frozen=True, slots=True, kw_only=True)
class PreviewBinding:
    account_id: UUID
    project_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    version_no: int
    representation_id: UUID
    source_hash: str = field(repr=False)
    source_ref: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreviewFile:
    path: str
    media_type: str
    content: bytes = field(repr=False)
    source_sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PreparedPreview:
    manifest: bytes = field(repr=False)
    files: tuple[PreviewFile, ...] = field(repr=False)


def delivery_manifest(
    binding: PreviewBinding, pages: dict[str, str], files: tuple[PreviewFile, ...]
) -> bytes:
    return canonical_json(
        {
            "manifest_version": MANIFEST_VERSION,
            "representation_id": str(binding.representation_id),
            "source": {
                "account_id": str(binding.account_id),
                "project_id": str(binding.project_id),
                "artifact_id": str(binding.artifact_id),
                "artifact_version_id": str(binding.artifact_version_id),
                "version_no": binding.version_no,
                "artifact_hash": binding.source_hash,
            },
            "contracts": {
                "source_manifest_version": "artifact_manifest/v1",
                "generation_ast_schema_version": "generation_ast_schema/v1",
                "transformer_version": TRANSFORMER_VERSION,
                "delivery_policy_version": DELIVERY_POLICY_VERSION,
            },
            "pages": [
                {"canonical_path": k, "file_path": v} for k, v in sorted(pages.items())
            ],
            "files": [
                {
                    "path": f.path,
                    "media_type": f.media_type,
                    "size_bytes": len(f.content),
                    "sha256": digest(f.content),
                    "source_sha256": f.source_sha256,
                }
                for f in sorted(files, key=lambda f: f.path)
            ],
        }
    )


def verified_source_manifest(
    value: bytes, binding: PreviewBinding
) -> dict[str, object]:
    try:
        result = json.loads(value.decode("utf-8"))
        if not isinstance(result, dict) or digest(value) != binding.source_hash:
            raise ValueError
        if set(result) != {
            "manifest_version",
            "artifact",
            "source",
            "contracts",
            "canonical_ast",
            "files",
        }:
            raise ValueError
        if (
            canonical_json(result) != value
            or result.get("manifest_version") != "artifact_manifest/v1"
        ):
            raise ValueError
        if result.get("artifact") != {
            "artifact_id": str(binding.artifact_id),
            "artifact_version_id": str(binding.artifact_version_id),
            "version_no": binding.version_no,
        }:
            raise ValueError
        contracts = result.get("contracts")
        if contracts != {
            "generation_ast_schema": "generation_ast_schema/v1",
            "component_registry": "component_registry/v1",
            "responsive_rules": "responsive_rules/v1",
            "renderer_version": "0.1.0",
            "design_tokens_version": "0.1.0",
        }:
            raise PreviewError("PREVIEW_SOURCE_UNSUPPORTED")
        if not isinstance(result.get("canonical_ast"), dict) or not isinstance(
            result.get("files"), list
        ):
            raise TypeError
        return cast(dict[str, object], result)
    except (ValueError, UnicodeDecodeError, TypeError):
        raise PreviewError("PREVIEW_SOURCE_INVALID") from None


TransformFile = Callable[[str, bytes, dict[str, str], set[str]], bytes]


def prepare_preview(
    binding: PreviewBinding,
    manifest_bytes: bytes,
    source_files: Mapping[str, bytes],
    transform: TransformFile,
) -> PreparedPreview:
    """Verify all source files before transformation; publish neither partial nor invalid output."""
    manifest = verified_source_manifest(manifest_bytes, binding)
    try:
        ast = cast(dict[str, object], manifest["canonical_ast"])
        if ast.get("schema_version") != "generation_ast_schema_v1":
            raise ValueError
        ast_pages = ast.get("pages")
        if not isinstance(ast_pages, list) or not ast_pages:
            raise ValueError
        pages: dict[str, str] = {}
        for page in ast_pages:
            if not isinstance(page, dict) or not isinstance(page.get("path"), str):
                raise TypeError
            path = page["path"]
            if path in pages:
                raise ValueError
            pages[path] = page_file(path)
        rows = cast(list[object], manifest["files"])
        verified: dict[str, dict[str, object]] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "path",
                "media_type",
                "size_bytes",
                "sha256",
            }:
                raise ValueError
            path = row["path"]
            size = row["size_bytes"]
            if (
                not isinstance(path, str)
                or path in verified
                or not isinstance(size, int)
                or isinstance(size, bool)
                or size < 0
            ):
                raise ValueError
            file_path(path)
            value = source_files.get(path)
            if (
                value is None
                or len(value) != size
                or digest(value) != row["sha256"]
                or row["media_type"] != MEDIA_TYPES[posixpath.splitext(path)[1]]
            ):
                raise ValueError
            verified[path] = row
        if set(verified) != set(source_files) or not set(pages.values()) <= set(
            verified
        ):
            raise ValueError
        paths = set(verified)
        files = tuple(
            PreviewFile(
                path,
                cast(str, verified[path]["media_type"]),
                transform(path, source_files[path], pages, paths),
                digest(source_files[path]),
            )
            for path in sorted(verified)
        )
        return PreparedPreview(delivery_manifest(binding, pages, files), files)
    except (KeyError, TypeError, ValueError):
        raise PreviewError("PREVIEW_SOURCE_INVALID") from None


def verified_delivery_manifest(
    value: bytes, *, binding: PreviewBinding, expected_hash: str
) -> dict[str, object]:
    try:
        manifest = json.loads(value.decode("utf-8"))
        if (
            digest(value) != expected_hash
            or not isinstance(manifest, dict)
            or canonical_json(manifest) != value
            or set(manifest)
            != {
                "manifest_version",
                "representation_id",
                "source",
                "contracts",
                "pages",
                "files",
            }
        ):
            raise ValueError
        if (
            manifest["manifest_version"] != MANIFEST_VERSION
            or manifest["representation_id"] != str(binding.representation_id)
            or manifest["source"]
            != {
                "account_id": str(binding.account_id),
                "project_id": str(binding.project_id),
                "artifact_id": str(binding.artifact_id),
                "artifact_version_id": str(binding.artifact_version_id),
                "version_no": binding.version_no,
                "artifact_hash": binding.source_hash,
            }
            or manifest["contracts"]
            != {
                "source_manifest_version": "artifact_manifest/v1",
                "generation_ast_schema_version": "generation_ast_schema/v1",
                "transformer_version": TRANSFORMER_VERSION,
                "delivery_policy_version": DELIVERY_POLICY_VERSION,
            }
        ):
            raise ValueError
        rows, pages = manifest["files"], manifest["pages"]
        if (
            not isinstance(rows, list)
            or not isinstance(pages, list)
            or not rows
            or not pages
        ):
            raise ValueError
        paths: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "path",
                "media_type",
                "size_bytes",
                "sha256",
                "source_sha256",
            }:
                raise ValueError
            path = row["path"]
            if not isinstance(path, str):
                raise TypeError
            file_path(path)
            if (
                row["media_type"] != MEDIA_TYPES[posixpath.splitext(path)[1]]
                or not isinstance(row["size_bytes"], int)
                or isinstance(row["size_bytes"], bool)
                or row["size_bytes"] < 0
            ):
                raise ValueError
            for key in ("sha256", "source_sha256"):
                if not isinstance(row[key], str) or not re.fullmatch(
                    r"sha256:[0-9a-f]{64}", row[key]
                ):
                    raise ValueError
            paths.append(path)
        if paths != sorted(set(paths)):
            raise ValueError
        page_paths: list[str] = []
        for page in pages:
            if (
                not isinstance(page, dict)
                or set(page) != {"canonical_path", "file_path"}
                or not isinstance(page["canonical_path"], str)
                or page_file(page["canonical_path"]) != page["file_path"]
                or page["file_path"] not in paths
            ):
                raise ValueError
            page_paths.append(page["canonical_path"])
        if page_paths != sorted(set(page_paths)):
            raise ValueError
        return cast(dict[str, object], manifest)
    except (KeyError, ValueError, UnicodeDecodeError, TypeError, PreviewError):
        raise PreviewError("PREVIEW_DELIVERY_CONFLICT") from None
