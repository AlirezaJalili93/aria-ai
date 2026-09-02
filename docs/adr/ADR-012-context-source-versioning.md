# ADR-012: Context Source Identity, Versioning, and Tenant Consistency

- **Status:** Accepted
- **Date:** 2026-09-02
- **Story:** S1-D01 — Context Source Model
- **Supersedes:** the `context_sources`-only omission in the current Detailed Data Dictionary;
  `context_source_id`, `current_version_no`, `parse_status=pending` on the Source, `archived_at`, and
  Source-to-Version `ON DELETE CASCADE` in the older Production Data Architecture/Migration Plan

## Context

The approved sources disagreed about whether Source versions are independent rows, whether a
mutable current-version pointer exists, which lifecycle vocabulary belongs to Source versus parse
state, and whether deleting a Source may cascade into its history. The owner resolved those
conflicts explicitly on 2026-09-02. Source identity/lifecycle and immutable content snapshots must
remain separate so traceability is not lost.

## Decision

- M003 has `context_sources` and `context_source_versions`.
- The canonical Version FK name is `source_id`; the older `context_source_id` name is superseded.
- Source status is exactly `uploaded|parsing|ready|failed|deleted`; Version parse status is exactly
  `pending|parsing|ready|failed`.
- `version_no >= 1` and `UNIQUE(source_id, version_no)` are database constraints.
- A ready Version contains `canonical_text` or `storage_ref` and is immutable. Future operational
  metadata requires a separate contract rather than mutating this snapshot.
- Current Version is the greatest ready `version_no` for a Source. No `current_version_no` cache or
  second source of truth is stored.
- Source deletion is a lifecycle transition to `deleted`; normal queries exclude it. Version rows
  remain. The physical Source-to-Version FK uses `RESTRICT`, not cascade.
- Version `account_id` and `project_id` must equal its Source values through a composite database FK.
- `created_by` is a required FK to `profiles.user_id`.
- The database recognizes `text|file|message|url_reference`; the S1-D01 Application policy admits
  only `text`. File/message/URL ingestion remains unavailable until its own approved increment.
- Hash algorithm, normalization, encoding and maximum text length are deferred together to S1-D02.
- Lifecycle logs include safe IDs/state only and never raw/canonical text, storage URL or metadata.

## Consequences

History cannot be erased by ordinary Source deletion, a Version cannot cross Account or Project
boundaries, and no cached pointer can drift from ready Version rows. The composite FK requires a
matching unique identity tuple on `context_sources`. RLS remains defense-in-depth and Data API
roles receive no table authority in this migration; policy creation stays in the approved M010
sequence.

## Rejected

- Store only mutable `raw_text` on `context_sources`: loses Source-level history.
- Keep `current_version_no`: creates a dual source of truth.
- Cascade Source deletion into Version rows: destroys traceability.
- Enable all schema-known Source types in Application: activates deferred product behavior.

## Sources

- Sprint 1 Technical Backlog v1.0 — S1-D01
- Detailed Data Dictionary v1.0 — current Context Source semantic baseline
- Production Data Architecture & Database Schema v2.0 — Source/Version separation baseline
- Database Migration Execution Plan v1.0 — M003
- Access Control & Authorization Matrix v1.0 — active tenant and resource isolation
- Owner clarification dated 2026-09-02

