from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_V1,
    COMPLETION_CHECKLIST_VERSION,
    CRITICAL_GAP_RULE_PACK_VERSION,
    CandidateGap,
    CandidateGapBatch,
    ChecklistItemRuleSignal,
    CriticalAssumptionRuleSignal,
    GapContextItem,
    GapCriticalPolicyUnavailableError,
    GapDetectionSnapshot,
    GapRequirement,
    GapRuleSignalError,
    GapSourceReference,
    RequirementConflictRuleSignal,
    VersionedCriticalGapRuleEvaluator,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)


def _snapshot(
    project_type: str = "landing",
    *,
    context_items: tuple[GapContextItem, ...] | None = None,
    requirements: tuple[GapRequirement, ...] = (),
) -> GapDetectionSnapshot:
    if context_items is None:
        context_items = (
            GapContextItem(
                id=UUID(int=1),
                updated_at=NOW,
                item_type="fact",
                status="confirmed",
                content="محتوای پشتیبان",
                source_refs=(),
            ),
        )
    return GapDetectionSnapshot(
        project_type=project_type,
        context_version=1,
        completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
        context_items=context_items,
        requirements=requirements,
    )


def _checklist_signals(
    snapshot: GapDetectionSnapshot,
    *,
    missing_item_id: str | None = None,
    candidate_index: int | None = None,
) -> tuple[ChecklistItemRuleSignal, ...]:
    items = COMPLETION_CHECKLIST_V1.items_for(snapshot.project_type)
    assert items is not None
    support_id = snapshot.context_items[0].id
    return tuple(
        ChecklistItemRuleSignal(
            signal_type="checklist_item",
            signal_origin="ai_candidate",
            checklist_item_id=item.item_id,
            state="missing" if item.item_id == missing_item_id else "present",
            supporting_context_item_ids=(
                () if item.item_id == missing_item_id else (support_id,)
            ),
            candidate_index=(
                candidate_index if item.item_id == missing_item_id else None
            ),
        )
        for item in items
    )


def _evaluate(
    snapshot: GapDetectionSnapshot,
    batch: CandidateGapBatch,
    rule_pack_version: str = CRITICAL_GAP_RULE_PACK_VERSION,
):
    return asyncio.run(
        VersionedCriticalGapRuleEvaluator().evaluate(
            snapshot=snapshot,
            batch=batch,
            rule_pack_version=rule_pack_version,
        )
    )


def test_completion_checklist_v1_is_exactly_the_approved_matrix() -> None:
    expected = {
        "landing": {
            "project.objective": True,
            "project.target_audience": True,
            "landing.primary_cta": True,
            "landing.offer_or_value_proposition": False,
            "landing.required_content_or_sections": False,
        },
        "corporate": {
            "project.objective": True,
            "project.target_audience": False,
            "corporate.services_or_offerings": True,
            "corporate.required_pages": True,
            "corporate.contact_path": False,
        },
        "portfolio": {
            "project.objective": True,
            "project.target_audience": False,
            "portfolio.professional_identity": True,
            "portfolio.work_or_case_study_inventory": True,
            "portfolio.contact_path": False,
        },
    }
    actual = {}
    for project_type in expected:
        items = COMPLETION_CHECKLIST_V1.items_for(project_type)
        assert items is not None
        actual[project_type] = {
            item.item_id: item.critical_if_missing for item in items if item.required
        }
    assert actual == expected


def test_cgr_001_generates_immutable_template_gap_for_missing_critical_item() -> None:
    snapshot = _snapshot()
    result = _evaluate(
        snapshot,
        CandidateGapBatch(
            items=(),
            rule_signals=_checklist_signals(
                snapshot, missing_item_id="landing.primary_cta"
            ),
        ),
    )
    assert result.matched_rule_ids == ("CGR-001",)
    assert result.authoritative_candidate_indexes == ()
    assert len(result.generated_candidates) == 1
    gap = result.generated_candidates[0]
    assert gap.severity == "critical"
    assert gap.gap_type == "missing_information"
    assert gap.explanation == (
        "اطلاعات الزامی «اقدام اصلی کاربر» برای تدوین Scope قابل اتکا موجود نیست."
    )


def test_missing_noncritical_checklist_item_does_not_become_critical() -> None:
    snapshot = _snapshot()
    result = _evaluate(
        snapshot,
        CandidateGapBatch(
            items=(),
            rule_signals=_checklist_signals(
                snapshot, missing_item_id="landing.offer_or_value_proposition"
            ),
        ),
    )
    assert result.matched_rule_ids == ()
    assert result.generated_candidates == ()


def test_rule_signal_cannot_elevate_an_unrelated_candidate() -> None:
    snapshot = _snapshot()
    unrelated = CandidateGap(
        gap_type="scope_risk",
        severity="low",
        explanation="ریسک",
        source_refs=(),
        affected_requirement_ids=(),
        suggested_resolution_type="mitigate_scope_risk",
    )
    with pytest.raises(GapRuleSignalError, match="candidate_type_mismatch"):
        _evaluate(
            snapshot,
            CandidateGapBatch(
                items=(unrelated,),
                rule_signals=_checklist_signals(
                    snapshot,
                    missing_item_id="landing.primary_cta",
                    candidate_index=0,
                ),
            ),
        )


def test_checklist_signal_coverage_and_support_are_snapshot_validated() -> None:
    snapshot = _snapshot()
    with pytest.raises(GapRuleSignalError, match="incomplete_or_duplicate"):
        _evaluate(snapshot, CandidateGapBatch(items=(), rule_signals=()))

    signals = list(_checklist_signals(snapshot))
    signals[0] = ChecklistItemRuleSignal(
        signal_type="checklist_item",
        signal_origin="ai_candidate",
        checklist_item_id=signals[0].checklist_item_id,
        state="present",
        supporting_context_item_ids=(uuid4(),),
    )
    with pytest.raises(GapRuleSignalError, match="checklist_support_outside_snapshot"):
        _evaluate(snapshot, CandidateGapBatch(items=(), rule_signals=tuple(signals)))


def test_requirement_conflict_requires_two_distinct_snapshot_requirements() -> None:
    with pytest.raises(GapRuleSignalError, match="distinct_pair"):
        RequirementConflictRuleSignal(
            signal_type="requirement_conflict",
            signal_origin="ai_candidate",
            requirement_ids=(UUID(int=1),),
        )


def test_cgr_002_only_matches_conflict_with_key_requirement() -> None:
    requirements = tuple(
        GapRequirement(
            id=UUID(int=value),
            updated_at=NOW,
            category="functional",
            title=f"نیازمندی {value}",
            description="شرح",
            priority=priority,
            status="confirmed",
            source_refs=(),
        )
        for value, priority in ((10, "must"), (11, "should"))
    )
    snapshot = _snapshot(requirements=requirements)
    conflict = RequirementConflictRuleSignal(
        signal_type="requirement_conflict",
        signal_origin="ai_candidate",
        requirement_ids=tuple(item.id for item in requirements),
    )
    result = _evaluate(
        snapshot,
        CandidateGapBatch(
            items=(), rule_signals=(*_checklist_signals(snapshot), conflict)
        ),
    )
    assert result.matched_rule_ids == ("CGR-002",)
    assert result.generated_candidates[0].affected_requirement_ids == (
        UUID(int=10),
        UUID(int=11),
    )


@pytest.mark.parametrize("risk_domain", ["payment", "security", "external_integration"])
def test_cgr_003_generates_gap_for_each_approved_sensitive_domain(
    risk_domain: str,
) -> None:
    assumption = GapContextItem(
        id=UUID(int=20),
        updated_at=NOW,
        item_type="assumption",
        status="proposed",
        content="فرض آزمایشی",
        source_refs=(GapSourceReference(UUID(int=30), UUID(int=31)),),
    )
    support = GapContextItem(
        id=UUID(int=1),
        updated_at=NOW,
        item_type="fact",
        status="confirmed",
        content="پشتیبان",
        source_refs=(),
    )
    snapshot = _snapshot(context_items=(support, assumption))
    signal = CriticalAssumptionRuleSignal(
        signal_type="critical_assumption",
        signal_origin="ai_candidate",
        context_item_id=assumption.id,
        risk_domain=risk_domain,  # type: ignore[arg-type]
    )
    result = _evaluate(
        snapshot,
        CandidateGapBatch(
            items=(), rule_signals=(*_checklist_signals(snapshot), signal)
        ),
    )
    assert result.matched_rule_ids == ("CGR-003",)
    assert result.generated_candidates[0].source_refs == assumption.source_refs


def test_confirmed_or_non_assumption_subject_cannot_claim_cgr_003() -> None:
    snapshot = _snapshot()
    signal = CriticalAssumptionRuleSignal(
        signal_type="critical_assumption",
        signal_origin="ai_candidate",
        context_item_id=snapshot.context_items[0].id,
        risk_domain="security",
    )
    with pytest.raises(GapRuleSignalError, match="invalid_critical_assumption_subject"):
        _evaluate(
            snapshot,
            CandidateGapBatch(
                items=(), rule_signals=(*_checklist_signals(snapshot), signal)
            ),
        )


def test_unknown_checklist_or_rule_pack_fails_closed_without_default() -> None:
    snapshot = _snapshot()
    batch = CandidateGapBatch(
        items=(), rule_signals=_checklist_signals(snapshot)
    )
    with pytest.raises(GapCriticalPolicyUnavailableError) as raised:
        _evaluate(snapshot, batch, "unknown-rules")
    assert raised.value.code == "GAP_CRITICAL_POLICY_UNAVAILABLE"
    assert raised.value.retryable is False


def test_rule_match_order_is_stable_and_preserves_all_matches() -> None:
    assumption = GapContextItem(
        id=UUID(int=20),
        updated_at=NOW,
        item_type="assumption",
        status="proposed",
        content="فرض",
        source_refs=(),
    )
    support = GapContextItem(
        id=UUID(int=1),
        updated_at=NOW,
        item_type="fact",
        status="confirmed",
        content="پشتیبان",
        source_refs=(),
    )
    requirements = tuple(
        GapRequirement(
            id=UUID(int=value),
            updated_at=NOW,
            category="functional",
            title="عنوان",
            description="شرح",
            priority=priority,
            status="draft",
            source_refs=(),
        )
        for value, priority in ((10, "must"), (11, "could"))
    )
    snapshot = _snapshot(context_items=(support, assumption), requirements=requirements)
    signals = (
        *_checklist_signals(snapshot, missing_item_id="landing.primary_cta"),
        RequirementConflictRuleSignal(
            signal_type="requirement_conflict",
            signal_origin="ai_candidate",
            requirement_ids=tuple(item.id for item in requirements),
        ),
        CriticalAssumptionRuleSignal(
            signal_type="critical_assumption",
            signal_origin="ai_candidate",
            context_item_id=assumption.id,
            risk_domain="payment",
        ),
    )
    result = _evaluate(snapshot, CandidateGapBatch(items=(), rule_signals=signals))
    assert result.matched_rule_ids == ("CGR-003", "CGR-002", "CGR-001")
    assert len(result.generated_candidates) == 3
