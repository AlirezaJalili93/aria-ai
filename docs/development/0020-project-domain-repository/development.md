# Development Record: 0020 Project Domain Repository

- Increment ID: `0020-project-domain-repository`
- Date: 2026-09-01
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-C01 — Project Domain + Repository`, migration `M002`
- [Test report](./test-report.md)

## Scope

Implement the approved Project aggregate vocabulary, Application services, SQLAlchemy repository,
M002 schema, tenant/active-Membership create guard, soft-delete filtering, database-managed
`updated_at`, and safe structured events. No Project HTTP endpoint or UI behavior is added.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-C01`.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Project fields, vocabulary, ownership and soft delete; corrected in place 2026-09-01.
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — Project DDL baseline and timestamp decision point.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — M002 columns, indexes, owner invariant and recovery tests.
- [API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — future Project mutation vocabulary and MVP soft delete.
- [Access Control Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active-Membership and Project role rules.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — Project and tenant test families.
- Owner approvals dated 2026-08-31 and 2026-09-01 for exact status, owner FK, context version zero, soft-delete query guardrails, event vocabulary, DB-trigger timestamps, and documentation correction.
- Repository `AGENTS.md`, architecture/data/governance mirrors, ADR-008 and Increment 0019.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-087 | S1-C01; Data Dictionary | Project Domain types and aggregate fields | TC-2001, TC-2002 |
| REQ-088 | Owner clarification | `owner_id` NOT NULL FK Profile; active Membership in same Account on create | TC-2003, TC-2004 |
| REQ-089 | Owner supersede | initial Context version is 0; DB default/check permit `>=0` | TC-2005 |
| REQ-090 | Data Dictionary; owner | exact seven statuses with `draft` default | TC-2006 |
| REQ-091 | API Contract; owner | nullable `deleted_at`; ordinary reads exclude deleted | TC-2007, TC-2008 |
| REQ-092 | Migration Plan | tenant-first Project indexes and account cascade | TC-2009 |
| REQ-093 | Owner P2-6 | DB trigger owns `updated_at` for existing mutable Identity rows and Projects | TC-2010 |
| REQ-094 | Owner logging contract | safe Project success/failure events with IDs and correlation, no content | TC-2011 |
| REQ-095 | Supabase security baseline | Project RLS enabled and no Data API grants/policies added before M010 | TC-2012 |

## Assumptions and Clarifications

Project Title normalization is not defined by the approved documents. This Increment enforces only
the documented `NOT NULL` and `VARCHAR(255)` constraints and does not trim, rewrite, or invent a
minimum length. Project API normalization remains blocked pending a dedicated contract.

**Unapproved assumptions:** None

## Changes

- Added immutable Domain types for the exact Project type/status vocabulary, persisted Project
  aggregate and unpersisted `NewProject` input. Context version is non-negative and timestamps are
  timezone-aware.
- Added Application commands and service for create, update, archive and soft delete over explicit
  repository/UoW ports. Create derives `owner_id` and `account_id` from active Tenant Context;
  archive/delete require active owner/admin authority.
- Added SQLAlchemy model/repository with tenant-scoped reads, default soft-delete exclusion and an
  explicit internal including-deleted recovery read.
- Added M002 with the approved columns, checks, FKs, indexes, RLS, fail-closed Data API grants and
  database-managed `updated_at` triggers for accounts/profiles/projects.
- Added safe structured Project success/failure events containing trace identifiers but no title,
  content, JWT, raw subject or Profile data.
- Corrected the canonical Detailed Data Dictionary lower bound to `>=0 default 0`, synchronized the
  developer data-model mirror and recorded ADR-010.

## Structure Preservation

- Domain imports no FastAPI, SQLAlchemy, Supabase or observability code.
- Application depends only on Domain, Identity Application Tenant Context, observability contract
  and repository/UoW ports; Infrastructure implements those ports.
- Repository failures are declared beside the Application port, not in the concrete service or
  Infrastructure adapter.
- No HTTP route, Project UI, new deployable, cross-module direct write or undocumented field was
  added. M002 follows the approved migration sequence after M001a.

## Senior Review

- **Domain/data parity:** PASS. Exact enums, owner FK, version-zero semantics, soft delete and
  tenant-first indexes match the approved sources and corrected canonical dictionary.
- **Authorization:** PASS. Non-active Memberships are rejected before write; member role cannot
  archive either through the archive command or by setting archived through general update.
- **Repository safety:** PASS after correction. `NewProject` no longer pretends to have persisted
  timestamps/deletion state; empty updates are rejected before SQL construction; ordinary reads
  always filter Account and `deleted_at IS NULL`.
- **Migration/recovery:** PASS on PostgreSQL. Fresh upgrade, constraints, RLS/grants, trigger
  advancement and downgrade/re-upgrade all passed.
- **Observability/privacy:** PASS. Success and repository-failure events contain IDs and correlation
  metadata only; private Persian title content was explicitly absent from logs.
- **Scope:** PASS. Title normalization and Project HTTP idempotency remain deferred rather than
  silently invented.

## Verification

Focused Project tests, the complete PostgreSQL-backed API suite, Web/Worker regressions, build,
security scans and mandatory repository gates all passed. See the linked test report.

## Remaining Risks

- Exact Title normalization remains unspecified and is not implemented.
- Project HTTP transport/idempotency is owned by S1-C02.
