# Development Record: 0021 Account Discovery and Project API

- Increment ID: `0021-account-discovery-project-api`
- Date: 2026-09-01
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-C02 — Project API`
- [Test report](./test-report.md)

## Scope

Implement the canonical pre-tenant Account Discovery query and tenant-authorized Project HTTP API:
create with persistent idempotency, tenant-scoped get/list, title-only optimistic update, and
owner/admin soft delete. Project description and public status transitions remain deferred.

## Source Documents

- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — synchronized 2026-09-01 at revision `AIroW37MdTGdhet8RugG-jB8HUHQlC1Smj_NaYCRAmbVNq93VcEUzD6dZlCHvAWSRmGZaFLGw-tyQSgJJIn6pkPpSPMSPjLcYi1JdAv6Pg`.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-C02`.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Project fields and vocabulary.
- [Access Control Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership and owner/admin delete authority.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — API, isolation, recovery and idempotency test families.
- Owner approval dated 2026-09-01 for the exact Account Discovery and S1-C02 contract.
- Repository `AGENTS.md`, architecture/governance mirrors, ADR-010 and corrected ADR-011.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-096 | Owner; API Contract | `GET /api/v1/accounts`, active memberships only, exact item/envelope | TC-2101, TC-2102 |
| REQ-097 | Owner; API Contract | Project create title/type only; trim and `1..255` title | TC-2103, TC-2104 |
| REQ-098 | Owner | mandatory persistent create idempotency and conflict semantics | TC-2105, TC-2106 |
| REQ-099 | Owner | keyset list ordered by `(created_at,id)` descending, limits 20/100 | TC-2107, TC-2108 |
| REQ-100 | Owner; Access Matrix | tenant-safe Project get/update/delete and non-enumerating 404 | TC-2109, TC-2110 |
| REQ-101 | Owner | title-only PATCH with `expected_updated_at` optimistic concurrency | TC-2111, TC-2112 |
| REQ-102 | Owner; API Contract | owner/admin soft delete; deleted resources invisible to ordinary API | TC-2113, TC-2114 |
| REQ-103 | Owner | safe structured mutation/security events with required identifiers | TC-2115 |
| REQ-104 | Repository governance | OpenAPI, implementation and canonical contract remain aligned | TC-2116 |

## Assumptions and Clarifications

The owner explicitly resolved Account Discovery naming/envelope, deferred `description`, locked the
Project request fields, title normalization, idempotency replay/conflict, cursor basis and limits,
safe-not-found behavior, optimistic concurrency and delete authorization. Status mutation remains
outside this public API until a transition matrix is approved.

**Unapproved assumptions:** None

## Changes

- Added the pre-tenant `GET /api/v1/accounts` query over a dedicated Identity Application contract
  and SQLAlchemy adapter. The query selects only active Memberships and the router returns only
  Account `id` and Membership `role` in the standard collection envelope.
- Added Project create/get/list/update/delete routers and synchronized the repository OpenAPI mirror.
  Request models forbid undocumented fields; `description` and public status mutation are absent.
- Added trim plus `1..255` Title validation, opaque keyset cursors, default/max list limits and
  tenant-safe resource lookup behavior.
- Added M003 `project_create_requests`: Account-scoped persistent reservations, normalized request
  hash, deferred Project FK and an immutable response snapshot provide concurrency-safe exact replay.
- Added atomic `expected_updated_at` comparison to Project update and mapped stale writes to
  `409 VERSION_CONFLICT`.
- Extended structured events with UUID-validated `actor_id` and safe attempted `project_id` support;
  Project content remains outside the logging allowlist.
- Added contract, Application, HTTP, privacy and real PostgreSQL tests, including concurrent create,
  migration recovery, active-only discovery and equal-timestamp keyset ordering.

## Architecture and Design Decisions

ADR-011 is corrected to the canonical `/api/v1/accounts` query. The idempotency reservation is
persisted transactionally beside Project creation. Its uniqueness is Account plus key—not actor plus
key—so retries preserve one result across authorized members of the selected tenant. A deferred FK
allows the reservation to win before Project insertion while enforcing referential integrity at
commit. No new deployable or cross-module write is added.

## Structure Preservation

- Identity and Projects remain separate modules. Account Discovery is an Identity read contract;
  Project writes continue through the Projects Application service and Project UoW.
- Domain code imports no FastAPI, SQLAlchemy or provider code. API models and cursor transport remain
  in the API layer; SQL and PostgreSQL conflict handling remain in Infrastructure.
- Existing M002 is unchanged; persistent idempotency is an immutable M003 follow-up. RLS is enabled
  and Data API roles receive no privileges or policies.
- The established route prefix, error envelope, tenant dependency, modular-monolith topology and
  single API deployable are preserved.

## Senior Review

- **HIGH — corrected:** the first reservation design scoped uniqueness by Account, actor and key.
  This could allow two active members to create duplicates with the same tenant key. Uniqueness is
  now exactly `(account_id, idempotency_key)`; a cross-actor replay test locks the correction.
- **HIGH — concurrency:** PASS. Reservation-first insertion uses `ON CONFLICT DO NOTHING`; the loser
  waits for the winning transaction and reads the committed snapshot. A deferred FK prevents an
  orphan reservation at commit. Two real concurrent PostgreSQL creates produced one Project.
- **Authorization/isolation:** PASS. Every Project route uses the existing active Tenant dependency;
  missing, deleted and cross-tenant resources converge on safe 404. Only owner/admin may delete.
- **Optimistic concurrency:** PASS. The read check gives a deterministic conflict and the SQL update
  repeats the timestamp predicate atomically, closing the time-of-check/time-of-use race.
- **Privacy/observability:** PASS. Approved identifiers and statuses are emitted; Title, JWT,
  Idempotency-Key, payload and response snapshot are never logged.
- **Contract/scope:** PASS. `/account-contexts`, Project `description` and public status mutation are
  absent. No undocumented Product field, UI behavior or endpoint was introduced.
- **Migration/recovery:** PASS against PostgreSQL 18. Upgrade, downgrade/re-upgrade, RLS/grants,
  deferred FK, Account discovery, idempotency and keyset behavior passed.

## Verification

All focused tests, 19 real PostgreSQL integration tests, monorepo lint/typecheck, 53 CI contract
tests, 12 Web tests, 16 Worker tests, production builds and both security scans passed. The final
mandatory `npm test` and `npm run validate` passed. GitHub PR #15 then passed Quality, Security
baseline and the Vercel Preview deployment; details are recorded in the linked test report.

## Remaining Risks

- Main/staging migration and post-merge smoke evidence remain gated on PR approval and merge; PR
  Quality, Security and Vercel Preview checks are complete.
- Idempotency reservation retention has no cleanup policy in S1-C02. No automatic deletion was
  invented; a future retention requirement may add an explicit maintenance policy.
