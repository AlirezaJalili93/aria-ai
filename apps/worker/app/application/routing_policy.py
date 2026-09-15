from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from .ai_execution import StructuredMapping

RoutingTier = Literal["cheap", "standard", "premium"]


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Provider-neutral routing result containing only the approved tier."""

    tier: RoutingTier

    def __post_init__(self) -> None:
        if self.tier not in {"cheap", "standard", "premium"}:
            raise ValueError("routing decision tier must be cheap, standard, or premium")


class RoutingPolicy(Protocol):
    """Application boundary for resolving a provider-neutral routing tier."""

    def resolve(self, task_type: str, context: StructuredMapping) -> RoutingDecision: ...


class RoutingPolicyRequiredError(RuntimeError):
    """Raised when a workflow attempts routing without an explicit policy."""

    code = "routing_policy_required"

    def __init__(self) -> None:
        super().__init__(self.code)


def resolve_routing_policy(
    policy: RoutingPolicy | None,
    task_type: str,
    context: StructuredMapping,
) -> RoutingDecision:
    """Resolve a tier or fail explicitly when no policy was supplied."""

    if policy is None:
        raise RoutingPolicyRequiredError()
    return policy.resolve(task_type, context)
