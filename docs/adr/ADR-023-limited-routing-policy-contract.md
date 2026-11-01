# ADR-023 — Limited Provider-Neutral Routing Policy Contract

- Status: Accepted for Sprint 1 G04 contract boundary
- Date: 2026-09-05
- Scope: Worker Application routing-policy boundary
- Source: [Aria AI — AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk)
- Supporting source: [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk)

## Decision

Sprint 1 G04 adds a provider-neutral routing contract with exactly three canonical tiers:

```text
cheap | standard | premium
```

The Application boundary exposes:

```text
RoutingPolicy.resolve(task_type, context) -> RoutingDecision
RoutingDecision.tier -> cheap | standard | premium
```

`task_type` remains an opaque string. `context` remains an opaque structured mapping. A missing
policy fails explicitly with `routing_policy_required`; no tier is selected implicitly.

## Non-decisions

- No task-type vocabulary or task-to-tier mapping is introduced.
- No default tier is introduced.
- No automatic premium escalation, trigger, threshold, count, or budget rule is introduced.
- No fallback behavior or provider selection is introduced.
- No provider name, model name, SDK, credential, endpoint, or provider-specific type crosses the
  Application boundary.
- G02/G03 concrete provider adapters remain Deferred/Blocked pending Provider Selection and an
  Evaluation Gate.

The existence of the `premium` tier is a contract capability only; runtime escalation remains
Deferred.

## Consequences

- Workflows can require an explicit policy without coupling Domain/Application to a provider.
- Later routing semantics can be added through a reviewed contract change without inventing a
  default behavior in this increment.
- A concrete Provider Selection Decision remains required before adapter and routing runtime work
  can be considered production-ready.

**Unapproved assumptions:** None
