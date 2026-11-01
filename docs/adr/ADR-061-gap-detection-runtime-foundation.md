# ADR-061: Gap Detection Runtime Foundation

- **Status:** Accepted for 0074 — owner approval received 2026-09-22
- **Date:** 2026-09-22
- **Story:** S1-J02 runtime foundation
- **Extends:** ADR-036, ADR-037, ADR-057

## Context

The provider-neutral AI-03 use case, deterministic Completion Checklist and Critical Gap Rule Pack
already exist. The remaining foundation is a durable, recoverable Job/Outbox/Worker path that can
exercise them without exposing a Product endpoint, using customer content or invoking a paid
Provider.

The approved 0074 clarification makes an empty Requirement set a valid business input. Gap
Detection still requires a usable exact Context snapshot. It must never synthesize a generic
"requirements are missing" Gap merely because the Requirement set is empty; Gap output must be
supported by Context, Checklist evidence, contradictions or the accepted deterministic rules.

## Decision

- AI-03 is scheduled only through an explicit internal Application command. There is no public
  HTTP endpoint and no AI-02-to-AI-03 chaining in this increment.
- Execution is synthetic-only: the Fake Provider and synthetic fixtures are the only authorized
  data path. Customer content, paid Providers, runtime Primary/Fallback selection and hosted task
  registration are prohibited.
- Canonical durable identities are:
  - Job type: `gap_detection`
  - Outbox event: `gap.detection_requested.v1`
  - Delivery channel: `job_queue`
  - Celery task: `aria.gaps.detect.v1`
  - Queue envelope: exactly `message_version`, `outbox_event_id`, `job_id`
- A Job pins one exact `context_version`, the sorted Context Item and Requirement revision vectors,
  `completion_checklist_v1` and `critical_gap_rule_pack_v1`. The Worker never resolves an
  unpinned latest snapshot.
- At least one eligible Context Item is required. Zero eligible Requirements is valid and the
  pinned Requirement revision vector may therefore be empty.
- At most one `queued|running` Gap Detection Job may exist for the same Account, Project and
  Context Version. A partial unique database index is the final concurrency guard.
- Queue-level automatic retry is disabled. Duplicate delivery is suppressed by the existing
  JobExecutionGuard. A persistence interruption releases the same Job for controlled recovery.
- Gap rows, Requirement links, deterministic Rule Pack results and `Job -> succeeded` finalize in
  one database transaction. A failed commit exposes none of them and keeps the same logical Job
  recoverable.
- Fake/synthetic recovery may safely re-execute. Re-invocation after an ambiguous paid-Provider
  success remains unauthorized and requires a separate AI invocation recovery contract.

## Synthetic adapter semantics

The deterministic Fake Provider returns the complete checklist signal set required by ADR-037.
It does not infer product meaning from arbitrary text, produce a generic no-Requirement Gap or
claim real model quality. The versioned Critical Rule Pack remains the sole authority for Critical
classification.

## Security and observability

- Job/Outbox/Queue payloads contain identifiers and pinned metadata only; Context, Requirement,
  Gap, source-reference and prompt content never crosses the queue boundary.
- Worker database authority is least-privilege for Gap/Gap-link reads and inserts. Existing Worker
  grants supply the exact snapshot, Job and Usage capabilities.
- Safe logs may contain Account, Project, Job, Context/policy versions, counts, rule IDs, duration,
  status and bounded reason codes. Customer content, explanations, source references, affected
  Requirement IDs, prompt and raw Provider output are prohibited.

## Deferred

- Public AI-03 command API and its idempotency/error contract.
- Automatic AI-02 -> AI-03 orchestration.
- Hosted task registration, customer content, real Provider and paid-call recovery.
- Queue automatic retry and runtime Provider promotion/fallback.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J02; reread 2026-09-22
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-03; reread 2026-09-22
- [ADR-036](ADR-036-gap-detection-foundation.md)
- [ADR-037](ADR-037-gap-critical-rule-pack.md)
- [ADR-057](ADR-057-durable-outbox-delivery-runtime.md)
- Owner-approved 0074 contract and empty-Requirement clarification dated 2026-09-22.
