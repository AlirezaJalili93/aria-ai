"""Compatibility import for the shared, framework-free K02 policy."""

from aria_backend_application.scope_readiness import (
    ScopeReadinessDecision,
    ScopeReadinessGap,
    ScopeReadinessGapSeverity,
    ScopeReadinessGapStatus,
    ScopeReadinessPolicy,
    ScopeReadinessReason,
    ScopeReadinessValidationError,
)

__all__ = (
    "ScopeReadinessDecision",
    "ScopeReadinessGap",
    "ScopeReadinessGapSeverity",
    "ScopeReadinessGapStatus",
    "ScopeReadinessPolicy",
    "ScopeReadinessReason",
    "ScopeReadinessValidationError",
)
