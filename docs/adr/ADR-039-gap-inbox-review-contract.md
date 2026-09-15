# ADR-039: Gap Inbox Read and Human Review Contract

- **Status:** Accepted for S1-J04 — owner approval received 2026-09-12
- **Date:** 2026-09-12
- **Story:** S1-J04 — Gap Inbox UI
- **Supersedes:** only the Gap dismissal transport and concurrency clauses in ADR-038 and the
  older general Gap PATCH in the API baseline

## Context

The approved backlog requires a Gap Inbox with visible severity, answer, accepted-assumption and
resolved states. J03-A already provides auditable question and Resolution commands, but the public
API did not expose a tenant-safe Gap list or Clarification history. The owner froze the missing
read contracts and refined Gap dismissal into a bodyless idempotent human command. J03-B semantic
propagation remains deferred.

## Decision

`GET /api/v1/projects/{project_id}/gaps` lists only rows whose `context_version` equals the
Project `current_context_version`. A Project at version zero returns a successful empty Collection
Envelope. Filters are the closed vocabularies `status`, `severity`, and `gap_type`. Results use
`(created_at,id) DESC`, default limit 20 and maximum 100. The opaque cursor contains its filter
identity; malformed cursors or reuse under different filters fail validation.

`GET /api/v1/projects/{project_id}/gaps/{gap_id}/clarifications` reads the complete question
history in `(created_at,id) ASC` order. It may read a historical Gap in the same Project even when
that Gap is no longer in the current Context Version. Each question exposes only its public
lifecycle fields and optional Resolution. Account IDs and internal `actor_id`/`author_id` audit
metadata are not exposed.

Missing, cross-account and cross-project resources return the same `404 RESOURCE_NOT_FOUND`.
All active owner, admin and member Memberships may perform J04 review actions; the Backend remains
the authorization authority.

`POST /api/v1/projects/{project_id}/gaps/{gap_id}/dismiss` is the only public dismissal command.
It has no body and requires `Idempotency-Key`. An open Gap becomes dismissed while `resolved_at`
stays null. A replay of the same completed command succeeds with 204; a resolved Gap is terminal.
Ignoring one Clarification remains distinct from dismissing its Gap.

`accepted_assumption` is permitted only when both `gap_type=unsupported_assumption` and
`suggested_resolution_type=validate_assumption`. UI eligibility never replaces the identical
Backend invariant.

The RTL route `/projects/{projectId}/gaps` provides loading, empty, filtered-empty, error/retry and
load-more states. Severity uses visible text plus an SVG icon and visual treatment, never color
alone. Resolved/dismissed Gaps and answered/ignored Clarifications are read-only while historical
Resolution remains visible.

## Exclusions

J04 does not add AI question generation, recompute, severity mutation, semantic answer validation,
Context or Requirement updates, readiness/confidence scores, hard delete, a new analytics provider,
or any J03-B behavior.

## Observability

Central HTTP telemetry is sufficient for reads. Approved mutation events remain
`clarification.edited`, `clarification.answered`, `clarification.ignored`,
`clarification.version_conflict`, `gap.resolved`, and `gap.dismissed`. Logs must not include
question or answer text, Gap explanation, Source References, Context/Requirement content, client
free text, JWTs or raw claims.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J04; synchronized 2026-09-12
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06 and US-08; synchronized 2026-09-12
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap/Clarification baseline; synchronized 2026-09-12
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03/AI-04 and human review; synchronized 2026-09-12
- [Backend API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Gap route baseline; synchronized 2026-09-12
- Owner-approved S1-J04 frozen refinements dated 2026-09-12.
