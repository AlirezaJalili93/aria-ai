from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast
from uuid import UUID, uuid5

from aria_backend_application.context_structuring import (
    CandidateContextBatch,
    CandidateContextItem,
    CandidateSourceReference,
    ContextStructuringError,
)
from aria_backend_application.gap_detection import (
    COMPLETION_CHECKLIST_V1,
    CRITICAL_GAP_RULE_PACK_VERSION,
    CandidateGap,
    CandidateGapBatch,
    ChecklistItemRuleSignal,
    CriticalAssumptionRuleSignal,
    GapContextItem,
    GapDetectionError,
    GapDetectionSnapshot,
    GapRequirement,
    GapSourceReference,
    RequirementConflictRuleSignal,
    RuleSignal,
    VersionedCriticalGapRuleEvaluator,
)
from aria_backend_application.requirements_generation import (
    CandidateRequirement,
    CandidateRequirementBatch,
    RequirementGenerationError,
    RequirementSourceReference,
)

from app.application.ai_execution import StructuredValue
from app.application.provider_quality_evaluation import (
    EvaluationCase,
    EvaluationContractError,
)

PROMPT_VERSIONS = {
    "context_structuring_eval_v1": "ai-01-real-eval-prompt-v1",
    "requirement_extraction_eval_v1": "ai-02-real-eval-prompt-v1",
    "gap_detection_eval_v1": "ai-03-real-eval-prompt-v1",
}
WORKFLOW_VERSIONS = {
    "context_structuring_eval_v1": "ai-01-context-structuring-v1",
    "requirement_extraction_eval_v1": "ai-02-requirement-extraction-v1",
    "gap_detection_eval_v1": "ai-03-gap-detection-v1",
}
SCHEMA_VERSIONS = {
    "context_structuring_eval_v1": "candidate-context-batch-v1",
    "requirement_extraction_eval_v1": "candidate-requirement-batch-v1",
    "gap_detection_eval_v1": "candidate-gap-batch-rule-signals-v1",
}
COMPLETION_CHECKLIST_VERSION = "completion_checklist_v1"
EVALUATION_ID_NAMESPACE = UUID("09a60ad4-2be5-4f82-bd2e-ea6de2d27fb3")
type SourceReference = CandidateSourceReference | RequirementSourceReference | GapSourceReference


class ApprovedPromptSchemaPackageV1:
    """Frozen 0086 prompts, provider-visible inputs and strict output schemas."""

    def materialize(
        self,
        *,
        eval_suite_version: str,
        fixture: Mapping[str, object],
        fixture_set_version: str,
        evaluation_rule_version: str,
    ) -> EvaluationCase:
        fixture_id = _required_string(fixture, "fixture_id")
        project_type = _required_string(fixture, "project_type")
        input_value = _required_mapping(fixture, "input")
        if eval_suite_version == "context_structuring_eval_v1":
            provider_input: StructuredValue = {
                "project_type": project_type,
                "sources": _required_list(input_value, "sources"),
            }
            instructions = _context_instructions()
            output_schema = _context_schema()
        elif eval_suite_version == "requirement_extraction_eval_v1":
            provider_input = {
                "project_type": project_type,
                "context_version": _required_positive_int(input_value, "context_version"),
                "context_items": _required_list(input_value, "context_items"),
            }
            instructions = _requirement_instructions()
            output_schema = _requirement_schema()
        elif eval_suite_version == "gap_detection_eval_v1":
            provider_input = {
                "project_type": project_type,
                "context_items": _required_list(input_value, "context_items"),
                "requirements": _required_list(input_value, "requirements"),
                "completion_checklist_v1": [
                    asdict(item) for item in COMPLETION_CHECKLIST_V1.items_for(project_type) or ()
                ],
            }
            if not provider_input["completion_checklist_v1"]:
                raise EvaluationContractError("evaluation_project_type_unsupported")
            instructions = _gap_instructions()
            output_schema = _gap_schema()
        else:
            raise EvaluationContractError("evaluation_suite_unsupported")

        return EvaluationCase(
            eval_suite_version=eval_suite_version,
            fixture_set_version=fixture_set_version,
            fixture_id=fixture_id,
            workflow_version=WORKFLOW_VERSIONS[eval_suite_version],
            prompt_version=PROMPT_VERSIONS[eval_suite_version],
            schema_version=SCHEMA_VERSIONS[eval_suite_version],
            evaluation_rule_version=evaluation_rule_version,
            request={
                "instructions": instructions,
                "input": provider_input,
                "output_schema": output_schema,
            },
        )

    async def normalize(
        self,
        *,
        case: EvaluationCase,
        provider_output: object,
    ) -> StructuredValue:
        try:
            if case.eval_suite_version == "context_structuring_eval_v1":
                return _normalize_context(case, provider_output)
            if case.eval_suite_version == "requirement_extraction_eval_v1":
                return _normalize_requirements(case, provider_output)
            if case.eval_suite_version == "gap_detection_eval_v1":
                return await _normalize_gaps(case, provider_output)
            raise EvaluationContractError("evaluation_suite_unsupported")
        except (
            ContextStructuringError,
            RequirementGenerationError,
            GapDetectionError,
        ) as error:
            raise EvaluationContractError("evaluation_output_invalid") from error


def _context_instructions() -> str:
    return (
        "متن مصنوعی فارسی را به آیتم‌های زمینه ساختاریافته تبدیل کن. فقط ادعاهای "
        "پشتیبانی‌شده را با ارجاع قابل‌حل به source_id/source_version_id ورودی برگردان. "
        "عدم قطعیت را به‌صورت assumption یا unknown حفظ کن. هیچ شناسه، منبع یا واقعیت "
        "جدیدی اختراع نکن. فقط JSON مطابق schema برگردان."
    )


def _requirement_instructions() -> str:
    return (
        "از snapshot مصنوعی زمینه، Requirementهای فارسی روشن و قابل‌اقدام استخراج کن. "
        "Requirement پشتیبانی‌شده باید فقط از source_refs موجود در context_items استفاده کند. "
        "مورد بدون پشتیبانی را unsupported=true علامت بزن و واقعیت تازه اختراع نکن. "
        "فقط JSON مطابق schema برگردان."
    )


def _gap_instructions() -> str:
    return (
        "Gapهای پروژه مصنوعی را از context_items، requirements و checklist داده‌شده استخراج کن. "
        "severity فقط high/medium/low است؛ Critical را تعیین نکن. برای تمام checklist items "
        "یک checklist_item rule signal بساز. rule_signals فقط شواهد ساختاری برای "
        "Rule Pack قطعی‌اند. "
        "فقط از شناسه‌ها و source_refs ورودی استفاده کن و فقط JSON مطابق schema برگردان."
    )


def _source_ref_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["source_id", "source_version_id", "start_offset", "end_offset"],
        "properties": {
            "source_id": {"type": "string", "minLength": 1},
            "source_version_id": {"type": "string", "minLength": 1},
            "start_offset": {"type": ["integer", "null"], "minimum": 0},
            "end_offset": {"type": ["integer", "null"], "minimum": 1},
        },
    }


def _context_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "item_type",
                        "content",
                        "source_refs",
                        "confidence",
                        "rationale_short",
                    ],
                    "properties": {
                        "item_type": {
                            "enum": [
                                "fact",
                                "assumption",
                                "decision",
                                "constraint",
                                "reference",
                                "unknown",
                            ]
                        },
                        "content": {"type": "string", "minLength": 1},
                        "source_refs": {"type": "array", "items": _source_ref_schema()},
                        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                        "rationale_short": {"type": ["string", "null"]},
                    },
                },
            }
        },
    }


def _requirement_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "description",
                        "category",
                        "priority",
                        "source_refs",
                        "confidence",
                        "unsupported",
                        "duplicate_group_key",
                        "conflict_group_key",
                    ],
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "description": {"type": "string", "minLength": 1},
                        "category": {
                            "enum": [
                                "functional",
                                "content",
                                "visual",
                                "technical",
                                "constraint",
                                "business",
                            ]
                        },
                        "priority": {"enum": ["must", "should", "could"]},
                        "source_refs": {"type": "array", "items": _source_ref_schema()},
                        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
                        "unsupported": {"type": "boolean"},
                        "duplicate_group_key": {"type": ["string", "null"]},
                        "conflict_group_key": {"type": ["string", "null"]},
                    },
                },
            }
        },
    }


def _gap_schema() -> dict[str, object]:
    candidate_index = {"type": ["integer", "null"], "minimum": 0}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items", "rule_signals"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "gap_type",
                        "severity",
                        "explanation",
                        "source_refs",
                        "affected_requirement_ids",
                        "suggested_resolution_type",
                    ],
                    "properties": {
                        "gap_type": {
                            "enum": [
                                "missing_information",
                                "ambiguity",
                                "conflict",
                                "decision_required",
                                "unsupported_assumption",
                                "scope_risk",
                            ]
                        },
                        "severity": {"enum": ["high", "medium", "low"]},
                        "explanation": {"type": "string", "minLength": 1},
                        "source_refs": {"type": "array", "items": _source_ref_schema()},
                        "affected_requirement_ids": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                        "suggested_resolution_type": {
                            "enum": [
                                "provide_information",
                                "clarify_ambiguity",
                                "resolve_conflict",
                                "make_decision",
                                "validate_assumption",
                                "mitigate_scope_risk",
                            ]
                        },
                    },
                },
            },
            "rule_signals": {
                "type": "array",
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "signal_type",
                                "signal_origin",
                                "checklist_item_id",
                                "state",
                                "supporting_context_item_ids",
                                "candidate_index",
                            ],
                            "properties": {
                                "signal_type": {"const": "checklist_item"},
                                "signal_origin": {"const": "ai_candidate"},
                                "checklist_item_id": {"type": "string", "minLength": 1},
                                "state": {"enum": ["present", "missing"]},
                                "supporting_context_item_ids": {
                                    "type": "array",
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "candidate_index": candidate_index,
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "signal_type",
                                "signal_origin",
                                "requirement_ids",
                                "candidate_index",
                            ],
                            "properties": {
                                "signal_type": {"const": "requirement_conflict"},
                                "signal_origin": {"const": "ai_candidate"},
                                "requirement_ids": {
                                    "type": "array",
                                    "minItems": 2,
                                    "items": {"type": "string", "minLength": 1},
                                },
                                "candidate_index": candidate_index,
                            },
                        },
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "signal_type",
                                "signal_origin",
                                "context_item_id",
                                "risk_domain",
                                "candidate_index",
                            ],
                            "properties": {
                                "signal_type": {"const": "critical_assumption"},
                                "signal_origin": {"const": "ai_candidate"},
                                "context_item_id": {"type": "string", "minLength": 1},
                                "risk_domain": {
                                    "enum": ["payment", "security", "external_integration"]
                                },
                                "candidate_index": candidate_index,
                            },
                        },
                    ]
                },
            },
        },
    }


def _normalize_context(case: EvaluationCase, output: StructuredValue) -> StructuredValue:
    root = _exact_mapping(output, {"items"})
    source_index = _context_source_index(case)
    items: list[CandidateContextItem] = []
    serialized: list[dict[str, object]] = []
    for index, value in enumerate(_sequence(root["items"])):
        item = _exact_mapping(
            value, {"item_type", "content", "source_refs", "confidence", "rationale_short"}
        )
        raw_refs = tuple(_sequence(item["source_refs"]))
        refs = tuple(_context_ref(ref, source_index) for ref in raw_refs)
        candidate = CandidateContextItem(
            item_type=cast(
                Literal[
                    "fact",
                    "assumption",
                    "decision",
                    "constraint",
                    "reference",
                    "unknown",
                ],
                item["item_type"],
            ),
            content=_nonempty_text(item["content"]),
            source_refs=refs,
            confidence=_decimal(item["confidence"]),
            rationale_short=_optional_text(item["rationale_short"]),
        )
        items.append(candidate)
        serialized.append(
            {
                "candidate_id": _candidate_id(case, index),
                "item_type": candidate.item_type,
                "content": candidate.content,
                "source_refs": [_serialize_raw_ref(ref) for ref in raw_refs],
                "confidence": _decimal_json(candidate.confidence),
                "rationale_short": candidate.rationale_short,
            }
        )
    CandidateContextBatch(tuple(items))
    return {"items": serialized}


def _normalize_requirements(case: EvaluationCase, output: StructuredValue) -> StructuredValue:
    root = _exact_mapping(output, {"items"})
    allowed_refs = _input_reference_index(case, "context_items")
    items: list[CandidateRequirement] = []
    serialized: list[dict[str, object]] = []
    for index, value in enumerate(_sequence(root["items"])):
        item = _exact_mapping(
            value,
            {
                "title",
                "description",
                "category",
                "priority",
                "source_refs",
                "confidence",
                "unsupported",
                "duplicate_group_key",
                "conflict_group_key",
            },
        )
        raw_refs = tuple(_sequence(item["source_refs"]))
        refs = tuple(_requirement_ref(ref, allowed_refs) for ref in raw_refs)
        unsupported = _boolean(item["unsupported"])
        if not unsupported and not refs:
            raise EvaluationContractError("supported_provenance_required")
        candidate = CandidateRequirement(
            title=_nonempty_text(item["title"]),
            description=_nonempty_text(item["description"]),
            category=cast(
                Literal[
                    "functional",
                    "content",
                    "visual",
                    "technical",
                    "constraint",
                    "business",
                ],
                item["category"],
            ),
            priority=cast(Literal["must", "should", "could"], item["priority"]),
            source_refs=refs,
            confidence=_decimal(item["confidence"]),
            unsupported=unsupported,
            duplicate_group_key=_optional_text(item["duplicate_group_key"]),
            conflict_group_key=_optional_text(item["conflict_group_key"]),
        )
        items.append(candidate)
        serialized.append(
            {
                "candidate_id": _candidate_id(case, index),
                "title": candidate.title,
                "description": candidate.description,
                "category": candidate.category,
                "priority": candidate.priority,
                "source_refs": [_serialize_raw_ref(ref) for ref in raw_refs],
                "confidence": _decimal_json(candidate.confidence),
                "unsupported": candidate.unsupported,
                "duplicate_group_key": candidate.duplicate_group_key,
                "conflict_group_key": candidate.conflict_group_key,
            }
        )
    CandidateRequirementBatch(tuple(items))
    return {"items": serialized}


async def _normalize_gaps(case: EvaluationCase, output: StructuredValue) -> StructuredValue:
    root = _exact_mapping(output, {"items", "rule_signals"})
    snapshot, context_ids, requirement_ids, allowed_refs = _gap_snapshot(case)
    requirement_aliases = {value: alias for alias, value in requirement_ids.items()}
    candidates: list[CandidateGap] = []
    for value in _sequence(root["items"]):
        item = _exact_mapping(
            value,
            {
                "gap_type",
                "severity",
                "explanation",
                "source_refs",
                "affected_requirement_ids",
                "suggested_resolution_type",
            },
        )
        severity = _nonempty_text(item["severity"])
        if severity == "critical":
            raise EvaluationContractError("provider_critical_classification_prohibited")
        refs = tuple(_gap_ref(ref, allowed_refs) for ref in _sequence(item["source_refs"]))
        affected = tuple(
            _resolve_alias(v, requirement_ids, "requirement_outside_gap_snapshot")
            for v in _sequence(item["affected_requirement_ids"])
        )
        candidates.append(
            CandidateGap(
                gap_type=cast(
                    Literal[
                        "missing_information",
                        "ambiguity",
                        "conflict",
                        "decision_required",
                        "unsupported_assumption",
                        "scope_risk",
                    ],
                    item["gap_type"],
                ),
                severity=cast(Literal["critical", "high", "medium", "low"], severity),
                explanation=_nonempty_text(item["explanation"]),
                source_refs=refs,
                affected_requirement_ids=affected,
                suggested_resolution_type=cast(
                    Literal[
                        "provide_information",
                        "clarify_ambiguity",
                        "resolve_conflict",
                        "make_decision",
                        "validate_assumption",
                        "mitigate_scope_risk",
                    ],
                    item["suggested_resolution_type"],
                ),
            )
        )
    signals = tuple(
        _rule_signal(value, context_ids, requirement_ids)
        for value in _sequence(root["rule_signals"])
    )
    batch = CandidateGapBatch(tuple(candidates), signals)
    evaluation = await VersionedCriticalGapRuleEvaluator().evaluate(
        snapshot=snapshot, batch=batch, rule_pack_version=CRITICAL_GAP_RULE_PACK_VERSION
    )
    critical_indexes = set(evaluation.authoritative_candidate_indexes)
    finalized = (
        tuple(
            replace(candidate, severity="critical") if index in critical_indexes else candidate
            for index, candidate in enumerate(batch.items)
        )
        + evaluation.generated_candidates
    )
    return {
        "items": [
            {
                "candidate_id": _candidate_id(case, index),
                "gap_type": candidate.gap_type,
                "severity": candidate.severity,
                "explanation": candidate.explanation,
                "source_refs": [
                    _serialize_resolved_ref(ref, allowed_refs) for ref in candidate.source_refs
                ],
                "affected_requirement_ids": [
                    requirement_aliases.get(value, str(value))
                    for value in candidate.affected_requirement_ids
                ],
                "suggested_resolution_type": candidate.suggested_resolution_type,
                "critical_rule_id": (
                    _critical_rule_id(candidate.gap_type)
                    if candidate.severity == "critical"
                    else None
                ),
            }
            for index, candidate in enumerate(finalized)
        ],
        "matched_critical_rule_ids": list(evaluation.matched_rule_ids),
    }


def _gap_snapshot(
    case: EvaluationCase,
) -> tuple[
    GapDetectionSnapshot,
    dict[str, UUID],
    dict[str, UUID],
    set[tuple[str, str, int | None, int | None]],
]:
    request_input = _request_input(case)
    context_ids: dict[str, UUID] = {}
    requirement_ids: dict[str, UUID] = {}
    refs = _input_reference_index(case, "context_items") | _input_reference_index(
        case, "requirements"
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    context_items = []
    for raw in _sequence(request_input["context_items"]):
        item = cast(Mapping[str, object], raw)
        alias = _required_string(item, "context_item_id")
        item_id = _stable_uuid("context_item", alias)
        context_ids[alias] = item_id
        context_items.append(
            GapContextItem(
                id=item_id,
                updated_at=now,
                item_type=_required_string(item, "item_type"),
                status=cast(
                    Literal["proposed", "confirmed"],
                    _required_string(item, "status"),
                ),
                content=_required_string(item, "content"),
                source_refs=tuple(_gap_ref(v, refs) for v in _required_list(item, "source_refs")),
            )
        )
    requirements = []
    for raw in _sequence(request_input["requirements"]):
        item = cast(Mapping[str, object], raw)
        alias = _required_string(item, "requirement_id")
        requirement_id = _stable_uuid("requirement", alias)
        requirement_ids[alias] = requirement_id
        requirements.append(
            GapRequirement(
                id=requirement_id,
                updated_at=now,
                category=_required_string(item, "category"),
                title=_required_string(item, "title"),
                description=_required_string(item, "description"),
                priority=_required_string(item, "priority"),
                status=cast(
                    Literal["draft", "confirmed"],
                    _required_string(item, "status"),
                ),
                source_refs=tuple(_gap_ref(v, refs) for v in _required_list(item, "source_refs")),
            )
        )
    return (
        GapDetectionSnapshot(
            project_type=_required_string(request_input, "project_type"),
            context_version=1,
            completion_checklist_version=COMPLETION_CHECKLIST_VERSION,
            context_items=tuple(context_items),
            requirements=tuple(requirements),
        ),
        context_ids,
        requirement_ids,
        refs,
    )


def _rule_signal(
    value: object, context_ids: Mapping[str, UUID], requirement_ids: Mapping[str, UUID]
) -> RuleSignal:
    item = cast(Mapping[str, object], value)
    signal_type = _required_string(item, "signal_type")
    origin = _required_string(item, "signal_origin")
    candidate_index = _optional_int(item.get("candidate_index"))
    if signal_type == "checklist_item":
        return ChecklistItemRuleSignal(
            signal_type="checklist_item",
            signal_origin=cast(Literal["ai_candidate"], origin),
            checklist_item_id=_required_string(item, "checklist_item_id"),
            state=cast(Literal["present", "missing"], _required_string(item, "state")),
            supporting_context_item_ids=tuple(
                _resolve_alias(v, context_ids, "checklist_support_outside_snapshot")
                for v in _required_list(item, "supporting_context_item_ids")
            ),
            candidate_index=candidate_index,
        )
    if signal_type == "requirement_conflict":
        return RequirementConflictRuleSignal(
            signal_type="requirement_conflict",
            signal_origin=cast(Literal["ai_candidate"], origin),
            requirement_ids=tuple(
                _resolve_alias(v, requirement_ids, "conflict_requirement_outside_snapshot")
                for v in _required_list(item, "requirement_ids")
            ),
            candidate_index=candidate_index,
        )
    if signal_type == "critical_assumption":
        return CriticalAssumptionRuleSignal(
            signal_type="critical_assumption",
            signal_origin=cast(Literal["ai_candidate"], origin),
            context_item_id=_resolve_alias(
                item.get("context_item_id"), context_ids, "critical_assumption_outside_snapshot"
            ),
            risk_domain=cast(
                Literal["payment", "security", "external_integration"],
                _required_string(item, "risk_domain"),
            ),
            candidate_index=candidate_index,
        )
    raise EvaluationContractError("invalid_rule_signal_type")


def _context_source_index(case: EvaluationCase) -> dict[tuple[str, str], int]:
    values: dict[tuple[str, str], int] = {}
    for raw in _sequence(_request_input(case)["sources"]):
        item = cast(Mapping[str, object], raw)
        key = (_required_string(item, "source_id"), _required_string(item, "source_version_id"))
        text = _required_string(item, "canonical_text")
        values[key] = len(text)
    return values


def _input_reference_index(
    case: EvaluationCase, collection: str
) -> set[tuple[str, str, int | None, int | None]]:
    values: set[tuple[str, str, int | None, int | None]] = set()
    for raw in _sequence(_request_input(case)[collection]):
        item = cast(Mapping[str, object], raw)
        for ref in _required_list(item, "source_refs"):
            values.add(_raw_ref_identity(ref))
    return values


def _context_ref(value: object, allowed: Mapping[tuple[str, str], int]) -> CandidateSourceReference:
    source_id, version_id, start, end = _raw_ref_identity(value)
    length = allowed.get((source_id, version_id))
    if length is None or (end is not None and end > length):
        raise EvaluationContractError("source_reference_outside_input")
    return CandidateSourceReference(
        _stable_uuid("source", source_id), _stable_uuid("source_version", version_id), start, end
    )


def _requirement_ref(
    value: object, allowed: set[tuple[str, str, int | None, int | None]]
) -> RequirementSourceReference:
    identity = _raw_ref_identity(value)
    if identity not in allowed:
        raise EvaluationContractError("source_reference_outside_context_snapshot")
    return RequirementSourceReference(
        _stable_uuid("source", identity[0]),
        _stable_uuid("source_version", identity[1]),
        identity[2],
        identity[3],
    )


def _gap_ref(
    value: object, allowed: set[tuple[str, str, int | None, int | None]]
) -> GapSourceReference:
    identity = _raw_ref_identity(value)
    if identity not in allowed:
        raise EvaluationContractError("source_reference_outside_gap_snapshot")
    return GapSourceReference(
        _stable_uuid("source", identity[0]),
        _stable_uuid("source_version", identity[1]),
        identity[2],
        identity[3],
    )


def _raw_ref_identity(value: object) -> tuple[str, str, int | None, int | None]:
    if not isinstance(value, Mapping):
        raise EvaluationContractError("evaluation_output_schema_invalid")
    item = cast(Mapping[str, object], value)
    source_id = _required_string(item, "source_id")
    version_id = _required_string(item, "source_version_id")
    start = _optional_int(item.get("start_offset"))
    end = _optional_int(item.get("end_offset"))
    if (start is None) != (end is None) or (
        start is not None and (start < 0 or end is None or start >= end)
    ):
        raise EvaluationContractError("invalid_source_reference_offsets")
    return source_id, version_id, start, end


def _serialize_raw_ref(value: object) -> dict[str, object]:
    source_id, source_version_id, start_offset, end_offset = _raw_ref_identity(value)
    return {
        "source_id": source_id,
        "source_version_id": source_version_id,
        "start_offset": start_offset,
        "end_offset": end_offset,
    }


def _serialize_resolved_ref(
    value: SourceReference,
    allowed: set[tuple[str, str, int | None, int | None]],
) -> dict[str, object]:
    for identity in allowed:
        if (
            value.source_id == _stable_uuid("source", identity[0])
            and value.source_version_id == _stable_uuid("source_version", identity[1])
            and value.start_offset == identity[2]
            and value.end_offset == identity[3]
        ):
            return {
                "source_id": identity[0],
                "source_version_id": identity[1],
                "start_offset": identity[2],
                "end_offset": identity[3],
            }
    raise EvaluationContractError("source_reference_outside_gap_snapshot")


def _request_input(case: EvaluationCase) -> Mapping[str, object]:
    value = case.request.get("input")
    if not isinstance(value, Mapping):
        raise EvaluationContractError("evaluation_request_input_invalid")
    return cast(Mapping[str, object], value)


def _exact_mapping(value: object, keys: set[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise EvaluationContractError("evaluation_output_schema_invalid")
    return cast(Mapping[str, object], value)


def _required_mapping(value: Mapping[str, object], field: str) -> Mapping[str, object]:
    result = value.get(field)
    if not isinstance(result, Mapping):
        raise EvaluationContractError("evaluation_fixture_shape_invalid")
    return cast(Mapping[str, object], result)


def _required_list(value: Mapping[str, object], field: str) -> list[object]:
    result = value.get(field)
    if not isinstance(result, list):
        raise EvaluationContractError("evaluation_fixture_shape_invalid")
    return cast(list[object], result)


def _sequence(value: object) -> Sequence[object]:
    if not isinstance(value, list):
        raise EvaluationContractError("evaluation_output_schema_invalid")
    return cast(Sequence[object], value)


def _required_string(value: Mapping[str, object], field: str) -> str:
    return _nonempty_text(value.get(field))


def _nonempty_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationContractError("evaluation_text_invalid")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _nonempty_text(value)


def _required_positive_int(value: Mapping[str, object], field: str) -> int:
    result = value.get(field)
    if isinstance(result, bool) or not isinstance(result, int) or result < 1:
        raise EvaluationContractError("evaluation_positive_integer_required")
    return result


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvaluationContractError("evaluation_integer_invalid")
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise EvaluationContractError("evaluation_boolean_invalid")
    return value


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise EvaluationContractError("evaluation_decimal_invalid")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise EvaluationContractError("evaluation_decimal_invalid") from error
    if not result.is_finite() or result < 0 or result > 1:
        raise EvaluationContractError("evaluation_decimal_invalid")
    return result


def _decimal_json(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _stable_uuid(kind: str, alias: str) -> UUID:
    return uuid5(EVALUATION_ID_NAMESPACE, f"{kind}:{alias}")


def _candidate_id(case: EvaluationCase, index: int) -> str:
    return f"{case.fixture_id}_candidate_{index + 1:03d}"


def _critical_rule_id(gap_type: str) -> str:
    rules = {
        "missing_information": "CGR-001",
        "conflict": "CGR-002",
        "unsupported_assumption": "CGR-003",
    }
    try:
        return rules[gap_type]
    except KeyError as error:
        raise EvaluationContractError("critical_gap_rule_unresolved") from error


def _resolve_alias(value: object, values: Mapping[str, UUID], error_code: str) -> UUID:
    if not isinstance(value, str) or value not in values:
        raise EvaluationContractError(error_code)
    return values[value]
