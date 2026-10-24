from __future__ import annotations

import hashlib
import io
import json
import posixpath
import tarfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, Protocol, cast
from uuid import UUID, uuid5

from aria_backend_application.generation_ast import (
    enrich_generation_candidate,
    validate_generation_candidate,
)

ARTIFACT_GENERATION_MESSAGE_VERSION = "1"
ARTIFACT_GENERATION_JOB_TYPE = "artifact_generation"
ARTIFACT_GENERATION_EVENT_TYPE = "artifact.generation_requested.v1"
ARTIFACT_GENERATION_TASK_NAME = "aria.artifact.generate.v1"
ARTIFACT_MANIFEST_VERSION = "artifact_manifest/v1"


class ArtifactGenerationError(RuntimeError):
    def __init__(self, reason_code: str, *, retryable: bool = False) -> None:
        self.reason_code = reason_code
        self.retryable = retryable
        super().__init__(reason_code)


class ArtifactGenerationMessageError(ValueError):
    """Identifier-only Queue envelope is invalid."""


@dataclass(frozen=True, slots=True)
class ArtifactGenerationMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    @classmethod
    def from_payload(cls, value: object) -> ArtifactGenerationMessage:
        if not isinstance(value, Mapping) or set(value) != {
            "message_version",
            "outbox_event_id",
            "job_id",
        }:
            raise ArtifactGenerationMessageError("invalid_artifact_generation_message")
        try:
            message = cls(
                message_version=str(value["message_version"]),
                outbox_event_id=UUID(str(value["outbox_event_id"])),
                job_id=UUID(str(value["job_id"])),
            )
        except (TypeError, ValueError):
            raise ArtifactGenerationMessageError(
                "invalid_artifact_generation_message"
            ) from None
        if message.message_version != ARTIFACT_GENERATION_MESSAGE_VERSION:
            raise ArtifactGenerationMessageError("unsupported_artifact_message_version")
        return message


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactGenerationJob:
    job_id: UUID
    account_id: UUID
    project_id: UUID
    correlation_id: UUID
    artifact_id: UUID
    artifact_version_id: UUID
    version_no: int
    scope_version_id: UUID
    scope_version_no: int
    scope_version_hash: str
    project_type: str
    checkpoint_ref: str | None
    checkpoint_hash: str | None
    already_completed: bool = False


@dataclass(frozen=True, slots=True)
class ArtifactBuildFile:
    path: str
    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ArtifactBuild:
    canonical_ast: Mapping[str, object]
    files: tuple[ArtifactBuildFile, ...]


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    sha256: str


class ArtifactGenerationJobStore(Protocol):
    async def prepare(self, message: ArtifactGenerationMessage) -> ArtifactGenerationJob: ...

    async def save_checkpoint(
        self, job: ArtifactGenerationJob, *, checkpoint_ref: str, checkpoint_hash: str
    ) -> None: ...

    async def finalize(
        self, job: ArtifactGenerationJob, *, storage_ref: str, artifact_hash: str
    ) -> Literal["finalized", "already_completed", "stale"]: ...

    async def release(self, message: ArtifactGenerationMessage) -> None: ...


class SyntheticCandidateSource(Protocol):
    async def load(self, *, project_type: str) -> object: ...


class ControlledArtifactBuilderPort(Protocol):
    async def build(self, canonical_ast: Mapping[str, object]) -> tuple[ArtifactBuildFile, ...]: ...


class PrivateArtifactStoragePort(Protocol):
    async def read(self, key: str) -> bytes | None: ...

    async def create_or_verify(self, key: str, content: bytes) -> StoredObject: ...


@dataclass(frozen=True, slots=True)
class ArtifactGenerationResult:
    status: Literal["succeeded", "already_completed"]
    artifact_hash: str | None = None


class ArtifactGenerationRuntime:
    def __init__(
        self,
        *,
        store: ArtifactGenerationJobStore,
        candidate_source: SyntheticCandidateSource,
        builder: ControlledArtifactBuilderPort,
        storage: PrivateArtifactStoragePort,
    ) -> None:
        self._store = store
        self._candidate_source = candidate_source
        self._builder = builder
        self._storage = storage

    async def execute(self, message: ArtifactGenerationMessage) -> ArtifactGenerationResult:
        try:
            job = await self._store.prepare(message)
            if job.already_completed:
                return ArtifactGenerationResult(status="already_completed")
            checkpoint = await self._load_checkpoint(job)
            if checkpoint is None:
                build = await self._build(job)
                manifest_bytes = canonical_manifest_bytes(job, build)
                checkpoint_bytes = checkpoint_bundle_bytes(build.files, manifest_bytes)
                checkpoint_ref = object_prefix(job) + "/checkpoint/build-bundle.tar"
                stored = await self._storage.create_or_verify(
                    checkpoint_ref, checkpoint_bytes
                )
                verified = await self._storage.read(stored.key)
                if verified != checkpoint_bytes:
                    raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
                await self._store.save_checkpoint(
                    job, checkpoint_ref=stored.key, checkpoint_hash=stored.sha256
                )
                checkpoint = (build.files, manifest_bytes)
            files, manifest_bytes = checkpoint
            manifest = parse_manifest(manifest_bytes, job)
            expected_files = cast(list[dict[str, object]], manifest["files"])
            by_path = {item.path: item for item in files}
            for expected in expected_files:
                path = str(expected["path"])
                file = by_path.get(path)
                if file is None:
                    raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID")
                await self._storage.create_or_verify(
                    object_prefix(job) + "/files/" + path, file.content
                )
            manifest_ref = object_prefix(job) + "/manifest.json"
            stored_manifest = await self._storage.create_or_verify(
                manifest_ref, manifest_bytes
            )
            await self._verify_publication(job, manifest_bytes, files)
            outcome = await self._store.finalize(
                job,
                storage_ref=stored_manifest.key,
                artifact_hash=stored_manifest.sha256,
            )
            if outcome == "stale":
                raise ArtifactGenerationError("ARTIFACT_GENERATION_STALE")
            return ArtifactGenerationResult(
                status=(
                    "already_completed"
                    if outcome == "already_completed"
                    else "succeeded"
                ),
                artifact_hash=stored_manifest.sha256,
            )
        finally:
            with suppress(Exception):
                await self._store.release(message)

    async def _build(self, job: ArtifactGenerationJob) -> ArtifactBuild:
        candidate = await self._candidate_source.load(project_type=job.project_type)
        requirement_ids = _candidate_requirement_ids(candidate)
        validated = validate_generation_candidate(
            candidate, pinned_requirement_ids=requirement_ids
        )
        sequence = 0

        def next_id() -> UUID:
            nonlocal sequence
            sequence += 1
            return uuid5(job.artifact_version_id, f"generation-node:{sequence}")

        canonical = enrich_generation_candidate(validated, id_factory=next_id)
        files = await self._builder.build(canonical)
        _validate_files(files)
        return ArtifactBuild(canonical_ast=canonical, files=files)

    async def _load_checkpoint(
        self, job: ArtifactGenerationJob
    ) -> tuple[tuple[ArtifactBuildFile, ...], bytes] | None:
        if job.checkpoint_ref is None and job.checkpoint_hash is None:
            return None
        if job.checkpoint_ref is None or job.checkpoint_hash is None:
            raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
        value = await self._storage.read(job.checkpoint_ref)
        if value is None or digest(value) != job.checkpoint_hash:
            raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
        files, manifest = read_checkpoint_bundle(value)
        parse_manifest(manifest, job)
        return files, manifest

    async def _verify_publication(
        self,
        job: ArtifactGenerationJob,
        manifest_bytes: bytes,
        files: tuple[ArtifactBuildFile, ...],
    ) -> None:
        manifest_ref = object_prefix(job) + "/manifest.json"
        if await self._storage.read(manifest_ref) != manifest_bytes:
            raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID")
        for item in files:
            value = await self._storage.read(object_prefix(job) + "/files/" + item.path)
            if value != item.content:
                raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID")


def canonical_manifest_bytes(job: ArtifactGenerationJob, build: ArtifactBuild) -> bytes:
    manifest = {
        "manifest_version": ARTIFACT_MANIFEST_VERSION,
        "artifact": {
            "artifact_id": str(job.artifact_id),
            "artifact_version_id": str(job.artifact_version_id),
            "version_no": job.version_no,
        },
        "source": {
            "scope_version_id": str(job.scope_version_id),
            "scope_version_no": job.scope_version_no,
            "scope_version_hash": job.scope_version_hash,
        },
        "contracts": {
            "generation_ast_schema": "generation_ast_schema/v1",
            "component_registry": "component_registry/v1",
            "responsive_rules": "responsive_rules/v1",
            "renderer_version": "0.1.0",
            "design_tokens_version": "0.1.0",
        },
        "canonical_ast": build.canonical_ast,
        "files": [
            {
                "path": item.path,
                "media_type": item.media_type,
                "size_bytes": len(item.content),
                "sha256": digest(item.content),
            }
            for item in sorted(build.files, key=lambda value: value.path)
        ],
    }
    return json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def parse_manifest(value: bytes, job: ArtifactGenerationJob) -> dict[str, object]:
    try:
        manifest = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID") from None
    if not isinstance(manifest, dict) or canonical_json(manifest) != value:
        raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID")
    artifact = manifest.get("artifact")
    source = manifest.get("source")
    files = manifest.get("files")
    if (
        manifest.get("manifest_version") != ARTIFACT_MANIFEST_VERSION
        or not isinstance(artifact, dict)
        or artifact.get("artifact_id") != str(job.artifact_id)
        or artifact.get("artifact_version_id") != str(job.artifact_version_id)
        or artifact.get("version_no") != job.version_no
        or not isinstance(source, dict)
        or source.get("scope_version_id") != str(job.scope_version_id)
        or source.get("scope_version_no") != job.scope_version_no
        or source.get("scope_version_hash") != job.scope_version_hash
        or not isinstance(files, list)
    ):
        raise ArtifactGenerationError("ARTIFACT_MANIFEST_INVALID")
    return cast(dict[str, object], manifest)


def checkpoint_bundle_bytes(
    files: tuple[ArtifactBuildFile, ...], manifest: bytes
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        _add_tar_file(archive, "manifest.json", manifest)
        for item in sorted(files, key=lambda value: value.path):
            _add_tar_file(archive, "files/" + item.path, item.content)
    return output.getvalue()


def read_checkpoint_bundle(
    value: bytes,
) -> tuple[tuple[ArtifactBuildFile, ...], bytes]:
    files: list[ArtifactBuildFile] = []
    manifest: bytes | None = None
    try:
        with tarfile.open(fileobj=io.BytesIO(value), mode="r:") as archive:
            for member in archive.getmembers():
                if (
                    not member.isfile()
                    or member.name.startswith("/")
                    or ".." in member.name.split("/")
                ):
                    raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
                content = stream.read()
                if member.name == "manifest.json":
                    manifest = content
                elif member.name.startswith("files/"):
                    path = member.name[6:]
                    files.append(
                        ArtifactBuildFile(path, _media_type(path), content)
                    )
                else:
                    raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
    except (tarfile.TarError, OSError):
        raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID") from None
    if manifest is None:
        raise ArtifactGenerationError("ARTIFACT_CHECKPOINT_INVALID")
    result = tuple(sorted(files, key=lambda item: item.path))
    _validate_files(result)
    return result, manifest


def object_prefix(job: ArtifactGenerationJob) -> str:
    return (
        f"artifacts/{job.account_id}/{job.project_id}/{job.artifact_id}/"
        f"versions/{job.artifact_version_id}"
    )


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _add_tar_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mtime = 0
    info.mode = 0o600
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    archive.addfile(info, io.BytesIO(content))


def _validate_files(files: tuple[ArtifactBuildFile, ...]) -> None:
    if not files:
        raise ArtifactGenerationError("ARTIFACT_BUILD_INVALID")
    seen: set[str] = set()
    for item in files:
        normalized = posixpath.normpath(item.path)
        if (
            not item.path
            or item.path.startswith("/")
            or "\\" in item.path
            or normalized != item.path
            or normalized == ".."
            or normalized.startswith("../")
            or item.path in seen
        ):
            raise ArtifactGenerationError("ARTIFACT_BUILD_INVALID")
        seen.add(item.path)


def _candidate_requirement_ids(value: object) -> frozenset[UUID]:
    if not isinstance(value, Mapping) or not isinstance(value.get("pages"), list):
        return frozenset()
    identifiers: set[UUID] = set()
    for page in value["pages"]:
        if not isinstance(page, Mapping) or not isinstance(page.get("sections"), list):
            continue
        for section in page["sections"]:
            if not isinstance(section, Mapping):
                continue
            refs = section.get("source_requirement_ids")
            if isinstance(refs, list):
                for identifier in refs:
                    with suppress(ValueError):
                        identifiers.add(UUID(str(identifier)))
    return frozenset(identifiers)


def _media_type(path: str) -> str:
    if path.endswith(".html"):
        return "text/html; charset=utf-8"
    if path.endswith(".css"):
        return "text/css; charset=utf-8"
    if path.endswith(".svg"):
        return "image/svg+xml"
    return "application/octet-stream"
