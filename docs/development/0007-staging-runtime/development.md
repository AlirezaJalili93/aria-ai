# Development Record: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-17
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-A03 — Staging Runtime`
- [Test report](./test-report.md)

## Scope

Establish the documented staging runtime for the existing three deployables: Web on Vercel, API and Worker on Render, and an isolated Supabase project for PostgreSQL, Auth, and Storage. The increment also prepares the documented Redis-compatible queue, environment-specific configuration, operational health/readiness contract, deployment metadata, smoke evidence, and strict secret separation. It does not implement product authentication flows, database domain migrations, queue consumers, outbox publishing, storage upload behavior, or AI workflows assigned to later Sprint 1 stories.

## Source Documents

- Google Drive `Aria AI/Development/Engineering Planning/Aria AI — Sprint 1 Technical Backlog v1.0`, story `S1-A03`.
- Google Drive `Aria AI — Environment & Configuration Specification v1.0`.
- Google Drive `Aria AI — Deployment & Release Runbook v1.0`.
- Google Drive `Aria AI — Accepted ADR Pack v1.0`, especially ADR-006, ADR-011, ADR-026, ADR-030, ADR-032, and ADR-033.
- Google Drive `Aria AI — Final System Architecture v2.0`.
- Google Drive `Aria AI — Backup, Restore & Disaster Recovery Plan v1.0`.
- Google Drive `Aria AI — SLO, Error Budget & Reliability Policy v1.0`.
- Repository `AGENTS.md` and [system architecture](../../architecture/system-architecture.md).
- [Document-driven development policy](../../governance/document-driven-development.md).
- User approvals on 2026-08-17: isolated Supabase staging project, existing Vercel team, and a repository-owned Render Blueprint.
- User-provided `ui-ux-pro-max.md` and `design-system.md`, plus repository `design-system/MASTER.md`, as UI quality guardrails.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-020 | S1-A03 scope: Web, API, Worker, Postgres, Queue, Storage, and Auth staging environment | Pending implementation and hosted evidence | TC-0701, TC-0705, TC-0706 |
| REQ-021 | S1-A03 AC: health/readiness endpoint | Pending approved path and API contract implementation | TC-0702, TC-0703 |
| REQ-022 | S1-A03 AC: staging URL | Pending Vercel/Render deployment | TC-0705 |
| REQ-023 | S1-A03 AC and Environment Specification: environment and secret separation | Typed settings, public env allowlist, platform secret stores, isolation tests | TC-0704, TC-0706 |
| REQ-024 | Environment Specification: staging fail-fast config and production-like deploy flow | Pending runtime configuration and deployment metadata | TC-0701, TC-0704 |
| REQ-025 | Runbook: liveness/readiness, smoke, observability sanity, rollback evidence | Pending tests and deployment evidence | TC-0702, TC-0703, TC-0705, TC-0707 |
| REQ-026 | Standing rule: development/test Markdown and senior review | This record, linked report, repository validation | TC-0708 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- The user approved creation of an isolated Supabase staging project in the only connected organization; Supabase requires a separate explicit cost confirmation before creation.
- The user approved the only connected Vercel team and a repository-owned Render Blueprint.
- Exact Supabase region, health/readiness paths, and Redis-compatible queue resource are awaiting explicit clarification because the canonical documents intentionally do not lock those implementation details.
- No product endpoint, schema, queue consumer, storage bucket contract, or auth flow is inferred from the infrastructure story.

## Changes

- Development and test evidence was initialized before implementation.
- Remaining changes are pending approved clarifications and implementation.

## Structure Preservation

- The three documented deployables remain `web`, `api`, and `worker`; this increment does not add a service.
- API operational endpoints remain outside domain modules and do not introduce framework imports into Domain or Application packages.
- No cross-module write, mutation endpoint, business event, queue consumer, migration, or AI provider behavior is introduced.
- UI remains RTL-first, token-driven, accessible, and compatible with the existing design-system baseline.

## Senior Review

- Pending after implementation and verification.

## Verification

- Pending. Actual commands and hosted smoke evidence will be recorded in [test-report.md](./test-report.md).

## Remaining Risks

- Hosted resource creation and smoke verification remain blocked until the explicitly required Supabase cost/region confirmation and the document-open operational choices are resolved.
