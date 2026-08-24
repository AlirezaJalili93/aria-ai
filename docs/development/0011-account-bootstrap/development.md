# Development Record: 0011 Account Bootstrap

- Increment ID: `0011-account-bootstrap`
- Date: 2026-08-24
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B02 — Account Bootstrap`
- Architecture decision: [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md)
- [Test report](./test-report.md)

## Scope

Implement the documented first-valid-login Account Bootstrap path: project the verified external
subject into `profiles`, create one Account, and create its active Owner Membership atomically. Add
an implicit FastAPI dependency after JWT verification, idempotent resolution for existing users,
concurrency protection, structured safe events, and the approved M000/M001 Alembic migrations.

Membership selection for multiple accounts (`S1-B03`), current Tenant Context (`S1-B04`), `/me`, a
dedicated bootstrap endpoint, login UI, email projection, invitations, membership removal, and RLS
policy selection (`M010`) are explicitly out of scope.

## Source Documents

Canonical Google Drive documents reviewed and synchronized on 2026-08-24:

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-B02`.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Identity/Account flow and Migration Batch 1.
- [Production Data Architecture & Database Schema v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — identity projection and database defaults.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — exact Profile, Account, and Membership fields.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — M000/M001, constraints, indexes, and rollback tests.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — identity boundary and no bootstrap endpoint.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — Membership status authority.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — migration, Identity, concurrency, and E2E coverage.
- [Coding Standards & Engineering Conventions v1.0](https://docs.google.com/document/d/1aDMdM0VXYf6widpZL5bnZkyzoV98yxXHaAGytiDiRjo/edit) — UoW, layering, SQLAlchemy, and migration conventions.
- [Dependency & Vendor Register v1.0](https://docs.google.com/document/d/1AVZdOzMahLmNL9c38q9DObuR1C4R787ROc85FBnLgHE/edit) — Alembic as the approved migration dependency.
- Owner clarification dated 2026-08-22 approving Membership statuses, Profile schema, implicit
  bootstrap dependency, transaction/concurrency guardrails, event names, and required test cases.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md),
  [data model mirror](../../architecture/data-model.md), and
  [document-driven development policy](../../governance/document-driven-development.md).
- Current official Supabase changelog, User Management, RLS, and Data API security documentation
  reviewed on 2026-08-24; current Alembic 1.19 documentation and package metadata reviewed the same day.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-047 | S1-B02 flow | Profile → Account → active Owner Membership bootstrap use case | TC-1101 |
| REQ-048 | Owner clarification: exact Profile schema and no Email | M001 migration and Identity persistence model | TC-1102 |
| REQ-049 | Access Control precedence and owner clarification | `active\|invited\|suspended`; suspended is not deletion | TC-1103 |
| REQ-050 | S1-B02 and owner idempotency guardrail | Existing bootstrap resolves read-only without writes | TC-1104 |
| REQ-051 | Owner concurrent-request guardrail | Profile PK conflict gate plus DB uniqueness constraints | TC-1105 |
| REQ-052 | Owner transaction guardrail | Application UoW commits Profile, Account, Membership together | TC-1106 |
| REQ-053 | Owner layering guardrail and Architecture v2 | FastAPI Dependency → Application Use Case → Ports → SQLAlchemy Infrastructure | TC-1107 |
| REQ-054 | Owner structured logging contract | started/completed/resolved/failed safe events | TC-1108, TC-1109 |
| REQ-055 | Owner implicit dependency approval | `require_bootstrapped_identity` after JWT verification; no route added | TC-1110 |
| REQ-056 | Migration Plan M000/M001 and Dependency Register | Alembic revision chain, constraints, indexes, upgrade/downgrade | TC-1111, TC-1112 |

## Assumptions and Clarifications

The owner resolved the documentation conflicts on 2026-08-22: Membership uses
`active|invited|suspended`; Profile stores no Email and uses DB-enforced `locale='fa-IR'`; bootstrap
is implicit and has no endpoint. The owner also required atomicity, concurrency safety through DB
uniqueness, no writes on resolution, clean layering, four named events, and five priority tests.

Detailed Data Dictionary is used for exact fields, while Access Control is authoritative for the
authorization-sensitive Membership status vocabulary as explicitly directed by the owner.

**Unapproved assumptions:** None

## Changes

- Added the Alembic M000/M001 revision chain and pinned Alembic 1.19.0. M001 creates the approved
  Account, Profile, and Membership projection with database defaults (including the documented
  Account `gen_random_uuid()` default), checks, foreign keys, unique constraints, indexes, and RLS
  enabled without prematurely defining M010 tenant policies.
- Added a shared async SQLAlchemy runtime and kept readiness compatible with either a database URL
  or the shared engine.
- Added the provider-neutral Identity domain vocabulary, Application ports/UoW contract, and
  `BootstrapAccountUseCase`.
- Implemented concurrency-safe bootstrap with `INSERT ... ON CONFLICT DO NOTHING RETURNING` on the
  Profile primary key. The winning transaction creates and commits the full aggregate; a concurrent
  loser resolves the committed Membership instead of creating another Account.
- Added SQLAlchemy infrastructure models, repository, and Unit of Work. The existing-identity path
  executes reads only and performs no commit or mutation.
- Added `require_bootstrapped_identity` after the existing JWT dependency and the approved safe
  structured events. No public route was introduced.
- Added a stable 403 `MEMBERSHIP_REQUIRED` mapping for an existing identity with no active
  Membership; suspended Memberships remain persisted and are not treated as deletion.
- Added PostgreSQL service configuration to CI and contract, unit, dependency, concurrency,
  rollback, schema, and migration-cycle tests.

## Architecture and Design Decisions

Alembic is recorded in ADR-008 because the accepted ADR pack treats migration strategy as an
architecture-critical decision. No new deployable, provider, endpoint, or Domain boundary is added.

## Structure Preservation

- Identity remains inside the modular monolith and follows API → Application → Domain/Ports with
  Infrastructure implementing persistence.
- Account selection and Tenant Context remain reserved for S1-B03/S1-B04.
- M001 enables deny-by-default RLS because the tables live in Supabase's exposed `public` schema;
  M010 policy selection is not pulled forward and no Data API grant is introduced.
- No Email, credential, Auth metadata, client-supplied Account ID, or new public response is added.

## Senior Review

Senior review was completed after the implementation and produced these findings:

1. **Resolved — transactional FK ordering:** the first PostgreSQL run showed SQLAlchemy could emit
   Membership before Account because the persistence models intentionally have no ORM relationship.
   The repository now flushes Account explicitly before adding Membership; the real PostgreSQL
   first-request and concurrency cases pass.
2. **Resolved — constraint naming:** the first migration run exposed double-prefixed check names
   under the repository naming convention. M001 now supplies semantic base names and the generated
   PostgreSQL names are asserted by integration tests.
3. **Resolved — Supabase exposure boundary:** the approved tables are in `public`; M001 therefore
   enables RLS on all three tables. No undocumented policy or Data API grant was invented, so access
   stays deny-by-default until the documented M010 increment.
4. **Verified — concurrency and atomicity:** Profile PK conflict serialization plus database
   uniqueness creates one aggregate under two simultaneous requests; forced Account failure rolls
   back Profile and Membership.
5. **Verified — no-write resolution:** PostgreSQL row transaction identifiers are unchanged across
   the repeated-request path.
6. **Verified — boundary and privacy:** Domain/Application contain no framework or SQLAlchemy
   imports; the FastAPI dependency contains no persistence logic; logs include no JWT, Email, raw
   subject, claims, or Profile data; no `/bootstrap` or `/me` endpoint exists.
7. **Verified — structure preservation:** account selection and Tenant Context are not implemented
   early. A single active Membership may enrich trace context; multiple memberships are returned to
   the future selection story without arbitrary selection.
8. **Resolved — Account identifier default:** the refreshed Production Data Architecture requires
   `accounts.id DEFAULT gen_random_uuid()`. The SQLAlchemy model, M001 revision, contract scan, and
   real PostgreSQL default-insert test now enforce it while the Application may still supply an ID.
9. **Verified — event correlation:** create, resolve, and failure tests now assert `request_id`,
   `correlation_id`, and `duration_ms`; logs still exclude JWT, Email, raw subject, claims, and
   Profile content.

## Verification

The final technical verification passed:

- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test:ci` — 27 passed.
- `npm run test:web` — 4 passed.
- `npm run test:api` with real PostgreSQL — 71 passed.
- `npm run test:worker` — 14 passed.
- `npm run build` — PASS for Web, API, and Worker.
- `npm run scan:dependencies` — no blocking vulnerabilities.
- `npm run scan:secrets` — 166 publishable text files inspected after temporary test-database
  cleanup, PASS.
- Final aggregate `npm run quality` — PASS after the documented lint correction.

- Repository-wide `npm test` — PASS (Development Records 6, CI/contract 27, Web 4, API 71, Worker
  14; 122 total).
- `npm run validate` — PASS; all 22 architecture and development-record checks passed.

## Remaining Risks

- M010 RLS policies are deliberately not implemented in S1-B02. Until that documented increment,
  direct Data API access to the new tables remains deny-by-default.
- Migration behavior is proven against a clean local PostgreSQL 18 instance and CI is configured
  for PostgreSQL 16. Hosted Supabase application is not claimed as evidence for this increment.
- FastAPI's current test client emits one upstream deprecation warning. The sandbox also cannot
  create pytest cache directories under the existing virtual environments; neither warning affects
  execution or Account Bootstrap evidence.
