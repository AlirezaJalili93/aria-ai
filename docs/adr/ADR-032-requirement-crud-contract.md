# ADR-032: Requirement CRUD and Human Review Contract

- **Status:** Accepted
- **Date:** 2026-09-07
- **Story:** S1-I03 — Requirement CRUD/Edit API
- **Extends:** ADR-030 Requirement Domain and ADR-031 Requirement Generation

## Context

The canonical Backlog requires manual add, edit, deactivation and audit metadata. The API baseline
lists title, description, priority, status and `acceptance_note` as mutable fields, while its
post-Snapshot delete rule depends on a Scope Snapshot lifecycle that does not yet exist. The Data
Dictionary supplies the four Requirement states, and the owner approved a limited I03 contract
that avoids inventing Snapshot detection, restore or historical edit records.

## Decision

- `GET /api/v1/projects/{project_id}/requirements` is tenant-scoped, uses an opaque
  `(created_at,id)` descending cursor, defaults to 20 and caps at 100. Only `category` and `status`
  are accepted filters. Without a status filter, `removed` and `superseded` are excluded.
- The public Requirement representation includes product fields and provenance but excludes
  `account_id`, `project_id`, `created_by`, `generation_job_id` and `duplicate_group_key`.
- `POST` requires `Idempotency-Key` and accepts only title, description, category and priority.
  The established generic 24-hour reservation contract applies. The server binds the current
  Project Context Version and owns `draft`, `user`, creator identity, empty Source References,
  null confidence and `is_unsupported=false`.
- A Project with `current_context_version=0` rejects manual creation with the stable
  `422 CONTEXT_VERSION_REQUIRED`. Missing, deleted and cross-tenant Projects remain the same safe
  `404 RESOURCE_NOT_FOUND`.
- `acceptance_note TEXT NULL` is added without an invented length or normalization rule. It is
  absent from create input, mutable through PATCH, and explicit JSON null clears it.
- PATCH requires `expected_updated_at`. A mismatch returns `409 VERSION_CONFLICT`. Only title,
  description, priority, acceptance note and explicit `draft -> confirmed` are mutable. Source
  References, origin, context version and AI-generation metadata are read-only.
- Editing a confirmed Requirement demotes it to `draft`; changing content cannot silently retain
  prior human confirmation. `removed` and `superseded` are terminal and immutable in I03.
- DELETE is a soft command permitted only for `draft`, changing it to `removed` and returning 204.
  It never physically deletes a row. Other states return `409 INVALID_REQUIREMENT_STATE`.
- Active Owner, Admin and Member Memberships may use the endpoints. Authorization is enforced by
  the existing tenant dependency and every repository predicate includes Account and Project.
- Minimal audit metadata remains creator/origin plus database-owned timestamps. Structured events
  are `requirement.added`, `requirement.edited`, `requirement.confirmed`,
  `requirement.removed`, `requirement.version_conflict` and safe access/failure signals. Requirement
  text, acceptance note and Source References are prohibited from logs. I03 adds no Audit table.

## Consequences

Human review is explicit and concurrency-safe, and manual Requirements cannot exist outside a
valid Project Context. Mutable operational Requirements remain distinct from future immutable
Scope snapshots. Create replay resolves the same resource identity without a second Requirement
write.

## Deferred

- Post-Scope-Snapshot delete-to-superseded behavior and Snapshot membership detection.
- Restore/reactivation, merge, selective regeneration and immutable Requirement edit history.
- Requirement UI (I04), quality evaluation (I05), Gap linkage and Scope snapshot behavior.
- Durable `audit_events` persistence beyond the approved minimal I03 metadata and safe logs.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I03
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Requirements and common API rules
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Requirements
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — Context and Requirement permissions
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Requirement edit/conflict states
- Owner-approved I03 contract dated 2026-09-07.
