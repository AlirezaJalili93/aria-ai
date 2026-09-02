# Development Record: 0023 Context Source Model

- Increment ID: `0023-context-source-model`
- Date: 2026-09-02
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-D01 — Context Source Model`, logical migration `M003`
- [Test report](./test-report.md)

## Scope

Implement the approved two-table Context Source/Version Domain, Application lifecycle service,
tenant-scoped SQLAlchemy repository, logical M003 migration, ready-snapshot immutability, derived
current Version, status-based deletion and safe lifecycle logging. No HTTP endpoint, parser, queue,
file upload, hash algorithm, text normalization or text-length policy is added.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-D01.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — current fields and Source vocabulary; read 2026-09-02.
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — two-table/version history baseline; read 2026-09-02.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — logical M003 fields/indexes/security; read 2026-09-02.
- [Access Control Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active tenant/resource isolation; read 2026-09-02.
- [API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — future Context Source route boundary; read 2026-09-02.
- [Supabase database migrations](https://supabase.com/docs/guides/deployment/database-migrations), [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), and [securing data](https://supabase.com/docs/guides/database/secure-data) — current implementation guidance checked 2026-09-02; no relevant breaking database change found.
- Owner clarification dated 2026-09-02 approving exact fields, states, immutability, derived current Version, deletion/FK behavior, tenant consistency and safe logs.
- Repository governance, architecture/data-model mirrors, ADR-008, ADR-010 and ADR-012.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-115 | S1-D01; owner | Two tables and exact approved fields | TC-2301, TC-2308 |
| REQ-116 | Data Dictionary; owner | Exact Source type/status and Version parse-status vocabularies | TC-2302, TC-2309 |
| REQ-117 | Owner | Application admits only `text`; other schema types remain unavailable | TC-2303 |
| REQ-118 | Owner | `version_no >= 1`, unique Source/version, derived greatest ready Version | TC-2304, TC-2310 |
| REQ-119 | Owner | Ready content invariant and immutable ready snapshot | TC-2305, TC-2311 |
| REQ-120 | Owner | Status-based deletion, ordinary-query exclusion and preserved Versions | TC-2306, TC-2312 |
| REQ-121 | Owner | Composite DB tenant/project consistency and required Profile creator FK | TC-2313 |
| REQ-122 | Owner; logging baseline | Five safe lifecycle events with IDs/trace, no content/storage/metadata | TC-2307, TC-2314 |
| REQ-123 | Supabase/Architecture | Tenant-first indexes, RLS, fail-closed Data API grants and safe downgrade | TC-2308, TC-2315 |
| REQ-124 | Owner | Hash/canonicalization/encoding/max length and file ingestion remain deferred | TC-2303, TC-2316 |
| REQ-125 | Repository governance | Documentation, full quality gates and senior review | TC-2317 |

## Assumptions and Clarifications

The owner explicitly resolved every known conflict on 2026-09-02. ADR-012 records the superseded
names, pointer, lifecycle and cascade behavior. Hash semantics and maximum text length are not part
of this increment.

**Unapproved assumptions:** None

## Changes

- Added the framework-independent Context Source/Version Domain with the exact approved Source,
  Source-status and parse-status vocabularies, positive Version numbers and ready-content invariant.
- Added Application ports and a tenant-aware lifecycle service for creating text Sources, creating
  Versions, completing/failing Versions, deriving the current ready Version and status-based Source
  deletion. Five approved lifecycle outcomes and a safe repository-failure event are emitted without
  source content, storage references or metadata.
- Added SQLAlchemy models, repository and Unit of Work. Ordinary Source reads require Account,
  Project and Source identity and exclude `deleted`; current Version is queried as the greatest ready
  `version_no` rather than read from a pointer.
- Added logical M003 (`0004_context_sources`) with the two approved tables, named checks, composite
  tenant FKs, creator FK, tenant-first indexes, RLS, fail-closed Data API grants, ready-row
  immutability trigger, `RESTRICT` Version history and safe downgrade.
- Added the Project `(id, account_id)` uniqueness needed by the composite Source FK and updated the
  existing head-schema test to recognize that constraint-backed index.
- Extended structured logging with validated `source_id` and `version_no`; registered the Context
  module/migration metadata and added contract, Domain, Application and PostgreSQL tests.
- Updated the developer data-model mirror and accepted ADR-012 to record the owner-approved
  supersede explicitly.

## Architecture and Design Decisions

See [ADR-012](../../adr/ADR-012-context-source-versioning.md).

## Structure Preservation

- The modular-monolith boundary remains `context/domain -> context/application ->
  context/infrastructure`; Domain imports no framework, SQLAlchemy, Supabase or observability code.
- No deployable, public route, OpenAPI operation, queue, parser or storage integration was added.
- Existing M000–M002/M003-predecessor order is preserved; the new logical M003 is an additive Alembic
  head revision and its downgrade does not restore Data API privileges.
- Existing Project soft-delete and Identity boundaries remain unchanged. The Project tuple uniqueness
  is solely a database target for Source tenant consistency.

## Senior Review

- **Architecture:** PASS. Domain models, Application ports/orchestration and Infrastructure adapters
  remain separated; current Version has one derived source of truth.
- **Tenant/security:** PASS. Composite Project/Source identity is enforced in PostgreSQL, repository
  reads are tenant scoped, Source history cannot cascade-delete, RLS is enabled and Data API roles
  receive no authority.
- **Data integrity/concurrency:** PASS. Named checks cover exact vocabularies and ready content;
  uniqueness serializes duplicate Version numbers; row locking plus the immutable-ready trigger
  prevents a committed ready snapshot from later mutation.
- **Privacy/observability:** PASS. Approved IDs, state, duration and trace metadata are allowlisted;
  tests prove raw/canonical text and metadata are absent from success and failure logs.
- **Migration/recovery:** PASS on an isolated PostgreSQL 18 cluster. Upgrade, real constraints,
  downgrade and re-upgrade were executed. Offline SQL generation also passes.
- Review corrections included PostgreSQL-safe constraint/index identifiers and alignment of the
  pre-existing Project schema test with the new constraint-backed index.

## Verification

PASS — contract, Domain, Application, real PostgreSQL integration, full API, Web, Worker, lint,
typecheck, build, architecture, secret and dependency gates are recorded in the linked test report.

## Remaining Risks

- S1-D02 still owns checksum algorithm, canonicalization, encoding and maximum text length.
- Public Context APIs, role-specific mutation authorization, ingestion orchestration, parser/Worker
  behavior and file/message/URL activation remain outside this increment and require their approved
  contracts before implementation.
- RLS policy creation remains in the documented later M010 sequence; M003 stays fail-closed for the
  Data API and the trusted Application connection remains the only current data path.
