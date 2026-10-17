from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    CandidateContextItem,
    CandidateSourceReference,
    ContextStructuringCommand,
    SourceSnapshot,
)

CONTEXT_STRUCTURING_CHECKPOINT_CODEC = "context_structuring_checkpoint_v1"
AI_INVOCATION_CHECKPOINT_INVALID = "AI_INVOCATION_CHECKPOINT_INVALID"


class ContextStructuringCheckpointCodecError(RuntimeError):
    """A checkpoint cannot be trusted for deterministic AI-01 finalization."""


@dataclass(frozen=True, slots=True)
class CheckpointSourceIdentity:
    source_id: UUID
    source_version_id: UUID
    version_no: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class DecodedContextStructuringCheckpoint:
    input_snapshot: tuple[CheckpointSourceIdentity, ...]
    batch: CandidateContextBatch


def context_structuring_input_fingerprint(
    command: ContextStructuringCommand,
    snapshot: Sequence[SourceSnapshot],
) -> str:
    material = {
        "sources": [_encode_source_identity(source) for source in _ordered(snapshot)],
        "workflow_version": command.workflow_version,
        "prompt_version": command.prompt_version,
        "output_schema_version": command.output_schema_version,
    }
    return _canonical_hash(material)


def encode_context_structuring_checkpoint(
    *,
    snapshot: Sequence[SourceSnapshot],
    batch: CandidateContextBatch,
) -> Mapping[str, object]:
    return {
        "codec": CONTEXT_STRUCTURING_CHECKPOINT_CODEC,
        "input_snapshot": [_encode_source_identity(source) for source in _ordered(snapshot)],
        "items": [
            {
                "item_type": item.item_type,
                "content": item.content,
                "source_refs": [
                    {
                        "source_id": str(reference.source_id),
                        "source_version_id": str(reference.source_version_id),
                        **(
                            {
                                "start_offset": reference.start_offset,
                                "end_offset": reference.end_offset,
                            }
                            if reference.start_offset is not None
                            else {}
                        ),
                    }
                    for reference in item.source_refs
                ],
                "confidence": str(item.confidence) if item.confidence is not None else None,
            }
            for item in batch.items
        ],
    }


def decode_context_structuring_checkpoint(
    payload: Mapping[str, object],
) -> DecodedContextStructuringCheckpoint:
    if set(payload) != {"codec", "input_snapshot", "items"}:
        raise ContextStructuringCheckpointCodecError("checkpoint_shape_invalid")
    if payload["codec"] != CONTEXT_STRUCTURING_CHECKPOINT_CODEC:
        raise ContextStructuringCheckpointCodecError("checkpoint_codec_invalid")
    raw_snapshot = payload["input_snapshot"]
    raw_items = payload["items"]
    if not isinstance(raw_snapshot, list) or not isinstance(raw_items, list):
        raise ContextStructuringCheckpointCodecError("checkpoint_shape_invalid")

    snapshot = tuple(_decode_source_identity(value) for value in raw_snapshot)
    if snapshot != tuple(sorted(snapshot, key=_identity_sort_key)):
        raise ContextStructuringCheckpointCodecError("checkpoint_snapshot_order_invalid")
    if len({identity.source_id for identity in snapshot}) != len(snapshot):
        raise ContextStructuringCheckpointCodecError("checkpoint_snapshot_duplicate")

    items = tuple(_decode_item(value) for value in raw_items)
    return DecodedContextStructuringCheckpoint(
        input_snapshot=snapshot,
        batch=CandidateContextBatch(items=items),
    )


def require_matching_context_snapshot(
    decoded: DecodedContextStructuringCheckpoint,
    snapshot: Sequence[SourceSnapshot],
) -> None:
    expected = tuple(
        CheckpointSourceIdentity(
            source_id=source.source_id,
            source_version_id=source.source_version_id,
            version_no=source.version_no,
            content_hash=_require_content_hash(source.content_hash),
        )
        for source in _ordered(snapshot)
    )
    if decoded.input_snapshot != expected:
        raise ContextStructuringCheckpointCodecError("checkpoint_input_snapshot_mismatch")


def _ordered(snapshot: Sequence[SourceSnapshot]) -> tuple[SourceSnapshot, ...]:
    return tuple(sorted(snapshot, key=lambda source: (source.source_id.hex, source.source_version_id.hex)))


def _encode_source_identity(source: SourceSnapshot) -> dict[str, object]:
    return {
        "source_id": str(source.source_id),
        "source_version_id": str(source.source_version_id),
        "version_no": source.version_no,
        "content_hash": _require_content_hash(source.content_hash),
    }


def _decode_source_identity(value: object) -> CheckpointSourceIdentity:
    if not isinstance(value, dict) or set(value) != {
        "source_id",
        "source_version_id",
        "version_no",
        "content_hash",
    }:
        raise ContextStructuringCheckpointCodecError("checkpoint_source_identity_invalid")
    version_no = value["version_no"]
    if isinstance(version_no, bool) or not isinstance(version_no, int) or version_no < 1:
        raise ContextStructuringCheckpointCodecError("checkpoint_source_identity_invalid")
    try:
        return CheckpointSourceIdentity(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            version_no=version_no,
            content_hash=_require_content_hash(value["content_hash"]),
        )
    except (TypeError, ValueError):
        raise ContextStructuringCheckpointCodecError(
            "checkpoint_source_identity_invalid"
        ) from None


def _decode_item(value: object) -> CandidateContextItem:
    if not isinstance(value, dict) or set(value) != {
        "item_type",
        "content",
        "source_refs",
        "confidence",
    }:
        raise ContextStructuringCheckpointCodecError("checkpoint_item_invalid")
    if not isinstance(value["content"], str) or not isinstance(value["source_refs"], list):
        raise ContextStructuringCheckpointCodecError("checkpoint_item_invalid")
    confidence = value["confidence"]
    if confidence is not None:
        if not isinstance(confidence, str):
            raise ContextStructuringCheckpointCodecError("checkpoint_confidence_invalid")
        try:
            confidence = Decimal(confidence)
        except InvalidOperation:
            raise ContextStructuringCheckpointCodecError(
                "checkpoint_confidence_invalid"
            ) from None
    try:
        return CandidateContextItem(
            item_type=value["item_type"],  # type: ignore[arg-type]
            content=value["content"],
            source_refs=tuple(_decode_source_ref(ref) for ref in value["source_refs"]),
            confidence=confidence,
        )
    except (TypeError, ValueError):
        raise ContextStructuringCheckpointCodecError("checkpoint_item_invalid") from None


def _decode_source_ref(value: object) -> CandidateSourceReference:
    if not isinstance(value, dict):
        raise ContextStructuringCheckpointCodecError("checkpoint_source_ref_invalid")
    expected = {"source_id", "source_version_id"}
    with_offsets = expected | {"start_offset", "end_offset"}
    if set(value) not in (expected, with_offsets):
        raise ContextStructuringCheckpointCodecError("checkpoint_source_ref_invalid")
    try:
        return CandidateSourceReference(
            source_id=UUID(str(value["source_id"])),
            source_version_id=UUID(str(value["source_version_id"])),
            start_offset=value.get("start_offset"),  # type: ignore[arg-type]
            end_offset=value.get("end_offset"),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError):
        raise ContextStructuringCheckpointCodecError(
            "checkpoint_source_ref_invalid"
        ) from None


def _require_content_hash(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ContextStructuringCheckpointCodecError("checkpoint_content_hash_invalid")
    return value


def _identity_sort_key(identity: CheckpointSourceIdentity) -> tuple[str, str]:
    return identity.source_id.hex, identity.source_version_id.hex


def _canonical_hash(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
