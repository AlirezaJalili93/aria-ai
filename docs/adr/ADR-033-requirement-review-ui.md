# ADR-033: Requirement Review UI Contract

- **Status:** Accepted
- **Date:** 2026-09-07
- **Story:** S1-I04 — Requirement UI
- **Extends:** ADR-032 Requirement CRUD and Human Review Contract

## Context

The canonical Backlog requires a Requirement list with filtering, editing, manual addition,
deactivation and source trace. The API and I03 already provide the tenant-scoped lifecycle and
optimistic-concurrency authority. The UI must therefore expose that approved behavior without
inventing generation, restore, merge, Scope Snapshot or human-readable Source metadata.

## Decision

- The canonical route is `/projects/{projectId}/requirements`, linked from Project Overview and
  protected by the established authenticated single-Account resolution flow.
- Category and status filters and cursor pagination call the approved API. The Web layer does not
  filter a stale client copy or derive Tenant authority from route/resource identifiers.
- Manual addition is a single inline form for title, description, category and priority. Create
  retries retain the same idempotency key for the same submission and rotate it after a changed or
  successful submission.
- Every Requirement displays origin, lifecycle state, category, priority, Context Version,
  confidence when present, unsupported status, acceptance note and the actual technical Source
  References returned by the API. No invented source name or provenance summary is shown.
- Human confirmation is explicit. Draft Requirements can be confirmed, edited or deactivated.
  Confirmed Requirements can be edited only with a visible warning that saving demotes them to
  draft. Removed and superseded Requirements are read-only.
- Edit sends title, description, priority, acceptance note and `expected_updated_at`. Version
  conflicts and invalid lifecycle states remain distinct recoverable errors. Provenance, origin,
  Context Version and generation metadata are not editable.
- Draft deactivation requires explicit confirmation. Hard delete, restore and deactivation of
  confirmed Requirements are not exposed.
- Loading, initial-empty, filtered-empty, partial request failure, retry, mutation failure,
  conflict, pending-submit and unsaved-edit states are explicit. Failed requests retain the
  currently visible data or form values.
- Product analytics uses the approved versioned internal instrumentation. The UI emits
  `requirement_edited` and `requirement_removed` once per successful result with identifiers only;
  Requirement text, notes and provenance are excluded.
- The implementation is RTL-first, uses canonical tokens, keeps visible focus and 44px targets,
  and respects reduced motion. Status meaning is never color-only.

## Consequences

I04 provides a complete human-control surface over the existing I03 API while PostgreSQL and the
backend remain the lifecycle, concurrency and Tenant authorities. The technical provenance view
is truthful but intentionally limited until a canonical source display contract exists.

## Deferred

- Requirement generation/regeneration controls, merge, restore and Scope Snapshot behavior.
- Human-readable Source labels, filenames, excerpts or source-detail navigation.
- Real analytics provider integration; the existing versioned internal instrumentation remains
  the only approved sink.
- Requirement quality evaluation (I05) and browser verification against an authenticated hosted
  environment.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-I04
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Requirement endpoints and common API rules
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — Requirement review, conflict and unsaved states
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — tenant-scoped Requirement permissions
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — traceability and mandatory human control
- [Aria AI Design System — Master](../../design-system/MASTER.md)
- Owner-approved I04 continuation contract dated 2026-09-07.
