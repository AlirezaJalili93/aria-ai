"""Explicit synthetic Preview preparation; never invokes a Renderer or Provider."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, cast
from uuid import UUID

from aria_backend_application.preview_delivery import (
    PreviewBinding,
    PreviewError,
    TransformFile,
    digest,
    file_path,
    prepare_preview,
    verified_delivery_manifest,
    verified_source_manifest,
)

PREVIEW_JOB_TYPE = "preview_publication"
PREVIEW_EVENT_TYPE = "preview.publication_requested.v1"
PREVIEW_TASK_NAME = "aria.preview.publish.v1"
PERMANENT_PREVIEW_FAILURES = frozenset(
    {"PREVIEW_SOURCE_UNSUPPORTED", "PREVIEW_SOURCE_INVALID", "PREVIEW_DELIVERY_CONFLICT"}
)


@dataclass(frozen=True, slots=True)
class PreviewPublicationMessage:
    message_version: str
    outbox_event_id: UUID
    job_id: UUID

    @classmethod
    def from_payload(cls, value: object) -> PreviewPublicationMessage:
        try:
            if (
                not isinstance(value, Mapping)
                or set(value) != {"message_version", "outbox_event_id", "job_id"}
                or value["message_version"] != "1"
            ):
                raise ValueError
            return cls("1", UUID(str(value["outbox_event_id"])), UUID(str(value["job_id"])))
        except (ValueError, TypeError):
            raise PreviewError("VALIDATION_FAILED") from None


@dataclass(frozen=True, slots=True, kw_only=True)
class PreviewPublicationJob:
    job_id: UUID
    publication_id: UUID
    binding: PreviewBinding = field(repr=False)
    already_completed: bool = False


class PreviewPublicationStore(Protocol):
    async def prepare(self, message: PreviewPublicationMessage) -> PreviewPublicationJob: ...

    async def finalize(
        self, job: PreviewPublicationJob, *, manifest_ref: str, manifest_hash: str
    ) -> None: ...

    async def release(self, message: PreviewPublicationMessage) -> None: ...

    async def finalize_failure(self, job: PreviewPublicationJob, *, error_code: str) -> None: ...


class PreviewSourceReader(Protocol):
    async def read(self, key: str) -> bytes | None: ...


class PrivatePreviewStorage(PreviewSourceReader, Protocol):
    async def create_or_verify(self, key: str, value: bytes) -> None: ...


class CanonicalPreviewValidator(Protocol):
    async def validate(self, ast: Mapping[str, object]) -> None: ...


@dataclass(frozen=True, slots=True)
class PreviewPublicationResult:
    status: Literal["succeeded", "already_completed", "failed"]
    error_code: str | None = None


def preview_prefix(binding: PreviewBinding) -> str:
    return (
        f"preview/{binding.account_id}/{binding.project_id}/{binding.artifact_version_id}"
        f"/{binding.representation_id}"
    )


def source_prefix(binding: PreviewBinding) -> str:
    return (
        f"artifacts/{binding.account_id}/{binding.project_id}/{binding.artifact_id}"
        f"/versions/{binding.artifact_version_id}"
    )


class PreviewPublicationRuntime:
    def __init__(
        self,
        *,
        store: PreviewPublicationStore,
        source: PreviewSourceReader,
        destination: PrivatePreviewStorage,
        validator: CanonicalPreviewValidator,
        transform: TransformFile,
        synthetic_sources: frozenset[tuple[UUID, str]],
    ) -> None:
        self._store = store
        self._source = source
        self._destination = destination
        self._validator = validator
        self._transform = transform
        self._synthetic_sources = synthetic_sources

    async def execute(self, message: PreviewPublicationMessage) -> PreviewPublicationResult:
        # Even callers bypassing the queue parser cannot introduce another message version.
        if message.message_version != "1":
            raise PreviewError("VALIDATION_FAILED")
        job: PreviewPublicationJob | None = None
        synthetic_authorized = False
        try:
            job = await self._store.prepare(message)
            binding = job.binding
            if job.job_id != message.job_id:
                raise PreviewError("RESOURCE_NOT_FOUND")
            if (binding.artifact_version_id, binding.source_hash) not in self._synthetic_sources:
                raise PreviewError("FEATURE_NOT_ENABLED")
            synthetic_authorized = True
            if binding.source_ref != source_prefix(binding) + "/manifest.json":
                raise PreviewError("PREVIEW_SOURCE_INVALID")
            if job.already_completed:
                return PreviewPublicationResult("already_completed")
            source = await self._read(self._source, binding.source_ref)
            if source is None:
                raise PreviewError("PREVIEW_SOURCE_INVALID")
            manifest = verified_source_manifest(source, binding)
            try:
                await self._validator.validate(
                    cast(Mapping[str, object], manifest["canonical_ast"])
                )
            except Exception:
                raise PreviewError("PREVIEW_SOURCE_INVALID") from None
            # Reject invalid names/duplicates before using any source path as a storage key.
            paths: set[str] = set()
            for row in cast(list[object], manifest["files"]):
                if not isinstance(row, dict) or not isinstance(row.get("path"), str):
                    raise PreviewError("PREVIEW_SOURCE_INVALID")
                path = file_path(row["path"])
                if path in paths:
                    raise PreviewError("PREVIEW_SOURCE_INVALID")
                paths.add(path)
            files: dict[str, bytes] = {}
            for path in sorted(paths):
                content = await self._read(self._source, source_prefix(binding) + "/files/" + path)
                if content is None:
                    raise PreviewError("PREVIEW_SOURCE_INVALID")
                files[path] = content
            prepared = prepare_preview(binding, source, files, self._transform)
            prefix = preview_prefix(binding)
            for item in prepared.files:
                await self._copy_verified(prefix + "/files/" + item.path, item.content)
            ref, manifest_hash = prefix + "/delivery-manifest.json", digest(prepared.manifest)
            verified_delivery_manifest(
                prepared.manifest, binding=binding, expected_hash=manifest_hash
            )
            await self._copy_verified(ref, prepared.manifest)
            try:
                await self._store.finalize(job, manifest_ref=ref, manifest_hash=manifest_hash)
            except PreviewError:
                raise
            except Exception:
                raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None
            return PreviewPublicationResult("succeeded")
        except PreviewError as exc:
            if (
                job is not None
                and synthetic_authorized
                and not job.already_completed
                and exc.code in PERMANENT_PREVIEW_FAILURES
                and not exc.retryable
            ):
                try:
                    await self._store.finalize_failure(job, error_code=exc.code)
                except PreviewError:
                    raise
                except Exception:
                    raise PreviewError("PREVIEW_FINALIZATION_RECOVERABLE", retryable=True) from None
                return PreviewPublicationResult("failed", exc.code)
            raise
        finally:
            # The store owns cleanup of its physical session/advisory lock, including cancellation.
            await self._store.release(message)

    async def _copy_verified(self, key: str, value: bytes) -> None:
        try:
            await self._destination.create_or_verify(key, value)
        except PreviewError:
            raise
        except Exception:
            raise PreviewError("PREVIEW_STORAGE_ERROR", retryable=True) from None
        if await self._read(self._destination, key) != value:
            raise PreviewError("PREVIEW_DELIVERY_CONFLICT")

    @staticmethod
    async def _read(storage: PreviewSourceReader, key: str) -> bytes | None:
        try:
            return await storage.read(key)
        except PreviewError:
            raise
        except Exception:
            raise PreviewError("PREVIEW_STORAGE_ERROR", retryable=True) from None
