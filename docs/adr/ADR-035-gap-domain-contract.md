# ADR-035: Gap Domain Contract

- **Status:** Accepted — owner approval received 2026-09-07
- **Date:** 2026-09-07
- **Story:** S1-J01 — Gap Domain
- **Supersedes:** `missing_info`, `context_version_id`, the four-type Data Dictionary vocabulary,
  and the older cascade-delete Gap DDL

## Context

The approved sources disagree on Gap vocabulary and fields. The Sprint Backlog names five types,
the AI Workflow names six, the current Data Dictionary uses the older `missing_info` spelling and
only four types, and the Migration Plan contains Clarification and accepted-assumption fields that
belong to later Stories. The owner approved one bounded J01 Domain/Data contract and explicitly
deferred J02 detection semantics and J03 Clarification/resolution behavior.

## Decision

The canonical `gaps` record contains only:

```text
id UUID PK
account_id UUID NOT NULL
project_id UUID NOT NULL
context_version INTEGER NOT NULL CHECK >= 1
gap_type missing_information | ambiguity | conflict | decision_required |
         unsupported_assumption | scope_risk
severity critical | high | medium | low
status open | resolved | dismissed DEFAULT open
source_refs JSONB NOT NULL DEFAULT []
created_at TIMESTAMPTZ NOT NULL
updated_at TIMESTAMPTZ NOT NULL
resolved_at TIMESTAMPTZ NULL
```

- `resolved_at` may be non-null only while `status=resolved`; it must be null for `open` and
  `dismissed`. J01 does not define a requirement that every resolved row already has a timestamp.
- `dismissed` means invalid or deliberately set aside. It is not resolved and must remain distinct
  in future Analytics and Scope Readiness.
- `source_refs` uses the accepted H01 provenance structure. Empty provenance is valid, including
  for `missing_information`. Type-specific evidence requirements wait for J02.
- Account and composite Project/Tenant foreign keys use `ON DELETE RESTRICT`. Hard delete is not a
  Domain operation; `dismissed` preserves history.
- PostgreSQL owns `updated_at`; RLS is enabled and broad Data API privileges are revoked.
- The Project/status/severity index begins with the tenant anchor.

## Explicit deferrals

- `question` and Clarification records/flows: J03.
- A simple `accepted_assumption` Boolean: rejected. Actor/timestamp semantics: J03.
- `affected_requirement_ids`, `suggested_resolution_type`, detection rules, type-specific evidence
  and generation: J02.
- Gap list/mutation API, resolution transition rules, Scope Readiness and UI: later Stories.
- No `title`, `explanation`, `created_by`, AI Provider, Job or Outbox field is introduced by J01.

## Safe observability

J01 creation emits `gap.created` with identifiers, context version, type, severity, status and
duration only. Future resolved/dismissed commands must use `gap.resolved` and `gap.dismissed` with
the same safe field policy. Source References and Context content are prohibited from logs.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J01; read 2026-09-07
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Gap baseline; modified 2026-09-01 and read 2026-09-07
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; read 2026-09-07
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-06; read 2026-09-07
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit) — Gap DDL baseline; read 2026-09-07
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — logical M006; read 2026-09-07
- Owner-approved J01 contract and refinements dated 2026-09-07.
