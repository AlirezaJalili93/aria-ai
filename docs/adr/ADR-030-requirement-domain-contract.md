# ADR-030: Requirement Domain and Provenance Contract

- **Status:** Accepted
- **Date:** 2026-09-06
- **Story:** S1-I01 — Requirement Domain
- **Supersedes:** `context_version_id`, singular `content`, `requirement_type`, `source_type`, and
  generic `provenance` in conflicting older Requirement definitions

## Context

The approved Requirement documents disagree about version references, textual fields, creator
vocabulary and provenance naming. The owner resolved the conflicts explicitly on 2026-09-06. I01
must establish a tenant-safe Domain/Data boundary without adding generation, deduplication, HTTP,
UI, lifecycle commands or `acceptance_note` behavior.

## Decision

- A Requirement references `context_version INTEGER NOT NULL CHECK (context_version >= 1)`. No
  `context_versions` table or `context_version_id` is introduced.
- Application persistence accepts the version only when it is not greater than the same tenant
  Project's `current_context_version`. A Project with version zero cannot receive a Requirement.
- Category is exactly `functional|content|visual|technical|constraint|business` and has no default.
- `title VARCHAR(255) NOT NULL` plus `description TEXT NOT NULL` supersede the older single
  `content` field. I01 does not normalize or invent a minimum content length.
- Priority is exactly `must|should|could`, is mandatory and has no default.
- Status is exactly `draft|confirmed|superseded|removed`, defaulting to `draft`. `removed` is a
  terminal soft-deactivation state in I01; hard delete and restore behavior are not exposed.
- `source_refs` is a non-null JSON array with an empty-array default. Each element follows the H01
  Source Reference contract: `source_id`, `source_version_id`, and either both or neither
  zero-based half-open offsets.
- Before persistence, every reference resolves to a ready, matching Source/Version pair in the
  same Account and Project. Offset ranges require canonical text and must fit that text.
- `confidence` is nullable `NUMERIC(5,4)` in the inclusive range zero to one.
- `created_by_type` is exactly `ai|user`. A user-created Requirement requires `created_by`; an AI
  Requirement may omit it. The older `source_type` name is superseded.
- Account, composite Project/Account and Creator references use `ON DELETE RESTRICT`.
- RLS is enabled and Data API roles receive no direct table privilege or public policy in I01.
- Requirement creation logs identifiers, version, priority and creator type only. Title,
  description and raw Source References are prohibited from logs.

## Consequences

Requirements remain traceable to an actual Project Context Version without adding a second Context
Version source of truth. JSONB element-level provenance remains an Application/Repository
responsibility. Database checks and restrictive foreign keys provide final defense for vocabulary,
tenant consistency, creator consistency and top-level JSON shape.

## Deferred

- S1-I02 generation, unsupported classification, duplicate detection and merge semantics are now
  defined by ADR-031.
- S1-I03 HTTP CRUD, lifecycle transitions, audit metadata and `acceptance_note`.
- S1-I04 UI and S1-I05 model-quality evaluation.
- Manual Requirements before the first valid Context Version.
- Restore/reactivation of a removed Requirement.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I01
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Requirements
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — §6
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — M005
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — §13
- Owner clarification dated 2026-09-06
