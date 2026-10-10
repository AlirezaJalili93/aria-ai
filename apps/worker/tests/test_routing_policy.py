from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.routing_policy import (
    RoutingDecision,
    RoutingPolicyRequiredError,
    resolve_routing_policy,
)


@pytest.mark.parametrize("tier", ["cheap", "standard", "premium"])
def test_routing_decision_accepts_only_canonical_tiers(tier: str) -> None:
    decision = RoutingDecision(tier=tier)  # type: ignore[arg-type]

    assert decision.tier == tier


def test_routing_decision_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="routing decision tier"):
        RoutingDecision(tier="unknown")  # type: ignore[arg-type]


@dataclass(frozen=True)
class FixedPolicy:
    decision: RoutingDecision

    def resolve(self, task_type: str, context: dict[str, object]) -> RoutingDecision:
        assert task_type == "opaque-task-type"
        assert context == {"opaque": "context"}
        return self.decision


def test_policy_resolves_opaque_task_type_without_mapping() -> None:
    decision = resolve_routing_policy(
        FixedPolicy(RoutingDecision("standard")),
        "opaque-task-type",
        {"opaque": "context"},
    )

    assert decision == RoutingDecision("standard")


def test_missing_policy_fails_explicitly() -> None:
    with pytest.raises(RoutingPolicyRequiredError) as error:
        resolve_routing_policy(None, "opaque-task-type", {})

    assert error.value.code == "routing_policy_required"
