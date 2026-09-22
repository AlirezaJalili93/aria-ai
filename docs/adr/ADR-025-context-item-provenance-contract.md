# ADR-025: Context Item Version and Provenance Contract

- **Status:** Accepted
- **Date:** 2026-09-05
- **Story:** S1-H01 — Context Item Schema
- **Supersedes:** `context_version_id`, singular `source_ref`, and `state=active` in older
  Context Item definitions

## Context

The approved sources disagree about whether Context Items reference an integer Context version or
a separate Context Version row, and the older architecture uses a singular Source reference and an
`active` state. The owner resolved these conflicts explicitly on 2026-09-05. H01 must establish the
schema and a trustworthy provenance boundary without adding the H02 AI workflow, a public API or a
new Context Version entity.

## Decision

- `context_version INTEGER CHECK (context_version >= 1)` is canonical. H01 does not create a
  `context_versions` table; `context_version_id` is superseded.
- `item_type` is exactly `fact|assumption|decision|constraint|reference|unknown`.
- `status` is exactly `proposed|confirmed|rejected|superseded`, with initial/default status
  `proposed`; the former `state=active` vocabulary is superseded.
- `source_refs` is a non-null JSON array. Each Application value is an exact Source Reference with
  `source_id`, `source_version_id`, and either both or neither zero-based half-open offsets.
- A whole-Version reference omits both offsets. An offset range satisfies
  `0 <= start_offset < end_offset <= len(canonical_text)`.
- Before persistence, Application and Repository resolve every reference to an existing,
  same-Account, same-Project, matching Source/Version pair whose Version is `ready`. Offset ranges
  require canonical text and must fit it.
- A confirmed Fact requires at least one semantically valid Source Reference. Other item types may
  use the explicit empty array.
- `confidence` is nullable `NUMERIC(5,4)` in the inclusive range zero to one.
- `created_by_type` is exactly `ai|user|system`. A user-created item requires `created_by`; AI and
  System items may omit it. `created_by` references Profile with `ON DELETE RESTRICT`.
- Account and Project references also use `ON DELETE RESTRICT`. Project and Account are linked by a
  composite foreign key so the Item cannot cross tenant boundaries.
- RLS is enabled and Data API roles have no direct table privileges. H01 adds no public policy.
- Context content and raw Source References are prohibited from logs.

## Consequences

Context Items can be traced to immutable ready Source Versions without introducing a second Context
Version source of truth. JSONB cannot provide element-level foreign keys, so semantic validation is
an Application/Repository responsibility and is covered by contract and PostgreSQL tests. Database
checks remain a final defense for JSON array shape, confirmed-Fact non-emptiness, vocabularies and
creator consistency.

## Deferred

- Content length and normalization policy.
- Context Item API and UI.
- H02 AI structuring, validation/repair and persistence workflow.
- A physical `context_versions` table or `context_version_id` relation.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H01
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit)
- [Production Data Architecture & Database Schema v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit)
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit)
- Owner clarification dated 2026-09-05

