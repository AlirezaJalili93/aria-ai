# ADR-046 — Product Analytics Baseline

- **Status:** Accepted — owner approval received 2026-09-12
- **Story:** S1-L01 — Product Event Baseline
- **Supersedes:** Earlier ad-hoc product event logging shapes

## Decision

Product Analytics uses one versioned, provider-neutral envelope for approved server-owned
outcomes and separate names for client-owned interactions. The server outcome names are
`project_created`, `context_added`, `structuring_started`, `structuring_completed`,
`requirements_generated`, `gap_detected`, `gap_resolved`, `scope_generated` and
`scope_version_saved`. Client interaction names are `project_opened`, `project_type_selected`,
`requirement_edited`, `requirement_removed` and `scope_edited`.

Every event carries `event_id`, `event_name`, `event_category=product_analytics`,
`schema_version=1`, `occurred_at`, `account_id`, `project_id`, `actor_id` (nullable) and
`properties`. Server event IDs are deterministic UUID5 values derived from event name and the
persisted logical entity ID. Replays therefore retain the same ID and are idempotently ignored by
the structured logger. Downstream ingestion must preserve that stable-ID deduplication contract.

## Property and ownership rules

Server properties are allowlisted per event: project creation permits project type, role and source
surface; context addition permits source ID, context version and source surface; structuring,
requirements and scope generation permit context version; gap events permit gap ID and context
version; and scope version saving permits context version and version number. IDs are UUIDs,
versions are positive integers, and enums are restricted to the documented vocabularies.

Outcome events are emitted by the server after the corresponding business commit. `gap_detected`
is emitted once per persisted Gap, `requirements_generated` once per successful generation batch,
`scope_generated` once per persisted Scope Draft and `scope_version_saved` after immutable version
commit. Start events may be emitted at workflow start. Client interaction events never claim a
server outcome; the pre-project `project_type_selected` interaction may carry `project_id=null`
because no Project exists yet, while authenticated account context remains mandatory.

Neither event properties nor logs may contain title, description, context/scope text, requirement
or gap content, provenance arrays, prompts, JWTs, email addresses, provider responses or raw
payloads. A new analytics provider, database table or deployable service is not introduced by L01.

## Transaction and structure boundaries

Analytics emission is an observability boundary only. Domain/Application layers depend on the
provider-neutral event helper; provider SDKs remain absent. Business writes remain authoritative
and analytics failure must not become a second business transaction. Existing operational event
names and the modular-monolith/API-Web boundaries remain preserved.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L01; synchronized 2026-09-12.
- [Product Analytics Baseline approval](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — owner-approved contract refinements dated 2026-09-12.
- [System Architecture v2](../architecture/system-architecture.md) — modular-monolith and observability boundaries.
