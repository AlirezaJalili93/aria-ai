from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.scope.domain.readiness import (
    ScopeReadinessGap,
    ScopeReadinessPolicy,
    ScopeReadinessValidationError,
)


def _gap(account_id, project_id, **overrides: object) -> ScopeReadinessGap:
    values: dict[str, object] = {
        "id": uuid4(),
        "account_id": account_id,
        "project_id": project_id,
        "context_version": 1,
        "severity": "critical",
        "status": "open",
    }
    values.update(overrides)
    return ScopeReadinessGap(**values)  # type: ignore[arg-type]


def test_open_critical_gap_blocks_current_context() -> None:
    account_id, project_id = uuid4(), uuid4()
    decision = ScopeReadinessPolicy().evaluate(
        account_id=account_id,
        project_id=project_id,
        context_version=1,
        gaps=[_gap(account_id, project_id)],
    )

    assert decision.ready_for_share is False
    assert decision.reason_code == "critical_gap_open"
    assert len(decision.blocking_gap_ids) == 1


@pytest.mark.parametrize("status", ["resolved", "dismissed"])
def test_explicit_human_resolution_is_non_blocking(status: str) -> None:
    account_id, project_id = uuid4(), uuid4()
    decision = ScopeReadinessPolicy().evaluate(
        account_id=account_id,
        project_id=project_id,
        context_version=1,
        gaps=[_gap(account_id, project_id, status=status)],
    )

    assert decision.ready_for_share is True
    assert decision.reason_code == "no_open_critical_gaps"
    assert decision.blocking_gap_ids == ()


def test_non_critical_and_historical_gaps_do_not_block() -> None:
    account_id, project_id = uuid4(), uuid4()
    decision = ScopeReadinessPolicy().evaluate(
        account_id=account_id,
        project_id=project_id,
        context_version=2,
        gaps=[
            _gap(account_id, project_id, severity="high", context_version=2),
            _gap(account_id, project_id, context_version=1),
        ],
    )

    assert decision.ready_for_share is True


def test_blocking_ids_are_deterministic_and_duplicate_evidence_rejected() -> None:
    account_id, project_id = uuid4(), uuid4()
    first = _gap(account_id, project_id)
    second = _gap(account_id, project_id)
    decision = ScopeReadinessPolicy().evaluate(
        account_id=account_id,
        project_id=project_id,
        context_version=1,
        gaps=[second, first],
    )
    assert decision.blocking_gap_ids == tuple(sorted((first.id, second.id), key=str))

    with pytest.raises(ScopeReadinessValidationError):
        ScopeReadinessPolicy().evaluate(
            account_id=account_id,
            project_id=project_id,
            context_version=1,
            gaps=[first, first],
        )


def test_tenant_and_future_context_evidence_fail_closed() -> None:
    account_id, project_id = uuid4(), uuid4()
    with pytest.raises(ScopeReadinessValidationError):
        ScopeReadinessPolicy().evaluate(
            account_id=account_id,
            project_id=project_id,
            context_version=1,
            gaps=[_gap(uuid4(), project_id)],
        )
    with pytest.raises(ScopeReadinessValidationError):
        ScopeReadinessPolicy().evaluate(
            account_id=account_id,
            project_id=project_id,
            context_version=1,
            gaps=[_gap(account_id, project_id, context_version=2)],
        )
