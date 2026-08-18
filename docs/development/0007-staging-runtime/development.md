# Development Record: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-18
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-A03 — Staging Runtime`
- [Test report](./test-report.md)

## Scope

Establish the documented staging runtime for the existing three deployables: Web on Vercel, API and Worker on Render, and an isolated Supabase project for PostgreSQL, Auth, and private Storage. The increment also establishes the Redis-compatible durable queue configuration, environment-specific bindings, operational liveness/readiness contract, deployment metadata, smoke evidence, and strict secret separation. It does not implement product authentication flows, domain migrations, queue consumers, outbox publishing, storage upload behavior, or AI workflows assigned to later Sprint 1 stories.

## Source Documents

- Google Drive `Aria AI/34 — MVP Documentation Index & Traceability Matrix v1.0` and its source-of-truth order.
- Google Drive `Aria AI — Master Execution Plan`.
- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, story `S1-A03`.
- Google Drive `Aria AI — Environment & Configuration Specification v1.0`.
- Google Drive `Aria AI — Deployment & Release Runbook v1.0`.
- Google Drive `Aria AI — Final System Architecture v2.0` and `Accepted ADR Pack v1.0`.
- Google Drive `Aria AI — API Contract`, `Test Strategy`, `Security Baseline`, and `Definition of Ready / Definition of Done`.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md), and [document-driven development policy](../../governance/document-driven-development.md).
- User approvals on 2026-08-18: Supabase Free in Frankfurt (`eu-central-1`), Render API/Worker/Persistent Key Value in Frankfurt, target budget ceiling of USD 24/month subject to the selected instance types, root `/health/live` and `/health/ready`, and exclusion of AI providers from readiness.
- User-provided `ui-ux-pro-max.md` and `design-system.md`, plus repository `design-system/MASTER.md`, as unchanged UI quality guardrails.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-020 | S1-A03: Web, API, Worker, Postgres, Queue, Storage, and Auth staging environment | Vercel target, `render.yaml`, isolated Supabase project and private bucket | TC-0701, TC-0705, TC-0706 |
| REQ-021 | Approved operational endpoint contract | `GET /health/live` and `GET /health/ready`; OpenAPI response schemas | TC-0702, TC-0703 |
| REQ-022 | S1-A03 AC: staging URL | Hosted Vercel and Render URLs with TLS | TC-0705 |
| REQ-023 | Environment Specification: environment and secret separation | Typed settings, `sync: false` runtime values, public env allowlist, secret scan | TC-0704, TC-0706 |
| REQ-024 | Staging fail-fast configuration and production-like deployment | Pydantic hosted-environment validation, locked builds, CI-gated Render deploys | TC-0701, TC-0707 |
| REQ-025 | Runbook: health, smoke, rollback identity, and dependency isolation | Bounded DB probe, `RELEASE_COMMIT_SHA`, hosted smoke plan | TC-0702, TC-0703, TC-0705, TC-0707 |
| REQ-026 | Standing rule: development/test Markdown and senior review | This record, linked report, repository quality gates | TC-0708 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- Supabase staging location, Render location, budget treatment, and health contracts are copied from explicit user approval; they were not inferred.
- The target Render plans remain a ceiling proposal until the dashboard shows the actual instance-price breakdown and the user confirms the paid creation action.
- `/health/live` never checks a dependency. `/health/ready` checks validated runtime configuration, PostgreSQL, and a real Redis-compatible `PING`; it deliberately excludes AI providers.
- The storage bucket is private because the approved architecture specifies private S3-compatible storage. No object policy or upload flow is added by this story.
- No product endpoint, domain schema, queue consumer, storage object contract, authentication flow, or AI behavior is inferred from this infrastructure story.

## Changes

- Created the isolated Supabase project `aria-ai-staging` (`hqgfqlvfwflbazsuhazs`) in `eu-central-1`; Supabase reports `ACTIVE_HEALTHY`.
- Created and independently verified the private Supabase Storage bucket `aria-staging-project-content` with `public=false`.
- Added root operational routes `/health/live` and `/health/ready` plus matching OpenAPI contracts and dependency-isolation tests.
- Added an async SQLAlchemy/asyncpg PostgreSQL readiness adapter with a three-second deadline, sanitized failure result, and lifecycle disposal.
- Added a bounded Redis-compatible queue readiness adapter using the standard RESP `PING` contract without selecting the still-open queue framework.
- Replaced presence-only runtime strings with typed HTTP URLs, supported PostgreSQL/Redis DSNs, enumerated log levels, and a 40-hex release SHA. Credential-bearing values now use `SecretStr`, and validation errors hide inputs.
- Removed the undocumented Worker dependency on `AUTH_PROVIDER_URL`. Worker startup now reports `runtime-started queue_adapter_configured=false` and never claims job-processing readiness before a queue consumer exists.
- Added the repository-owned Render Blueprint for Frankfurt API, Worker, and Persistent Key Value, using Starter candidates, private-only queue access, `noeviction`, Journal + Snapshot persistence, locked builds, CI-gated deployment, and secret placeholders.
- Added deployment configuration tests and included them in the CI contract suite.
- Updated the API README and staging shell copy without adding a product feature.
- Hosted Vercel and Render deployment plus remote smoke evidence remain pending.

## Structure Preservation

- The documented deployables remain exactly `web`, `api`, and `worker`; no service or domain module was added.
- Health routers remain in API presentation code and the PostgreSQL probe remains in Infrastructure. Domain and Application packages do not import FastAPI, SQLAlchemy, Supabase, Render, or Vercel code.
- No cross-module write, mutating endpoint, event contract, migration, queue consumer, or AI-provider behavior is introduced.
- The queue remains a Redis-compatible infrastructure binding and never becomes a Domain or financial source of truth.
- UI remains RTL-first, token-driven, keyboard accessible, and structurally unchanged apart from honest staging-status copy.

## Senior Review

- **Resolved — readiness isolation:** liveness has no probe call; readiness checks the critical database and queue bindings concurrently and never calls an AI provider.
- **Resolved — bounded failure:** the first database probe had no deadline; it now returns sanitized `503` after a three-second timeout instead of allowing a health request to hang indefinitely.
- **Resolved — deploy safety:** API and Worker now use `autoDeployTrigger: checksPass`, locked dependency sync, and `--no-sync` startup to prevent runtime dependency drift.
- **Resolved — queue durability:** the Key Value resource is private-only, persistent, and uses `noeviction`, matching durable queue semantics.
- **Resolved — source-control confidentiality:** all credentials and runtime-derived URLs remain outside Git; the repository secret scanner also caught and removed a credential-shaped test fixture.
- **Resolved — typed configuration:** malformed HTTP URLs, unsupported PostgreSQL driver schemes, malformed Redis DSNs/database selectors, invalid log levels, and non-40-character release SHAs now fail before startup without echoing their values.
- **Resolved — Worker semantics/coupling:** the Worker no longer depends on the Auth provider without a documented use case and no longer emits a false `runtime-ready` claim.
- **Resolved — contract drift:** OpenAPI retains the documented `/api/v1` product base while overriding the two root operational routes; response schemas include environment, version, release SHA, DB/queue checks, and 503.
- **Verified — architecture:** operational transport and infrastructure concerns preserve modular-monolith dependency direction and add no deployable boundary.
- Hosted configuration, remote smoke, and final review remain open until the deployment actions complete.

## Verification

- API tests: 24/24 passed, including a real loopback RESP `PING`; Ruff and MyPy passed.
- Worker tests: 11/11 passed; Ruff and MyPy passed.
- Deployment/CI contract tests: 12/12 passed.
- Web/API/Worker production builds passed; repository lint and type-check passed.
- Secret scan inspected 109 publishable text files with zero findings after the fixture correction.
- Supabase project URL, region, health status, and private bucket state were independently read back.
- Hosted smoke and final full `npm test` / `npm run validate` evidence remain pending and will be recorded in [test-report.md](./test-report.md).

## Remaining Risks

- Render resources do not yet exist. Actual paid instance prices must be confirmed in the dashboard and remain at or below the approved target ceiling before creation.
- Supabase Free may pause after inactivity and does not provide production-grade backup/PITR; this is accepted only for Sprint 1 staging.
- Database and S3 credentials must be generated only at the action point and transmitted directly to the Render secret store; they must never enter source control, command output, or this evidence record.
- Hosted TLS, cross-platform connectivity, Vercel/Render URLs, deployment logs, and rollback SHA are not yet verified.
- The Worker process is intentionally not job-ready until the dedicated queue framework/consumer story and ADR are completed; this staging increment proves runtime/config binding only and reports that state explicitly.
- FastAPI 0.141 currently emits an upstream TestClient deprecation warning for httpx; it is non-blocking and requires a separately documented dependency migration when the approved stack adopts httpx2.
