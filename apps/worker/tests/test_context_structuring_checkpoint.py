from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    CandidateContextItem,
    CandidateSourceReference,
    ContextRepairPolicy,
    ContextStructuringCommand,
    SourceSnapshot,
)
from aria_backend_application.context_structuring_checkpoint import (
    ContextStructuringCheckpointCodecError,
    context_structuring_input_fingerprint,
    decode_context_structuring_checkpoint,
    encode_context_structuring_checkpoint,
    require_matching_context_snapshot,
)


def _command() -> ContextStructuringCommand:
    return ContextStructuringCommand(
        account_id=uuid4(),
        project_id=uuid4(),
        job_id=uuid4(),
        correlation_id=uuid4(),
        task_type="context_structuring",
        workflow_version="synthetic-ai-01-v1",
        prompt_version="synthetic-prompt-v1",
        output_schema_version="context-structuring-output-v1",
        repair_prompt_version="unused",
        repair_policy=ContextRepairPolicy(policy_version="no-repair-v1", max_repairs=0),
        pricing_version="synthetic-zero-v1",
        output_schema={"type": "object"},
        routing_policy={"tier": "standard"},
        cost_budget={"paid_calls_allowed": False},
        timeout_policy={"synthetic": True},
    )


def _snapshot() -> tuple[SourceSnapshot, ...]:
    first_id, second_id = uuid4(), uuid4()
    return (
        SourceSnapshot(
            source_id=max(first_id, second_id),
            source_version_id=uuid4(),
            version_no=2,
            canonical_text="متن مصنوعی دوم",
            storage_ref=None,
            content_hash="b" * 64,
        ),
        SourceSnapshot(
            source_id=min(first_id, second_id),
            source_version_id=uuid4(),
            version_no=1,
            canonical_text="متن مصنوعی اول",
            storage_ref=None,
            content_hash="a" * 64,
        ),
    )


def _batch(snapshot: tuple[SourceSnapshot, ...]) -> CandidateContextBatch:
    source = snapshot[0]
    return CandidateContextBatch(
        items=(
            CandidateContextItem(
                item_type="reference",
                content="خروجی مصنوعی کنترل‌شده",
                source_refs=(
                    CandidateSourceReference(
                        source_id=source.source_id,
                        source_version_id=source.source_version_id,
                    ),
                ),
                confidence=Decimal("1.0000"),
                rationale_short="must not be checkpointed",
            ),
        )
    )


def test_codec_is_deterministic_strict_and_excludes_rationale() -> None:
    snapshot = _snapshot()
    payload = encode_context_structuring_checkpoint(
        snapshot=snapshot,
        batch=_batch(snapshot),
    )
    decoded = decode_context_structuring_checkpoint(payload)
    require_matching_context_snapshot(decoded, snapshot)

    assert [item["source_id"] for item in payload["input_snapshot"]] == sorted(  # type: ignore[index]
        item["source_id"] for item in payload["input_snapshot"]  # type: ignore[index]
    )
    assert "rationale_short" not in payload["items"][0]  # type: ignore[index]
    assert decoded.batch.items[0].rationale_short is None


def test_fingerprint_ignores_query_order_but_detects_pinned_input_change() -> None:
    command = _command()
    snapshot = _snapshot()
    assert context_structuring_input_fingerprint(
        command, snapshot
    ) == context_structuring_input_fingerprint(command, tuple(reversed(snapshot)))
    changed = (replace(snapshot[0], content_hash="c" * 64), snapshot[1])
    assert context_structuring_input_fingerprint(
        command, snapshot
    ) != context_structuring_input_fingerprint(command, changed)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: {**payload, "codec": "context_structuring_checkpoint_v2"},
        lambda payload: {**payload, "unexpected": True},
        lambda payload: {
            **payload,
            "input_snapshot": list(reversed(payload["input_snapshot"])),
        },
    ],
)
def test_tampered_codec_shape_or_order_is_rejected(mutation) -> None:
    snapshot = _snapshot()
    payload = encode_context_structuring_checkpoint(
        snapshot=snapshot,
        batch=_batch(snapshot),
    )
    with pytest.raises(ContextStructuringCheckpointCodecError):
        decode_context_structuring_checkpoint(mutation(payload))


def test_snapshot_revalidation_rejects_identity_or_hash_change() -> None:
    snapshot = _snapshot()
    decoded = decode_context_structuring_checkpoint(
        encode_context_structuring_checkpoint(snapshot=snapshot, batch=_batch(snapshot))
    )
    with pytest.raises(
        ContextStructuringCheckpointCodecError,
        match="checkpoint_input_snapshot_mismatch",
    ):
        require_matching_context_snapshot(
            decoded,
            (replace(snapshot[0], content_hash="d" * 64), snapshot[1]),
        )
