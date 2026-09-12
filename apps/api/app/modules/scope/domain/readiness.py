from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ScopeReadinessGapStatus = Literal["open", "resolved", "dismissed"]
ScopeReadinessGapSeverity = Literal["critical", "high", "medium", "low"]
ScopeReadinessReason = Literal["critical_gap_open", "no_open_critical_gaps"]

_GAP_STATUSES = frozenset({"open", "resolved", "dismissed"})
_GAP_SEVERITIES = frozenset({"critical", "high", "medium", "low"})


class ScopeReadinessValidationError(ValueError):
    """An input violates the K02 readiness-policy boundary."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeReadinessGap:
    """Persisted Gap metadata supplied by a tenant-scoped repository query."""

    id: UUID
    account_id: UUID
    project_id: UUID
    context_version: int
    severity: ScopeReadinessGapSeverity
    status: ScopeReadinessGapStatus

    def __post_init__(self) -> None:
        if isinstance(self.context_version, bool) or not isinstance(self.context_version, int):
            raise ScopeReadinessValidationError("Gap context_version must be an integer")
        if self.context_version < 1:
            raise ScopeReadinessValidationError("Gap context_version must be at least one")
        if self.severity not in _GAP_SEVERITIES:
            raise ScopeReadinessValidationError("Unsupported Gap severity")
        if self.status not in _GAP_STATUSES:
            raise ScopeReadinessValidationError("Unsupported Gap status")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeReadinessDecision:
    ready_for_share: bool
    reason_code: ScopeReadinessReason
    blocking_gap_ids: tuple[UUID, ...]


class ScopeReadinessPolicy:
    """Compute share-readiness from authoritative, tenant-scoped Gap metadata.

    J02 owns critical-rule evaluation. K02 consumes the resulting persisted severity and never
    re-evaluates model signals or the human decision behind a dismissed Gap.
    """

    def evaluate(
        self,
        *,
        account_id: UUID,
        project_id: UUID,
        context_version: int,
        gaps: Iterable[ScopeReadinessGap],
    ) -> ScopeReadinessDecision:
        if isinstance(context_version, bool) or not isinstance(context_version, int):
            raise ScopeReadinessValidationError("Project context_version must be an integer")
        if context_version < 1:
            raise ScopeReadinessValidationError("Project context_version must be at least one")

        seen_ids: set[UUID] = set()
        blocking_ids: list[UUID] = []
        for gap in gaps:
            if gap.id in seen_ids:
                raise ScopeReadinessValidationError("Gap evidence IDs must be unique")
            seen_ids.add(gap.id)
            if gap.account_id != account_id or gap.project_id != project_id:
                raise ScopeReadinessValidationError("Gap evidence is outside the tenant project")
            if gap.context_version > context_version:
                raise ScopeReadinessValidationError("Gap evidence is ahead of the Project context")
            if (
                gap.context_version == context_version
                and gap.status == "open"
                and gap.severity == "critical"
            ):
                blocking_ids.append(gap.id)

        ordered_blocking_ids = tuple(sorted(blocking_ids, key=str))
        if ordered_blocking_ids:
            return ScopeReadinessDecision(
                ready_for_share=False,
                reason_code="critical_gap_open",
                blocking_gap_ids=ordered_blocking_ids,
            )
        return ScopeReadinessDecision(
            ready_for_share=True,
            reason_code="no_open_critical_gaps",
            blocking_gap_ids=(),
        )
