# Development Record: 0025 Text Context API

- Increment ID: `0025-text-context-api`
- Date: 2026-09-05
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-D02 — Text Context Input API`; first transactional consumer of
  `S1-E01` and `S1-E03` persistence
- [Test report](./test-report.md)

## Scope

Implement the approved tenant-authorized endpoint for exact text Context ingestion. Persist Source,
Source Version 1, parse Job, Transactional Outbox Event and a reusable idempotency reservation in one
PostgreSQL transaction. Publish the exact OpenAPI contract, enforce the approved content rules,
return the standard asynchronous `202` envelope and keep customer content out of operational
payloads and logs. Parsing, queue delivery, retry/backoff and non-text ingestion are explicit
non-goals.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D02, S1-E01 and S1-E03; read 2026-09-02.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Context, Job, Outbox and generic idempotency data; read 2026-09-02.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — transaction and migration verification rules; read 2026-09-02.
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — Source/Version, Job and Outbox persistence baseline; read 2026-09-02.
- [API Contract](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — versioned API envelope and error baseline; read 2026-09-02.
- [Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit) — modular-monolith and asynchronous boundary; read 2026-09-02.
- Owner-approved D02 clarification in this task, 2026-09-05 — exact request, validation,
  SHA-256/UTF-8, actor-aware idempotency scope, 24-hour TTL, replay/conflict and atomic outcome.
- Repository governance, ADR-002, ADR-012, ADR-013 and
  [ADR-014](../../adr/ADR-014-text-context-ingestion.md).
- [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security) and
  PostgreSQL schema/constraint guidance — current platform check 2026-09-05.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-135 | S1-D02; owner clarification | `POST /api/v1/projects/{project_id}/context-sources`; Bearer + active tenant + mandatory key; exact body and standard `202` envelope | TC-2501, TC-2502 |
| REQ-136 | Owner clarification | Text-only, extra-field rejection, blank/control validation and exact 50,000 Unicode-character boundary | TC-2503 |
| REQ-137 | Owner clarification; ADR-012 | Preserve exact `raw_text`; lowercase SHA-256 over exact UTF-8 bytes | TC-2503, TC-2504 |
| REQ-138 | S1-D02; ADR-002/013 | Source + Version 1 + queued Job + pending Outbox + idempotency result share one Application-owned transaction | TC-2504, TC-2508 |
| REQ-139 | S1-D02; privacy/logging baseline | Job ref contains only Source IDs; Outbox uses versioned trace IDs; logs contain no raw/canonical text, storage URL or key | TC-2504, TC-2509 |
| REQ-140 | Owner clarification | Generic actor-aware idempotency, complete request fingerprint, 24-hour TTL, replay and `409` conflict | TC-2505, TC-2506 |
| REQ-141 | Migration/Supabase baseline | Additive `0006` schema, FK/unique constraint, RLS, revoked Data API grants and safe downgrade/re-upgrade | TC-2507 |
| REQ-142 | API/authorization baseline | Missing/deleted/cross-tenant Project remains safe `404`; invalid input `422`; inactive authority is denied | TC-2502, TC-2508 |
| REQ-143 | Documentation governance | OpenAPI, ADR, data model, migration mirror and linked final development/test records stay synchronized | TC-2510 |
| REQ-144 | S1-E02/E04 scope | No parser, file input, queue transport, retry/backoff, relay or consumer behavior is invented | TC-2511 |

## Assumptions and Clarifications

The owner-approved D02 clarification closes the prior documented gaps for the request body,
character limit, checksum, idempotency scope and TTL. The idempotency fingerprint includes the
Project path parameter in addition to the exact body because both are approved request inputs and
can change the command target. Source checksum remains independently defined over exact raw UTF-8
content. Parser/queue behavior remains deferred.

**Unapproved assumptions:** None

## Changes

- Added strict Text Context validation and exact raw-content SHA-256 checksum in the Context Domain.
- Added `CreateTextContextUseCase`, Application ports and one SQLAlchemy Unit of Work spanning the
  existing Project, Context, Jobs and Outbox repositories plus generic idempotency persistence.
- Added the approved reusable idempotency protocol to the shared Application kernel so generic
  infrastructure does not depend on the Context module's private contract.
- Added the tenant-authorized FastAPI route with exact request schema, standard `202` response and
  stable `404/409/422` mappings.
- Added `0006_idempotency_records` with the exact four-part unique scope, account/profile FKs, RLS,
  fail-closed Supabase Data API grants and safe downgrade.
- Added a complete request fingerprint so identical text sent with the same key to another Project
  cannot replay the first Project's result.
- Added OpenAPI, ADR-014, data-model and migration mirrors plus Domain, Application, API, contract
  and real PostgreSQL tests.

## Architecture and Design Decisions

[ADR-014](../../adr/ADR-014-text-context-ingestion.md) records the exact ingestion and idempotency
contract. PostgreSQL remains the transaction source of truth. The API creates durable intent only;
the Worker/queue boundary remains unchanged and no new deployable or provider is introduced.

## Structure Preservation

- Dependency direction remains `context/domain -> context/application -> context/infrastructure`;
  FastAPI stays in API routers and SQLAlchemy stays in Infrastructure.
- Cross-module writes are coordinated by an Application Unit of Work instead of direct router SQL.
- Existing Source/Version and Jobs/Outbox schemas are consumed without mutation; `0006` is an
  additive Alembic head revision.
- Tenant authorization reuses `require_tenant_context`; normal Project repository filtering keeps
  deleted/cross-tenant records indistinguishable.
- The Web, Worker and accepted repository layout remain unchanged; no service or provider is added.

## Senior Review

- **Contract fidelity:** PASS. Request, response, error, text and idempotency rules match the explicit
  owner decision and are machine-checked against OpenAPI.
- **Architecture:** PASS. The router only maps transport; orchestration is in Application; all five
  writes share one Infrastructure transaction; Domain imports no framework/provider code.
- **Tenant/security:** PASS. Project lookup is account-scoped and excludes soft-deleted rows. RLS and
  Data API revocation are verified on PostgreSQL. Cross-tenant input returns safe not-found.
- **Idempotency:** PASS. Scope is account + actor + route + key, expiration is exactly 24 hours, and
  the fingerprint covers the body and Project target. Review added a regression test for the
  cross-Project replay risk.
- **Privacy:** PASS. Exact customer text exists only on Context Source storage; Job/Outbox refs and
  structured logs are content-free. Raw text and idempotency key are asserted absent from logs.
- **Migration safety:** PASS. Fresh/offline chain, live upgrade, downgrade to `0005`, re-upgrade,
  schema inspection and grants are tested. No earlier revision was rewritten.
- **Test reliability:** PASS. Review corrected a Windows async test-harness defect by constructing,
  using and closing each async Engine within one event loop, matching FastAPI runtime semantics.
- **Scope control:** PASS. Parse execution, transport selection, retry policy and non-text input are
  absent and remain assigned to later approved increments.

## Verification

PASS — focused Domain/Application/API tests, live PostgreSQL integration, Alembic offline SQL, full
repository quality, build, architecture validation and independent secret/dependency scans all
passed. Exact commands and totals are in the linked report.

## Remaining Risks

- The accepted Job is not consumed until the separate queue/Worker contract is approved and
  implemented; this Increment claims durable acceptance, not completed parsing.
- PostgreSQL idempotency cleanup currently occurs on the exact request scope during reservation.
  No global cleanup schedule is introduced because the approved documents do not define one.
- Pytest reports a non-product cache-write warning caused by workspace permissions, and the pinned
  FastAPI TestClient stack reports its upstream httpx deprecation notice; neither affects results.
