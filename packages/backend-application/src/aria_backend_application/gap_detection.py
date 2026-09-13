from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from types import TracebackType
from typing import Literal, Protocol, Self
from uuid import UUID, uuid4

from aria_observability import emit_product_analytics  # type: ignore[attr-defined]

from aria_backend_application.ai_execution import AIExecutionPort, StructuredAIResponse
from aria_backend_application.usage_ledger import UsageLedger, UsageRecord

GapType = Literal[
    "missing_information",
    "ambiguity",
    "conflict",
    "decision_required",
    "unsupported_assumption",
    "scope_risk",
]
GapSeverity = Literal["critical", "high", "medium", "low"]
SuggestedResolutionType = Literal[
    "provide_information",
    "clarify_ambiguity",
    "resolve_conflict",
    "make_decision",
    "validate_assumption",
    "mitigate_scope_risk",
]
ContextItemStatus = Literal["proposed", "confirmed"]
RequirementStatus = Literal["draft", "confirmed"]
RuleSignalOrigin = Literal["ai_candidate"]
ChecklistSignalState = Literal["present", "missing"]
CriticalRiskDomain = Literal["payment", "security", "external_integration"]

GAP_TYPES = frozenset(
    {
        "missing_information",
        "ambiguity",
        "conflict",
        "decision_required",
        "unsupported_assumption",
        "scope_risk",
    }
)
GAP_SEVERITIES = frozenset({"critical", "high", "medium", "low"})
SUGGESTED_RESOLUTION_TYPES = frozenset(
    {
        "provide_information",
        "clarify_ambiguity",
        "resolve_conflict",
        "make_decision",
        "validate_assumption",
        "mitigate_scope_risk",
    }
)
ELIGIBLE_CONTEXT_STATUSES = frozenset({"proposed", "confirmed"})
ELIGIBLE_REQUIREMENT_STATUSES = frozenset({"draft", "confirmed"})
CRITICAL_RISK_DOMAINS = frozenset({"payment", "security", "external_integration"})
COMPLETION_CHECKLIST_VERSION = "completion_checklist_v1"
CRITICAL_GAP_RULE_PACK_VERSION = "critical_gap_rule_pack_v1"


class GapDetectionError(RuntimeError):
    """A safe provider-neutral Gap detection failure."""

    retryable = False

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class GapDetectionSchemaError(GapDetectionError):
    """Provider output does not satisfy the accepted J02-A schema."""


class GapDetectionProvenanceError(GapDetectionError):
    """A candidate reference is outside the exact input snapshot."""


class GapAffectedRequirementError(GapDetectionError):
    """A candidate points outside the exact active Requirement snapshot."""


class GapDuplicateError(GapDetectionError):
    code = "DUPLICATE_GAP"

    def __init__(self) -> None:
        super().__init__("duplicate_gap")


class GapSnapshotChangedError(GapDetectionError):
    code = "GAP_SNAPSHOT_CHANGED"

    def __init__(self) -> None:
        super().__init__("gap_snapshot_changed")


class GapRepairExhaustedError(GapDetectionError):
    code = "GAP_REPAIR_EXHAUSTED"

    def __init__(self) -> None:
        super().__init__("gap_repair_exhausted")


class GapDetectionRepositoryError(GapDetectionError):
    """A declared Gap detection persistence failure."""


class GapCriticalPolicyUnavailableError(GapDetectionError):
    code = "GAP_CRITICAL_POLICY_UNAVAILABLE"

    def __init__(self) -> None:
        super().__init__("gap_critical_policy_unavailable")


class GapRuleSignalError(GapDetectionSchemaError):
    """Untrusted structured AI rule evidence failed validation."""


@dataclass(frozen=True, slots=True)
class GapSourceReference:
    source_id: UUID
    source_version_id: UUID
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        absent = self.start_offset is None and self.end_offset is None
        present = self.start_offset is not None and self.end_offset is not None
        if not absent and not present:
            raise GapDetectionSchemaError("invalid_source_reference_shape")
        if present:
            assert self.start_offset is not None and self.end_offset is not None
            if (
                isinstance(self.start_offset, bool)
                or isinstance(self.end_offset, bool)
                or not isinstance(self.start_offset, int)
                or not isinstance(self.end_offset, int)
                or self.start_offset < 0
                or self.start_offset >= self.end_offset
            ):
                raise GapDetectionSchemaError("invalid_source_reference_offsets")

    def identity(self) -> tuple[UUID, UUID, int | None, int | None]:
        return (
            self.source_id,
            self.source_version_id,
            self.start_offset,
            self.end_offset,
        )


@dataclass(frozen=True, slots=True)
class ContextItemRevision:
    context_item_id: UUID
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Context Item revision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RequirementRevision:
    requirement_id: UUID
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Requirement revision timestamp must be timezone-aware")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapContextItem:
    id: UUID
    updated_at: datetime
    item_type: str
    status: ContextItemStatus
    content: str
    source_refs: tuple[GapSourceReference, ...]

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Context Item updated_at must be timezone-aware")
        if self.status not in ELIGIBLE_CONTEXT_STATUSES:
            raise ValueError("Context Item is outside the Gap snapshot predicate")

    @property
    def revision(self) -> ContextItemRevision:
        return ContextItemRevision(self.id, self.updated_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class GapRequirement:
    id: UUID
    updated_at: datetime
    category: str
    title: str
    description: str
    priority: str
    status: RequirementStatus
    source_refs: tuple[GapSourceReference, ...]

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("Requirement updated_at must be timezone-aware")
        if self.status not in ELIGIBLE_REQUIREMENT_STATUSES:
            raise ValueError("Requirement is outside the Gap snapshot predicate")

    @property
    def revision(self) -> RequirementRevision:
        return RequirementRevision(self.id, self.updated_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class GapDetectionSnapshot:
    project_type: str
    context_version: int
    completion_checklist_version: str
    context_items: tuple[GapContextItem, ...]
    requirements: tuple[GapRequirement, ...]

    @property
    def context_item_revisions(self) -> tuple[ContextItemRevision, ...]:
        return tuple(
            sorted(
                (item.revision for item in self.context_items),
                key=lambda value: value.context_item_id.int,
            )
        )

    @property
    def requirement_revisions(self) -> tuple[RequirementRevision, ...]:
        return tuple(
            sorted(
                (item.revision for item in self.requirements),
                key=lambda value: value.requirement_id.int,
            )
        )


@dataclass(frozen=True, slots=True)
class GapSnapshotRevisions:
    project_type: str
    context_item_revisions: tuple[ContextItemRevision, ...]
    requirement_revisions: tuple[RequirementRevision, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateGap:
    gap_type: GapType
    severity: GapSeverity
    explanation: str
    source_refs: tuple[GapSourceReference, ...]
    affected_requirement_ids: tuple[UUID, ...]
    suggested_resolution_type: SuggestedResolutionType

    def __post_init__(self) -> None:
        if self.gap_type not in GAP_TYPES:
            raise GapDetectionSchemaError("invalid_gap_type")
        if self.severity not in GAP_SEVERITIES:
            raise GapDetectionSchemaError("invalid_gap_severity")
        if not isinstance(self.explanation, str):
            raise GapDetectionSchemaError("invalid_gap_explanation")
        if self.suggested_resolution_type not in SUGGESTED_RESOLUTION_TYPES:
            raise GapDetectionSchemaError("invalid_suggested_resolution_type")
        if not isinstance(self.source_refs, tuple) or not all(
            isinstance(reference, GapSourceReference) for reference in self.source_refs
        ):
            raise GapDetectionSchemaError("invalid_gap_source_refs")
        if not isinstance(self.affected_requirement_ids, tuple) or not all(
            isinstance(requirement_id, UUID)
            for requirement_id in self.affected_requirement_ids
        ):
            raise GapDetectionSchemaError("invalid_affected_requirement_ids")

    @property
    def exact_identity(self) -> tuple[object, ...]:
        return (
            self.gap_type,
            self.severity,
            self.explanation,
            self.suggested_resolution_type,
            tuple(sorted(reference.identity() for reference in self.source_refs)),
            tuple(sorted(self.affected_requirement_ids, key=lambda value: value.int)),
        )


def _validate_candidate_index(candidate_index: int | None) -> None:
    if candidate_index is not None and (
        isinstance(candidate_index, bool)
        or not isinstance(candidate_index, int)
        or candidate_index < 0
    ):
        raise GapRuleSignalError("invalid_rule_signal_candidate_index")


@dataclass(frozen=True, slots=True, kw_only=True)
class ChecklistItemRuleSignal:
    signal_type: Literal["checklist_item"]
    signal_origin: RuleSignalOrigin
    checklist_item_id: str
    state: ChecklistSignalState
    supporting_context_item_ids: tuple[UUID, ...]
    candidate_index: int | None = None

    def __post_init__(self) -> None:
        if self.signal_type != "checklist_item":
            raise GapRuleSignalError("invalid_rule_signal_type")
        if self.signal_origin != "ai_candidate":
            raise GapRuleSignalError("invalid_rule_signal_origin")
        if not self.checklist_item_id:
            raise GapRuleSignalError("invalid_checklist_item_id")
        if self.state not in {"present", "missing"}:
            raise GapRuleSignalError("invalid_checklist_signal_state")
        if len(set(self.supporting_context_item_ids)) != len(
            self.supporting_context_item_ids
        ):
            raise GapRuleSignalError("duplicate_supporting_context_item")
        if self.state == "present" and not self.supporting_context_item_ids:
            raise GapRuleSignalError("present_checklist_item_without_support")
        if self.state == "missing" and self.supporting_context_item_ids:
            raise GapRuleSignalError("missing_checklist_item_with_support")
        _validate_candidate_index(self.candidate_index)


@dataclass(frozen=True, slots=True, kw_only=True)
class RequirementConflictRuleSignal:
    signal_type: Literal["requirement_conflict"]
    signal_origin: RuleSignalOrigin
    requirement_ids: tuple[UUID, ...]
    candidate_index: int | None = None

    def __post_init__(self) -> None:
        if self.signal_type != "requirement_conflict":
            raise GapRuleSignalError("invalid_rule_signal_type")
        if self.signal_origin != "ai_candidate":
            raise GapRuleSignalError("invalid_rule_signal_origin")
        if len(self.requirement_ids) < 2 or len(set(self.requirement_ids)) != len(
            self.requirement_ids
        ):
            raise GapRuleSignalError("requirement_conflict_requires_distinct_pair")
        _validate_candidate_index(self.candidate_index)


@dataclass(frozen=True, slots=True, kw_only=True)
class CriticalAssumptionRuleSignal:
    signal_type: Literal["critical_assumption"]
    signal_origin: RuleSignalOrigin
    context_item_id: UUID
    risk_domain: CriticalRiskDomain
    candidate_index: int | None = None

    def __post_init__(self) -> None:
        if self.signal_type != "critical_assumption":
            raise GapRuleSignalError("invalid_rule_signal_type")
        if self.signal_origin != "ai_candidate":
            raise GapRuleSignalError("invalid_rule_signal_origin")
        if self.risk_domain not in CRITICAL_RISK_DOMAINS:
            raise GapRuleSignalError("invalid_critical_assumption_risk_domain")
        _validate_candidate_index(self.candidate_index)


RuleSignal = (
    ChecklistItemRuleSignal
    | RequirementConflictRuleSignal
    | CriticalAssumptionRuleSignal
)


@dataclass(frozen=True, slots=True)
class CandidateGapBatch:
    items: tuple[CandidateGap, ...]
    rule_signals: tuple[RuleSignal, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple) or not all(
            isinstance(item, CandidateGap) for item in self.items
        ):
            raise GapDetectionSchemaError("invalid_gap_candidate_batch")
        if not isinstance(self.rule_signals, tuple) or not all(
            isinstance(
                signal,
                (
                    ChecklistItemRuleSignal,
                    RequirementConflictRuleSignal,
                    CriticalAssumptionRuleSignal,
                ),
            )
            for signal in self.rule_signals
        ):
            raise GapRuleSignalError("invalid_rule_signal_batch")


@dataclass(frozen=True, slots=True)
class CompletionChecklistItem:
    item_id: str
    label: str
    required: bool
    critical_if_missing: bool


@dataclass(frozen=True, slots=True)
class CompletionChecklist:
    version: str
    common_items: tuple[CompletionChecklistItem, ...]
    project_items: tuple[tuple[str, tuple[CompletionChecklistItem, ...]], ...]

    def items_for(self, project_type: str) -> tuple[CompletionChecklistItem, ...] | None:
        for configured_type, items in self.project_items:
            if configured_type == project_type:
                return self.common_items + items
        return None


COMPLETION_CHECKLIST_V1 = CompletionChecklist(
    version=COMPLETION_CHECKLIST_VERSION,
    common_items=(
        CompletionChecklistItem(
            "project.objective", "هدف پروژه", required=True, critical_if_missing=True
        ),
    ),
    project_items=(
        (
            "landing",
            (
                CompletionChecklistItem(
                    "project.target_audience",
                    "مخاطب هدف",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "landing.primary_cta",
                    "اقدام اصلی کاربر",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "landing.offer_or_value_proposition",
                    "پیشنهاد ارزش",
                    required=True,
                    critical_if_missing=False,
                ),
                CompletionChecklistItem(
                    "landing.required_content_or_sections",
                    "محتوا یا بخش‌های ضروری",
                    required=True,
                    critical_if_missing=False,
                ),
            ),
        ),
        (
            "corporate",
            (
                CompletionChecklistItem(
                    "project.target_audience",
                    "مخاطب هدف",
                    required=True,
                    critical_if_missing=False,
                ),
                CompletionChecklistItem(
                    "corporate.services_or_offerings",
                    "خدمات یا پیشنهادهای کسب‌وکار",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "corporate.required_pages",
                    "صفحات ضروری",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "corporate.contact_path",
                    "مسیر تماس",
                    required=True,
                    critical_if_missing=False,
                ),
            ),
        ),
        (
            "portfolio",
            (
                CompletionChecklistItem(
                    "project.target_audience",
                    "مخاطب هدف",
                    required=True,
                    critical_if_missing=False,
                ),
                CompletionChecklistItem(
                    "portfolio.professional_identity",
                    "هویت حرفه‌ای",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "portfolio.work_or_case_study_inventory",
                    "نمونه‌کارها یا مطالعات موردی",
                    required=True,
                    critical_if_missing=True,
                ),
                CompletionChecklistItem(
                    "portfolio.contact_path",
                    "مسیر تماس",
                    required=True,
                    critical_if_missing=False,
                ),
            ),
        ),
    ),
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GapRepairPolicy:
    policy_version: str
    max_repairs: int

    def __post_init__(self) -> None:
        if not isinstance(self.policy_version, str) or not self.policy_version:
            raise ValueError("Gap repair policy version is required")
        if isinstance(self.max_repairs, bool) or self.max_repairs not in (0, 1):
            raise ValueError("Sprint 1 Gap repair permits max_repairs 0 or 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class DetectGapsCommand:
    account_id: UUID
    project_id: UUID
    job_id: UUID
    correlation_id: UUID
    context_version: int
    context_item_revisions: tuple[ContextItemRevision, ...]
    requirement_revisions: tuple[RequirementRevision, ...]
    completion_checklist_version: str
    critical_rule_pack_version: str
    task_type: str
    workflow_version: str
    prompt_version: str
    repair_prompt_version: str
    repair_policy: GapRepairPolicy
    pricing_version: str
    output_schema: Mapping[str, object]
    routing_policy: Mapping[str, object]
    cost_budget: Mapping[str, object]
    timeout_policy: Mapping[str, object]

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or self.context_version < 1:
            raise ValueError("context_version must be at least one")
        if not self.completion_checklist_version:
            raise ValueError("completion_checklist_version is required")
        if not self.critical_rule_pack_version:
            raise ValueError("critical_rule_pack_version is required")
        _assert_sorted_unique_context_revisions(self.context_item_revisions)
        _assert_sorted_unique_requirement_revisions(self.requirement_revisions)


@dataclass(frozen=True, slots=True)
class CriticalGapRuleEvaluation:
    authoritative_candidate_indexes: tuple[int, ...]
    generated_candidates: tuple[CandidateGap, ...] = ()
    matched_rule_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if len(set(self.authoritative_candidate_indexes)) != len(
            self.authoritative_candidate_indexes
        ) or any(
            isinstance(index, bool) or not isinstance(index, int) or index < 0
            for index in self.authoritative_candidate_indexes
        ):
            raise ValueError(
                "Critical candidate indexes must be unique non-negative integers"
            )
        if any(candidate.severity != "critical" for candidate in self.generated_candidates):
            raise ValueError("Rule-generated Gap candidates must be critical")
        if len(set(self.matched_rule_ids)) != len(self.matched_rule_ids):
            raise ValueError("Matched rule IDs must be unique")


class CriticalGapRuleEvaluator(Protocol):
    async def evaluate(
        self,
        *,
        snapshot: GapDetectionSnapshot,
        batch: CandidateGapBatch,
        rule_pack_version: str,
    ) -> CriticalGapRuleEvaluation: ...


class VersionedCriticalGapRuleEvaluator:
    """J02-B rules over validated, untrusted structured AI signals."""

    async def evaluate(
        self,
        *,
        snapshot: GapDetectionSnapshot,
        batch: CandidateGapBatch,
        rule_pack_version: str,
    ) -> CriticalGapRuleEvaluation:
        if (
            snapshot.completion_checklist_version != COMPLETION_CHECKLIST_VERSION
            or rule_pack_version != CRITICAL_GAP_RULE_PACK_VERSION
        ):
            raise GapCriticalPolicyUnavailableError
        checklist_items = COMPLETION_CHECKLIST_V1.items_for(snapshot.project_type)
        if checklist_items is None:
            raise GapCriticalPolicyUnavailableError

        candidate_indexes: set[int] = set()
        generated: list[CandidateGap] = []
        matched: set[str] = set()
        context_by_id = {item.id: item for item in snapshot.context_items}
        requirements_by_id = {item.id: item for item in snapshot.requirements}
        checklist_by_id = {item.item_id: item for item in checklist_items}

        checklist_signals = tuple(
            signal
            for signal in batch.rule_signals
            if isinstance(signal, ChecklistItemRuleSignal)
        )
        signal_ids = tuple(signal.checklist_item_id for signal in checklist_signals)
        if len(set(signal_ids)) != len(signal_ids) or set(signal_ids) != set(
            checklist_by_id
        ):
            raise GapRuleSignalError("incomplete_or_duplicate_checklist_signals")

        processing_order = {
            CriticalAssumptionRuleSignal: 0,
            RequirementConflictRuleSignal: 1,
            ChecklistItemRuleSignal: 2,
        }
        ordered_signals = tuple(
            sorted(batch.rule_signals, key=lambda value: processing_order[type(value)])
        )
        for signal in ordered_signals:
            _validate_rule_signal_candidate_index(signal, batch)
            if isinstance(signal, ChecklistItemRuleSignal):
                if any(
                    item_id not in context_by_id
                    for item_id in signal.supporting_context_item_ids
                ):
                    raise GapRuleSignalError("checklist_support_outside_snapshot")
                item = checklist_by_id[signal.checklist_item_id]
                if signal.state == "missing" and item.required and item.critical_if_missing:
                    _validate_linked_candidate(
                        signal.candidate_index,
                        batch,
                        expected_gap_type="missing_information",
                    )
                    matched.add("CGR-001")
                    if signal.candidate_index is None:
                        generated.append(
                            CandidateGap(
                                gap_type="missing_information",
                                severity="critical",
                                explanation=(
                                    f'اطلاعات الزامی «{item.label}» برای تدوین Scope '
                                    "قابل اتکا موجود نیست."
                                ),
                                source_refs=(),
                                affected_requirement_ids=(),
                                suggested_resolution_type="provide_information",
                            )
                        )
                    else:
                        candidate_indexes.add(signal.candidate_index)
            elif isinstance(signal, RequirementConflictRuleSignal):
                if any(value not in requirements_by_id for value in signal.requirement_ids):
                    raise GapRuleSignalError("conflict_requirement_outside_snapshot")
                if any(
                    requirements_by_id[value].status in ELIGIBLE_REQUIREMENT_STATUSES
                    and requirements_by_id[value].priority == "must"
                    for value in signal.requirement_ids
                ):
                    _validate_linked_candidate(
                        signal.candidate_index,
                        batch,
                        expected_gap_type="conflict",
                        expected_requirement_ids=frozenset(signal.requirement_ids),
                    )
                    matched.add("CGR-002")
                    if signal.candidate_index is None:
                        refs = _canonical_reference_union(
                            reference
                            for requirement_id in signal.requirement_ids
                            for reference in requirements_by_id[requirement_id].source_refs
                        )
                        generated.append(
                            CandidateGap(
                                gap_type="conflict",
                                severity="critical",
                                explanation=(
                                    "بین Requirementهای کلیدی پروژه تعارض حل‌نشده وجود دارد."
                                ),
                                source_refs=refs,
                                affected_requirement_ids=tuple(
                                    sorted(signal.requirement_ids, key=lambda value: value.int)
                                ),
                                suggested_resolution_type="resolve_conflict",
                            )
                        )
                    else:
                        candidate_indexes.add(signal.candidate_index)
            else:
                context_item = context_by_id.get(signal.context_item_id)
                if (
                    context_item is None
                    or context_item.item_type != "assumption"
                    or context_item.status == "confirmed"
                ):
                    raise GapRuleSignalError("invalid_critical_assumption_subject")
                matched.add("CGR-003")
                _validate_linked_candidate(
                    signal.candidate_index,
                    batch,
                    expected_gap_type="unsupported_assumption",
                )
                if signal.candidate_index is None:
                    generated.append(
                        CandidateGap(
                            gap_type="unsupported_assumption",
                            severity="critical",
                            explanation=(
                                "یک فرض تأییدنشده در حوزه حساس پروژه نیازمند تعیین تکلیف است."
                            ),
                            source_refs=context_item.source_refs,
                            affected_requirement_ids=(),
                            suggested_resolution_type="validate_assumption",
                        )
                    )
                else:
                    candidate_indexes.add(signal.candidate_index)

        precedence = ("CGR-003", "CGR-002", "CGR-001")
        return CriticalGapRuleEvaluation(
            authoritative_candidate_indexes=tuple(sorted(candidate_indexes)),
            generated_candidates=tuple(generated),
            matched_rule_ids=tuple(rule_id for rule_id in precedence if rule_id in matched),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class GapWrite:
    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    gap_type: GapType
    severity: GapSeverity
    explanation: str
    source_refs: tuple[GapSourceReference, ...]
    suggested_resolution_type: SuggestedResolutionType
    generation_job_id: UUID
    affected_requirement_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class GapDetectionResult:
    gap_ids: tuple[UUID, ...]
    gap_count: int
    critical_candidate_count: int
    authoritative_critical_gap_ids: tuple[UUID, ...]
    rule_generated_gap_count: int = 0
    critical_gap_count: int = 0
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class GapDetectionReplay:
    status: Literal["succeeded", "failed"]
    gap_ids: tuple[UUID, ...]
    gap_count: int | None
    critical_candidate_count: int | None
    error_code: str | None
    rule_generated_gap_count: int | None = None
    critical_gap_count: int | None = None
    completion_checklist_version: str | None = None
    critical_rule_pack_version: str | None = None


class GapDetectionSnapshotReader(Protocol):
    async def resolve_exact(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        completion_checklist_version: str,
    ) -> GapDetectionSnapshot | None: ...


class GapDetectionRepository(Protocol):
    async def resolve_replay(
        self, *, account_id: UUID, project_id: UUID, generation_job_id: UUID
    ) -> GapDetectionReplay | None: ...

    async def lock_snapshot_and_resolve_revisions(
        self, *, account_id: UUID, project_id: UUID, context_version: int
    ) -> GapSnapshotRevisions | None: ...

    async def add_batch(self, gaps: tuple[GapWrite, ...]) -> None: ...

    async def mark_job_succeeded(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        job_id: UUID,
        gap_count: int,
        critical_candidate_count: int,
        rule_generated_gap_count: int,
        critical_gap_count: int,
        completion_checklist_version: str,
        critical_rule_pack_version: str,
        finished_at: datetime,
    ) -> None: ...


class GapDetectionUnitOfWork(Protocol):
    @property
    def repository(self) -> GapDetectionRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class GapDetectionUnitOfWorkFactory(Protocol):
    def __call__(self) -> GapDetectionUnitOfWork: ...


class GapDetectionEventLogger(Protocol):
    def emit(
        self, event_name: str, *, level: str = "INFO", **fields: object
    ) -> None: ...


class DetectGapsUseCase:
    def __init__(
        self,
        *,
        snapshot_reader: GapDetectionSnapshotReader,
        ai_execution: AIExecutionPort,
        usage_ledger: UsageLedger,
        critical_rule_evaluator: CriticalGapRuleEvaluator,
        unit_of_work_factory: GapDetectionUnitOfWorkFactory,
        event_logger: GapDetectionEventLogger,
        id_factory: Callable[[], UUID] = uuid4,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._ai_execution = ai_execution
        self._usage_ledger = usage_ledger
        self._critical_rule_evaluator = critical_rule_evaluator
        self._unit_of_work_factory = unit_of_work_factory
        self._event_logger = event_logger
        self._id_factory = id_factory
        self._wall_clock = wall_clock
        self._clock = monotonic_clock

    async def execute(self, command: DetectGapsCommand) -> GapDetectionResult:
        started_at = self._clock()
        self._event_logger.emit(
            "gap.detection_started",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            completion_checklist_version=command.completion_checklist_version,
            critical_rule_pack_version=command.critical_rule_pack_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            status="started",
        )
        try:
            replay = await self._resolve_replay(command)
            if replay is not None:
                result = self._replay_result(replay)
                self._emit_replay(command, result, started_at)
                return result

            snapshot = await self._snapshot_reader.resolve_exact(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
                completion_checklist_version=command.completion_checklist_version,
            )
            if snapshot is None:
                raise GapDetectionError("gap_snapshot_unavailable")
            self._assert_snapshot(command, snapshot)
            (
                batch,
                critical,
                ai_candidate_count,
                critical_candidate_count,
            ) = await self._execute_with_repair(command=command, snapshot=snapshot)
            return await self._persist(
                command=command,
                snapshot=snapshot,
                batch=batch,
                critical=critical,
                ai_candidate_count=ai_candidate_count,
                critical_candidate_count=critical_candidate_count,
                started_at=started_at,
            )
        except Exception as error:
            reason_code = (
                error.reason_code
                if isinstance(error, GapDetectionError)
                else "gap_detection_failed"
            )
            if isinstance(error, GapSnapshotChangedError):
                event_name = "gap.snapshot_changed"
            else:
                event_name = "gap.detection_failed"
            self._event_logger.emit(
                event_name,
                level="ERROR",
                correlation_id=str(command.correlation_id),
                account_id=str(command.account_id),
                project_id=str(command.project_id),
                job_id=str(command.job_id),
                context_version=command.context_version,
                completion_checklist_version=command.completion_checklist_version,
                critical_rule_pack_version=command.critical_rule_pack_version,
                workflow_version=command.workflow_version,
                prompt_version=command.prompt_version,
                duration_ms=(self._clock() - started_at) * 1000,
                reason_code=reason_code,
                status="failed",
            )
            raise

    async def _resolve_replay(
        self, command: DetectGapsCommand
    ) -> GapDetectionReplay | None:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.repository.resolve_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )

    @staticmethod
    def _replay_result(replay: GapDetectionReplay) -> GapDetectionResult:
        if replay.status == "failed":
            raise GapDetectionError(replay.error_code or "gap_detection_failed")
        if replay.gap_count is None or replay.gap_count != len(replay.gap_ids):
            raise GapDetectionRepositoryError("invalid_gap_replay_metadata")
        return GapDetectionResult(
            gap_ids=replay.gap_ids,
            gap_count=replay.gap_count,
            critical_candidate_count=replay.critical_candidate_count or 0,
            authoritative_critical_gap_ids=(),
            rule_generated_gap_count=replay.rule_generated_gap_count or 0,
            critical_gap_count=replay.critical_gap_count or 0,
            replayed=True,
        )

    async def _execute_with_repair(
        self, *, command: DetectGapsCommand, snapshot: GapDetectionSnapshot
    ) -> tuple[CandidateGapBatch, CriticalGapRuleEvaluation, int, int]:
        response = await self._execute_and_meter(
            command=command,
            snapshot=snapshot,
            prompt_version=command.prompt_version,
            repair_no=0,
            repair=None,
        )
        try:
            return await self._validate_and_evaluate(
                response=response, snapshot=snapshot, command=command
            )
        except GapDetectionError as error:
            if isinstance(error, GapDuplicateError):
                self._emit_duplicate_rejected(command)
            reason = _repair_reason(error)
            if reason is None or command.repair_policy.max_repairs == 0:
                raise
        rejected_output = response.data
        response = await self._execute_and_meter(
            command=command,
            snapshot=snapshot,
            prompt_version=command.repair_prompt_version,
            repair_no=1,
            repair={
                "repair_no": 1,
                "repair_policy_version": command.repair_policy.policy_version,
                "structured_error_codes": (reason,),
                "rejected_output": rejected_output,
            },
        )
        try:
            return await self._validate_and_evaluate(
                response=response, snapshot=snapshot, command=command
            )
        except GapDetectionError as error:
            if isinstance(error, GapDuplicateError):
                self._emit_duplicate_rejected(command)
            if _repair_reason(error) is None:
                raise
            raise GapRepairExhaustedError from None

    async def _execute_and_meter(
        self,
        *,
        command: DetectGapsCommand,
        snapshot: GapDetectionSnapshot,
        prompt_version: str,
        repair_no: int,
        repair: Mapping[str, object] | None,
    ) -> StructuredAIResponse:
        input_context = _build_input_context(snapshot)
        if repair is not None:
            input_context = {**input_context, "repair": repair}
        response = await self._ai_execution.execute_structured(
            task_type=command.task_type,
            workflow_version=command.workflow_version,
            prompt_version=prompt_version,
            output_schema=command.output_schema,
            input_context=input_context,
            routing_policy=command.routing_policy,
            cost_budget=command.cost_budget,
            timeout_policy=command.timeout_policy,
            metadata={
                "account_id": str(command.account_id),
                "project_id": str(command.project_id),
                "job_id": str(command.job_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        await self._usage_ledger.append(
            UsageRecord(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                task_type=command.task_type,
                workflow_version=response.workflow_version,
                prompt_version=response.prompt_version,
                provider=response.provider,
                model=response.model,
                provider_request_id=response.provider_request_id,
                input_tokens=response.input_tokens,
                cached_input_tokens=response.cached_input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=Decimal(str(response.latency_ms)),
                status=response.status,
                error_code=None
                if response.status == "success"
                else "ai_execution_failed",
                retry_no=response.retry_no,
                repair_no=repair_no,
                estimated_cost=Decimal(str(response.estimated_cost)),
                pricing_version=command.pricing_version,
                correlation_id=command.correlation_id,
            )
        )
        if response.status != "success":
            raise GapDetectionError("provider_execution_failed")
        return response

    @staticmethod
    def _validate_response(
        response: StructuredAIResponse, snapshot: GapDetectionSnapshot
    ) -> CandidateGapBatch:
        if not isinstance(response.data, CandidateGapBatch):
            raise GapDetectionSchemaError("invalid_gap_candidate_batch")
        _validate_provenance(response.data, snapshot)
        _validate_affected_requirements(response.data, snapshot)
        return response.data

    async def _validate_and_evaluate(
        self,
        *,
        response: StructuredAIResponse,
        snapshot: GapDetectionSnapshot,
        command: DetectGapsCommand,
    ) -> tuple[CandidateGapBatch, CriticalGapRuleEvaluation, int, int]:
        candidate_batch = self._validate_response(response, snapshot)
        critical = await self._critical_rule_evaluator.evaluate(
            snapshot=snapshot,
            batch=candidate_batch,
            rule_pack_version=command.critical_rule_pack_version,
        )
        self._validate_critical_evaluation(critical, candidate_batch)
        evaluated_batch = _apply_critical_evaluation(candidate_batch, critical)
        _reject_exact_duplicates(evaluated_batch)
        return (
            evaluated_batch,
            critical,
            len(candidate_batch.items),
            sum(candidate.severity == "critical" for candidate in candidate_batch.items),
        )

    async def _persist(
        self,
        *,
        command: DetectGapsCommand,
        snapshot: GapDetectionSnapshot,
        batch: CandidateGapBatch,
        critical: CriticalGapRuleEvaluation,
        ai_candidate_count: int,
        critical_candidate_count: int,
        started_at: float,
    ) -> GapDetectionResult:
        gap_ids = tuple(self._id_factory() for _ in batch.items)
        writes = tuple(
            GapWrite(
                id=gap_id,
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
                gap_type=candidate.gap_type,
                severity=candidate.severity,
                explanation=candidate.explanation,
                source_refs=candidate.source_refs,
                suggested_resolution_type=candidate.suggested_resolution_type,
                generation_job_id=command.job_id,
                affected_requirement_ids=tuple(
                    sorted(
                        candidate.affected_requirement_ids, key=lambda value: value.int
                    )
                ),
            )
            for gap_id, candidate in zip(gap_ids, batch.items, strict=True)
        )
        async with self._unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.repository
            replay = await repository.resolve_replay(
                account_id=command.account_id,
                project_id=command.project_id,
                generation_job_id=command.job_id,
            )
            if replay is not None:
                result = self._replay_result(replay)
                self._emit_replay(command, result, started_at)
                return result
            actual = await repository.lock_snapshot_and_resolve_revisions(
                account_id=command.account_id,
                project_id=command.project_id,
                context_version=command.context_version,
            )
            if actual is None:
                raise GapSnapshotChangedError
            self._assert_locked_snapshot(command, snapshot, actual)
            await repository.add_batch(writes)
            await repository.mark_job_succeeded(
                account_id=command.account_id,
                project_id=command.project_id,
                job_id=command.job_id,
                gap_count=len(writes),
                critical_candidate_count=critical_candidate_count,
                rule_generated_gap_count=len(critical.generated_candidates),
                critical_gap_count=sum(
                    candidate.severity == "critical" for candidate in batch.items
                ),
                completion_checklist_version=command.completion_checklist_version,
                critical_rule_pack_version=command.critical_rule_pack_version,
                finished_at=self._wall_clock(),
            )
            await unit_of_work.commit()

        critical_gap_ids = tuple(
            gap_id
            for gap_id, candidate in zip(gap_ids, batch.items, strict=True)
            if candidate.severity == "critical"
        )
        result = GapDetectionResult(
            gap_ids=gap_ids,
            gap_count=len(gap_ids),
            critical_candidate_count=critical_candidate_count,
            authoritative_critical_gap_ids=critical_gap_ids,
            rule_generated_gap_count=len(critical.generated_candidates),
            critical_gap_count=len(critical_gap_ids),
        )
        for gap_id in result.gap_ids:
            emit_product_analytics(
                self._event_logger,
                event_name="gap_detected",
                logical_id=gap_id,
                account_id=command.account_id,
                project_id=command.project_id,
                properties={"gap_id": gap_id, "context_version": command.context_version},
            )
        self._event_logger.emit(
            "gap.detection_completed",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            completion_checklist_version=command.completion_checklist_version,
            critical_rule_pack_version=command.critical_rule_pack_version,
            workflow_version=command.workflow_version,
            prompt_version=command.prompt_version,
            ai_candidate_count=ai_candidate_count,
            rule_generated_gap_count=result.rule_generated_gap_count,
            gap_count=result.gap_count,
            critical_gap_count=result.critical_gap_count,
            matched_rule_count=len(critical.matched_rule_ids),
            duration_ms=(self._clock() - started_at) * 1000,
            status="success",
        )
        return result

    @staticmethod
    def _assert_snapshot(
        command: DetectGapsCommand, snapshot: GapDetectionSnapshot
    ) -> None:
        if (
            snapshot.context_version != command.context_version
            or snapshot.completion_checklist_version
            != command.completion_checklist_version
            or snapshot.context_item_revisions != command.context_item_revisions
            or snapshot.requirement_revisions != command.requirement_revisions
        ):
            raise GapSnapshotChangedError

    @staticmethod
    def _assert_locked_snapshot(
        command: DetectGapsCommand,
        original: GapDetectionSnapshot,
        actual: GapSnapshotRevisions,
    ) -> None:
        if (
            actual.project_type != original.project_type
            or actual.context_item_revisions != command.context_item_revisions
            or actual.requirement_revisions != command.requirement_revisions
        ):
            raise GapSnapshotChangedError

    @staticmethod
    def _validate_critical_evaluation(
        evaluation: CriticalGapRuleEvaluation, batch: CandidateGapBatch
    ) -> None:
        if any(
            index >= len(batch.items)
            for index in evaluation.authoritative_candidate_indexes
        ):
            raise GapDetectionError("invalid_critical_rule_evaluation")

    def _emit_replay(
        self,
        command: DetectGapsCommand,
        result: GapDetectionResult,
        started_at: float,
    ) -> None:
        self._event_logger.emit(
            "gap.replay_served",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            completion_checklist_version=command.completion_checklist_version,
            critical_rule_pack_version=command.critical_rule_pack_version,
            gap_count=result.gap_count,
            duration_ms=(self._clock() - started_at) * 1000,
            status="success",
        )

    def _emit_duplicate_rejected(self, command: DetectGapsCommand) -> None:
        self._event_logger.emit(
            "gap.duplicate_rejected",
            level="ERROR",
            correlation_id=str(command.correlation_id),
            account_id=str(command.account_id),
            project_id=str(command.project_id),
            job_id=str(command.job_id),
            context_version=command.context_version,
            completion_checklist_version=command.completion_checklist_version,
            critical_rule_pack_version=command.critical_rule_pack_version,
            reason_code="duplicate_gap",
            status="rejected",
        )


def _validate_rule_signal_candidate_index(
    signal: RuleSignal, batch: CandidateGapBatch
) -> None:
    if signal.candidate_index is not None and signal.candidate_index >= len(batch.items):
        raise GapRuleSignalError("rule_signal_candidate_outside_batch")


def _validate_linked_candidate(
    candidate_index: int | None,
    batch: CandidateGapBatch,
    *,
    expected_gap_type: GapType,
    expected_requirement_ids: frozenset[UUID] | None = None,
) -> None:
    if candidate_index is None:
        return
    candidate = batch.items[candidate_index]
    if candidate.gap_type != expected_gap_type:
        raise GapRuleSignalError("rule_signal_candidate_type_mismatch")
    if expected_requirement_ids is not None and frozenset(
        candidate.affected_requirement_ids
    ) != expected_requirement_ids:
        raise GapRuleSignalError("rule_signal_candidate_requirements_mismatch")


def _canonical_reference_union(
    references: Iterable[GapSourceReference],
) -> tuple[GapSourceReference, ...]:
    unique: dict[tuple[UUID, UUID, int | None, int | None], GapSourceReference] = {}
    for reference in references:
        unique[reference.identity()] = reference
    return tuple(
        sorted(
            unique.values(),
            key=lambda value: (
                value.source_id.int,
                value.source_version_id.int,
                -1 if value.start_offset is None else value.start_offset,
                -1 if value.end_offset is None else value.end_offset,
            ),
        )
    )


def _apply_critical_evaluation(
    batch: CandidateGapBatch, evaluation: CriticalGapRuleEvaluation
) -> CandidateGapBatch:
    authoritative = set(evaluation.authoritative_candidate_indexes)
    evaluated = tuple(
        replace(
            candidate,
            severity=(
                "critical"
                if index in authoritative
                else "high"
                if candidate.severity == "critical"
                else candidate.severity
            ),
        )
        for index, candidate in enumerate(batch.items)
    )
    return CandidateGapBatch(
        items=evaluated + evaluation.generated_candidates,
        rule_signals=batch.rule_signals,
    )


def _reject_exact_duplicates(batch: CandidateGapBatch) -> None:
    identities: set[tuple[object, ...]] = set()
    for candidate in batch.items:
        if candidate.exact_identity in identities:
            raise GapDuplicateError
        identities.add(candidate.exact_identity)


def _validate_provenance(
    batch: CandidateGapBatch, snapshot: GapDetectionSnapshot
) -> None:
    allowed = {
        reference.identity()
        for item in snapshot.context_items
        for reference in item.source_refs
    }
    allowed.update(
        reference.identity()
        for item in snapshot.requirements
        for reference in item.source_refs
    )
    for candidate in batch.items:
        for reference in candidate.source_refs:
            if reference.identity() not in allowed:
                raise GapDetectionProvenanceError(
                    "source_reference_outside_gap_snapshot"
                )


def _validate_affected_requirements(
    batch: CandidateGapBatch, snapshot: GapDetectionSnapshot
) -> None:
    allowed = {requirement.id for requirement in snapshot.requirements}
    for candidate in batch.items:
        if len(set(candidate.affected_requirement_ids)) != len(
            candidate.affected_requirement_ids
        ) or any(
            requirement_id not in allowed
            for requirement_id in candidate.affected_requirement_ids
        ):
            raise GapAffectedRequirementError("requirement_outside_gap_snapshot")


def _build_input_context(snapshot: GapDetectionSnapshot) -> Mapping[str, object]:
    return {
        "project_type": snapshot.project_type,
        "context_version": snapshot.context_version,
        "completion_checklist_version": snapshot.completion_checklist_version,
        "context_items": tuple(
            {
                "context_item_id": str(item.id),
                "item_type": item.item_type,
                "status": item.status,
                "content": item.content,
                "source_refs": tuple(
                    _source_reference_dict(ref) for ref in item.source_refs
                ),
            }
            for item in snapshot.context_items
        ),
        "requirements": tuple(
            {
                "requirement_id": str(item.id),
                "category": item.category,
                "title": item.title,
                "description": item.description,
                "priority": item.priority,
                "status": item.status,
                "source_refs": tuple(
                    _source_reference_dict(ref) for ref in item.source_refs
                ),
            }
            for item in snapshot.requirements
        ),
    }


def _source_reference_dict(reference: GapSourceReference) -> Mapping[str, object]:
    value: dict[str, object] = {
        "source_id": str(reference.source_id),
        "source_version_id": str(reference.source_version_id),
    }
    if reference.start_offset is not None:
        value["start_offset"] = reference.start_offset
        value["end_offset"] = reference.end_offset
    return value


def _repair_reason(error: GapDetectionError) -> str | None:
    if isinstance(error, GapDetectionSchemaError):
        return "schema_invalid"
    if isinstance(error, GapDetectionProvenanceError):
        return "invalid_source_reference"
    if isinstance(error, GapAffectedRequirementError):
        return "invalid_affected_requirement"
    if isinstance(error, GapDuplicateError):
        return "duplicate_gap"
    return None


def _assert_sorted_unique_context_revisions(
    revisions: tuple[ContextItemRevision, ...],
) -> None:
    canonical = tuple(sorted(revisions, key=lambda value: value.context_item_id.int))
    if canonical != revisions or len(
        {value.context_item_id for value in revisions}
    ) != len(revisions):
        raise ValueError("Context Item revision vector must be sorted and unique")


def _assert_sorted_unique_requirement_revisions(
    revisions: tuple[RequirementRevision, ...],
) -> None:
    canonical = tuple(sorted(revisions, key=lambda value: value.requirement_id.int))
    if canonical != revisions or len(
        {value.requirement_id for value in revisions}
    ) != len(revisions):
        raise ValueError("Requirement revision vector must be sorted and unique")
