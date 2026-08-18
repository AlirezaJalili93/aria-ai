# Development Record: 0008 Structured Logging & Correlation

- Increment ID: `0008-structured-logging`
- Date: 2026-08-18
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-A04 — Structured Logging & Correlation`
- [Test report](./test-report.md)

## Scope

Implement the documented observability foundation shared by API and Worker: structured JSON events, request and correlation identifiers, versioned job trace metadata, worker/provider propagation context, release labels, and strict allowlist logging. This increment does not implement a queue consumer, outbox publisher, AI provider adapter, product endpoint, metric backend, alerting platform, or distributed tracing product assigned to later stories.

## Source Documents

- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, story `S1-A04`.
- Google Drive `05 — Aria AI — Observability & Alerting Runbook v1.0`, sections 3–6, 31, 34, 39, and 40.
- Google Drive `11 — Aria AI — Coding Standards & Engineering Conventions v1.0`, sections 20–23.
- Google Drive `01 — Aria AI — API Contract Specification v1.0`, header and safe logging contracts.
- Google Drive `03 — Aria AI — Security & Threat Model v1.0`, mandatory sensitive-log test baseline.
- Google Drive `07 — Aria AI — Environment & Configuration Specification v1.0`, logging and release-label configuration.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md), and [document-driven development policy](../../governance/document-driven-development.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-027 | Every HTTP request has safe request/correlation IDs | API observability middleware and UUID resolver | TC-0801, TC-0802 |
| REQ-028 | Correlation propagates API → job → worker → provider | Framework-neutral trace contexts and versioned JSON contract | TC-0803, TC-0804 |
| REQ-029 | Production-compatible logs are structured JSON with service/environment/version fields | Strict structured event logger; API and Worker bindings | TC-0801, TC-0805 |
| REQ-030 | Secrets, headers, query values, raw project content, prompt/response, and share tokens are never logged | Field allowlist, safe serializers, route templates, negative tests | TC-0806 |
| REQ-031 | Runtime logging follows configured levels and does not use `print()` | Standard-library logger and Worker startup migration | TC-0805, TC-0807 |
| REQ-032 | Shared contract remains framework-neutral and architecture-safe | `packages/observability` plus language-neutral job context schema | TC-0804, TC-0808 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- The canonical API specification states that identifiers are UUIDs, while the coding standard requires accepting only safe request/correlation identifiers. Client header values are therefore preserved only when they parse as UUIDs; malformed values are treated as absent and replaced with generated UUIDs.
- Local human-readable logs are documented as allowed, not required. One JSON format is used in every environment so the security and contract behavior stays identical; `LOG_LEVEL` remains environment-specific.
- No queue or provider implementation is inferred. `JobTraceContext` and `ProviderTraceContext` establish only the approved metadata boundary for later adapters.

## Changes

- Added the typed, framework-neutral `aria-observability` package with context-local binding, safe HTTP ID resolution, versioned job metadata, provider propagation metadata, and JSON event output.
- Added API middleware that returns `X-Request-ID` and `X-Correlation-ID`, logs matched route templates rather than raw paths, measures duration, and records only status/error codes.
- Migrated Worker startup from `print()` to `worker.runtime_started` JSON with service, environment, application version, release commit, and truthful queue-adapter state.
- Added `job-trace-context.schema.json`; it rejects additional fields and carries no job payload or raw content.
- Added negative sensitive-log tests and CI contract coverage; shared source now participates in repository lint, type-check, and build gates.
- Updated runtime READMEs and both uv lockfiles for the internal package.

## Architecture and Design Decisions

- The correlation primitives are a non-deployable shared package with no FastAPI, broker, provider, persistence, or Domain dependency. Framework adapters remain inside their owning deployables.
- Context travels explicitly in a versioned job envelope and through a context-local runtime binding; no hidden mutable global business state was introduced.
- Structured logging uses a positive allowlist. Unknown fields are discarded instead of recursively serializing caller-controlled mappings.
- No ADR is required because this implements the already-approved observability baseline and existing shared-package boundary; it does not change a deployable, data model, vendor, or architecture decision.

## Structure Preservation

- API middleware remains Presentation/framework code and does not enter Domain or Application packages.
- Worker startup remains queue-neutral; no consumer, task handler, retry policy, or readiness claim was added.
- Shared contracts remain in `packages/contracts`; runtime primitives remain in a non-deployable package.
- No product route, mutation, database write, tenant authorization path, outbox behavior, or provider SDK was introduced.

## Senior Review

- **Resolved — raw path leakage:** unmatched routes initially fell back to the caller-controlled URL path. The fallback is now the constant `/<unmatched>`, while matched routes use framework templates.
- **Resolved — shared-code gate gap:** the first implementation linted/type-checked only deployable source. Repository scripts now include the shared observability source in API lint, type-check, and compile gates.
- **Resolved — typed-package boundary:** the internal wheel initially lacked a `py.typed` marker. It is now fully typed and passes strict MyPy.
- **Resolved — unsafe async metadata:** job task type and payload version now accept only bounded safe identifiers; UUID-bearing fields are parsed and canonicalized.
- **Resolved — legacy Worker contract:** the previous test expected human-readable `print()` output. It now asserts the documented JSON event and truthful runtime state.
- **Verified — secret minimization:** arbitrary fields, Authorization, query values, raw paths, project content, prompts, and share tokens are absent from emitted JSON.
- **Verified — architecture:** the shared package has no framework/infrastructure dependency and Domain code remains untouched.

## Verification

- API tests: 28 passed; the known FastAPI/httpx TestClient deprecation warning remains non-blocking.
- Worker tests: 14 passed.
- CI/contract tests: 14 passed.
- Repository-wide lint, strict MyPy/TypeScript checks, Web/API/Worker builds, dependency scan, and secret scan passed after the review corrections.
- `npm run validate` passes every architecture/content check for this increment but remains globally non-zero only because `0007-staging-runtime` truthfully retains `PENDING` hosted Render evidence.

## Remaining Risks

- Hosted Render verification is still blocked by the provider's incomplete card-verification state; S1-A03 remains open and no hosted API/Worker log evidence is claimed here.
- Queue delivery, outbox correlation, provider request IDs, metrics, dashboards, and alerts require their explicitly assigned later stories. This increment provides their trace contract only.
- FastAPI 0.141 emits the existing upstream TestClient/httpx deprecation warning; changing the HTTP client stack requires a separately documented dependency migration.
