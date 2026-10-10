# Development Record: 0051 — Clarification Domain and API

- **Status:** COMPLETE
- **Increment:** S1-J03-A
- **Source sync date:** 2026-09-09
- **Completed:** 2026-09-12
- [Test report](./test-report.md)

## Scope

Implement the owner-approved J03-A Clarification question lifecycle, immutable human Resolution
audit record, deterministic Gap completion evaluator, explicit Gap dismissal command, tenant-safe
PostgreSQL persistence, public API contracts, provider-neutral AI-04 question-generation port and
safe operational events.

J03-B semantic answer validation, answer-to-Context persistence, Context version advancement,
Requirement regeneration, semantic deduplication, guest identity and real-provider AI-04 quality
evaluation remain explicit non-goals.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J03
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — human-in-the-loop Gap resolution
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — superseded Clarification baseline
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-04 and human resolution
- [Backend API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — authorization and superseded combined endpoint
- [ADR-038 — Clarification Question and Human Resolution Contract](../../adr/ADR-038-clarification-domain-api.md)
- Owner-approved J03-A frozen contract and refinements dated 2026-09-09.

The Google Drive documents above were read on the source sync date. Official Supabase changelog,
RLS guidance and PostgreSQL best-practice checks were used as engineering safety references; they
do not add product behavior.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-5101 | Approved Clarification lifecycle and creator invariant | `domain/clarification.py`, models, migration | TC-5101 |
| REQ-5102 | One terminal auditable human Resolution | Resolution domain/model and unique constraint | TC-5102 |
| REQ-5103 | Resolution-specific answer shape and human actor/author distinction | Domain, API validation, DB checks | TC-5103 |
| REQ-5104 | Resolve Gap only after no open Clarification remains | `ClarificationService.resolve_question` | TC-5104 |
| REQ-5105 | Ignore Clarification differs from explicit Gap dismissal | Resolution flow and `dismiss_gap` command | TC-5105 |
| REQ-5106 | Separate create/edit/resolve/dismiss endpoints | Clarification router and OpenAPI | TC-5106 |
| REQ-5107 | Idempotent creates and optimistic concurrency | Existing idempotency repository and CAS writes | TC-5107 |
| REQ-5108 | Deterministic normalization and exact-open duplicate rejection | Shared normalizer and partial unique index | TC-5108 |
| REQ-5109 | Tenant consistency, RESTRICT history and safe 404 | Composite FKs, repository filters, router mapping | TC-5109 |
| REQ-5110 | Provider-neutral AI-04 boundary only | `clarification_question_generation.py` | TC-5110 |
| REQ-5111 | Content-safe structured observability | Service events and logging allow-list | TC-5111 |
| REQ-5112 | Documentation, architecture and quality gates | ADR-038, mirror and this record/report | TC-5112 |

## Assumptions and Clarifications

- The simple Data Dictionary answer record and combined API operation are explicitly superseded
  by the owner-approved J03-A two-entity/two-command contract.
- The Sprint 1 deterministic Gap resolution rule is exactly: no Clarification with `status=open`
  remains for the open Gap.
- Question creation uses the repository-wide mutating-create idempotency strategy; Resolution
  registration uses the explicitly required `Idempotency-Key`.
- No semantic claim is made about whether a provided answer resolves the underlying business Gap;
  J03-A records human actions and applies only the frozen deterministic state rule.

**Unapproved assumptions:** None

## Changes

- Added immutable Clarification/Resolution domain values, answer-shape validation and shared
  deterministic Persian-safe text normalization.
- Added provider-neutral AI-04 question generation port with deterministic Fake contract coverage.
- Added Application service and ports for create, edit, resolve and explicit Gap dismiss commands.
- Added Alembic revision `0016_clarifications` with tenant composite FKs, RESTRICT deletion, closed
  checks, one-Resolution uniqueness, partial exact-open duplicate index, RLS and revoked public/Data
  API role authority.
- Added SQLAlchemy models, repository/UoW, FastAPI routes, stable error mapping and OpenAPI schemas.
- Added safe event metadata and negative checks preventing question/answer content in logs.
- Updated stale J01/J02 contract tests so they continue to forbid Gap detection/create APIs while
  accepting only the later owner-approved J03-A routes.
- Added ADR-038 and synchronized the developer-facing data-model mirror.

## Architecture and Design Decisions

ADR-038 is authoritative for this Increment. Domain and Application contain no FastAPI,
SQLAlchemy, Supabase client, Provider SDK, model name or Queue framework dependency. Transaction
ownership stays in Application/UoW; SQL, RLS and idempotency persistence remain Infrastructure.
No new deployable service, Provider selection, Context mutation or downstream regeneration path
was added.

## Structure Preservation

- Extended the existing modular-monolith `gaps` module without creating a cross-module write path.
- Reused the existing Tenant Context dependency, idempotency repository, database runtime and
  structured event facility.
- Preserved API/Application/Domain/Infrastructure layering and the existing Alembic linear head.
- Kept `question_text`/`answer_text` out of Jobs, Outbox, logs and metrics.
- Maintained PostgreSQL as the transactional source of truth; RLS is defense in depth and backend
  object authorization remains mandatory.

## Senior Review

**Status:** PASS.

The review checked state transitions, lock ordering, replay boundaries, CAS behavior, uniqueness,
cross-tenant hiding, deletion semantics, downgrade safety, RLS/direct grants, FK consistency,
provider neutrality and log field allow-lists. It found two stale predecessor tests that rejected
all `/gaps` paths after J03-A had approved specific routes; those assertions now narrowly prohibit
unapproved Gap creation/detection operations. It also found an import-order lint defect after the
normalizer extraction; that was corrected before the clean full run. No unresolved High or Medium
finding remains.

Supabase safety review confirmed new public-schema tables have RLS enabled and no direct
`PUBLIC`/`anon`/`authenticated` privileges, consistent with the direct SQLAlchemy application
access model. Migration upgrade/downgrade/re-upgrade and real constraint enforcement were tested
against PostgreSQL 16.

## Verification

Focused J03-A Domain/Application/API/PostgreSQL tests: 28/28 PASS. Contract CI: 140/140 PASS;
Eval: 24/24 PASS; Web: 26/26 PASS; API: 435/435 PASS with PostgreSQL; Worker: 57/57 PASS. Full
lint, Python/TypeScript typecheck and production build PASS. The explicit `npm test`, final record
validation, architecture validation, secret scan and diff checks are recorded in the linked test
report.

## Remaining Risks

- AI-04 real-provider quality and semantic question deduplication remain deferred to J03-B.
- J03-A does not make answers part of versioned Context or update Requirements; downstream state
  intentionally remains unchanged.
- Existing Starlette/httpx deprecation and local Pytest cache permission warnings are non-blocking
  repository/tooling warnings and did not alter test results.
