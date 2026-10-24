# Development Record: 0036 Limited Provider-Neutral Routing Policy Contract

- Increment ID: `0036-limited-routing-policy-contract`
- Date: 2026-09-05
- Owner: AI/Platform Engineering
- Related plan/issue: `S1-G04 — Limited Routing Policy Contract`
- [Test report](./test-report.md)

## Scope

Implement only the approved provider-neutral routing-policy contract:

- canonical tiers `cheap | standard | premium`;
- `RoutingPolicy.resolve(task_type, context) -> RoutingDecision`;
- opaque `task_type` and structured `context`;
- explicit `routing_policy_required` when no policy is supplied.

Explicit non-goals are task vocabulary, task-to-tier mapping, default tier, automatic escalation,
fallback, provider selection, provider/model names, SDKs, credentials, endpoints and runtime
budget/threshold semantics.

## Source Documents

- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk) — routing tiers and provider-neutral policy boundary; read 2026-09-05.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-G04 scope; read 2026-09-05.
- [Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit?usp=drivesdk) — Application/Infrastructure boundary; read 2026-09-05.
- [ADR-021 — Provider-Neutral AI Execution Port](../../adr/ADR-021-ai-execution-port.md) — existing AI port boundary.
- [ADR-022 — Generic Provider Adapter Port](../../adr/ADR-022-generic-provider-adapter-port.md) — concrete adapters remain deferred.
- [ADR-023 — Limited Provider-Neutral Routing Policy Contract](../../adr/ADR-023-limited-routing-policy-contract.md).
- Repository `AGENTS.md` — documentation-driven development and quality gates.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3601 | AI Workflow §7; owner-approved G04 contract | `RoutingTier` accepts exactly `cheap`, `standard`, `premium` | TC-3601 |
| REQ-3602 | AI Workflow §2–§7; G04 approval | `RoutingPolicy` resolves opaque `task_type` and structured context to `RoutingDecision` | TC-3602 |
| REQ-3603 | G04 approval | No task vocabulary or Task→Tier mapping is implemented | TC-3602 |
| REQ-3604 | G04 approval | Missing policy raises `routing_policy_required`; no implicit tier | TC-3603 |
| REQ-3605 | AI Workflow §2; ADR-022/023 | No provider/model/SDK type or concrete adapter is introduced | TC-3604 |

## Assumptions and Clarifications

The owner explicitly approved a contract-only G04 increment. `task_type` and `context` remain opaque;
runtime escalation, defaults, mapping, fallback and provider selection remain deferred.

**Unapproved assumptions:** None

## Changes

- Added `apps/worker/app/application/routing_policy.py` with `RoutingTier`, `RoutingDecision`,
  `RoutingPolicy`, explicit missing-policy error and resolution helper.
- Added unit tests in `apps/worker/tests/test_routing_policy.py`.
- Added contract tests in `scripts/test/routing-policy-contract.test.js` and registered them in
  `package.json`.
- Added ADR-023 and indexed it in `docs/adr/README.md`.

## Architecture and Design Decisions

- Routing remains in the Worker Application boundary and is provider-neutral.
- The policy returns only a tier; it does not select a provider or model.
- A missing policy is an explicit error, not an implicit `cheap` or `standard` choice.
- The `premium` tier is represented as a capability only; escalation rules are not runtime behavior.

## Structure Preservation

- The existing modular-monolith Worker Application boundary is preserved.
- No Domain/Application import of provider SDKs, queue clients, Redis, or persistence was added.
- `AIExecutionPort` and `ProviderAdapter` remain unchanged; G02/G03 remain Deferred/Blocked.
- No migration, deployable service, endpoint, secret, task vocabulary or external integration was added.

## Senior Review

- PASS: exactly three approved tiers are runtime-validated.
- PASS: `task_type` remains opaque and no mapping/default is introduced.
- PASS: missing policy fails explicitly with the approved stable code.
- PASS: no provider-specific dependency or selection logic crosses the Application boundary.
- PASS: focused tests, static checks, build, repository tests and architecture validation pass; final evidence is recorded in the test report.

## Verification

See [test-report.md](./test-report.md) for focused and repository-wide commands and results. The
final `npm test`, lint, typecheck, build, validate and diff checks all passed.

## Remaining Risks

- Task vocabulary, mapping, escalation/budget semantics, fallback and provider selection require
  later approved contracts and must not be inferred from this increment.
- G02/G03 remain blocked until Provider Selection and Evaluation Gate decisions are approved.

**Final status:** PASS
