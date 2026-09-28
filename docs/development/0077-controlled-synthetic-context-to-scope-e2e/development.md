# Development Record: 0077 Controlled Synthetic Context-to-Scope E2E

- **Status:** COMPLETE — isolated synthetic 0077 gate passed under `aria_worker`
- **Increment ID:** `0077-controlled-synthetic-context-to-scope-e2e`
- **Source sync date:** 2026-09-27
- [Test report](./test-report.md)

## Scope

Implement only the owner-approved, isolated ADR-063 synthetic integration gate. AI-01
establishes Context Version N; explicit internal commands then execute AI-02, AI-03
and AI-05 against exactly N. The existing authorized Gap dismissal command is the
only permitted way for a synthetic test actor to waive an open Critical Gap.

## Source Documents

- [ADR-063](../../adr/ADR-063-controlled-synthetic-context-to-scope-integration.md) — owner-approved 2026-09-27.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — E2E-01/02; reread 2026-09-27.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — isolated integration and negative paths; reread 2026-09-27.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-01/02/03/05; reread 2026-09-27.
- [Sprint 1 Acceptance & Demo Plan](https://docs.google.com/document/d/1cNO4P5hBIzgQAvNVAnOdfI84IyTQj8UXxdN9GfGvb1Y/edit) — full Product E2E remains separate; reread 2026-09-27.
- [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md), [ADR-059](../../adr/ADR-059-context-structuring-command-synthetic-e2e.md), [ADR-060](../../adr/ADR-060-requirement-generation-runtime-foundation.md), [ADR-061](../../adr/ADR-061-gap-detection-runtime-foundation.md), [ADR-062](../../adr/ADR-062-scope-generation-runtime-foundation.md).
- [ADR-064](../../adr/ADR-064-generation-input-row-lock-privileges.md) — limited Worker lock remediation approved 2026-09-28.
- Owner's 2026-09-28 scope clarification — new helper/Job path must be tenant-scoped; pre-existing raw Worker `SELECT`/RLS is unchanged and deferred to a separate security contract.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-7701 | ADR-063 accepted boundary | `tests/e2e/controlled_context_to_scope_api.py`, `controlled_context_to_scope_worker.py`, `run-context-to-scope-controlled.ps1` | TC-7701 |
| REQ-7702 | ADR-063; ADR-060/061/062 | Exact N assertion in both E2E Python scripts; existing pinned-revision PostgreSQL regressions | TC-7702, TC-7706 |
| REQ-7703 | ADR-063; ADR-042; J03/J04 | `ClarificationService.dismiss_gap` used by the API harness; no direct Gap status SQL | TC-7703 |
| REQ-7704 | ADR-063; ADR-057/060/061/062 | PostgreSQL Relay → Redis/Celery queue → Worker, duplicate delivery and Draft conflict | TC-7704, TC-7705 |
| REQ-7705 | ADR-063 negative gate | Dedicated DB guard, PostgreSQL regressions, log/queue assertions and per-Job queue cleanup | TC-7706, TC-7707, TC-7708 |
| REQ-7710 | Owner-approved 2026-09-28 Worker lock remediation and scope clarification; ADR-064 | Migration 0030, AI-02/AI-03 scoped row-lock helpers, Job-bound Application port; no raw Worker RLS changes | TC-7710, TC-7711 |

## Assumptions and Clarifications

- Owner approval of ADR-063 on 2026-09-27 clarified that AI-01 establishes N; only
  AI-02/03/05 are pinned to it. The test actor may dismiss synthetic Critical Gaps
  only through the existing authorized Application command.
- Owner clarification on 2026-09-28 scoped tenant isolation to the new helper/Job
  path. Existing shared-credential raw `SELECT`/RLS behavior is an independent,
  deferred security architecture concern and does not block 0077.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-063 and added its link to the ADR index.
- Added the immutable `context_to_scope_synthetic_fa_v1` Persian fixture with a stable ID.
- Added a guarded, test-only API orchestrator. It migrates and resets only a database
  named `aria_0077_test...`, seeds one synthetic tenant/project/source, and explicitly
  schedules AI-01/02/03/05 through their accepted Application commands.
- Added a separate Worker test process. Each Job passes through the existing durable
  PostgreSQL Relay, real local Redis/Celery queue and accepted Worker consumer. Queue
  payload is exactly identifier-only; each per-Job queue is consumed and deleted.
- The harness first proves open Critical Gaps block AI-05 with no new Job. It then
  dismisses them via `ClarificationService.dismiss_gap`, explicitly schedules AI-05,
  and asserts one Requirement set, dismissed Gaps, one Draft @ N and Job success.
- Added the scoped runner, negative database-guard test, existing-Draft/replay checks,
  PostgreSQL negative suites and the `npm run test:context-to-scope-e2e` command.
- Added Migration 0030 with a private schema, non-login/non-RLS-bypass helper owner,
  account-scoped RLS policies and two fixed Job-bound row-lock functions. Both
  Worker repositories now use those functions, not table-wide locks. The
  Application port passes the immutable Job ID; no public API was added.
- Added PostgreSQL positive/negative privilege tests and exercised Migration 0030
  downgrade/re-upgrade without broad Worker grants.

## Structure Preservation

- PASS. The owner-approved limited Worker runtime and Alembic Migration 0030
  changed; no Domain, public API, production composition or deployment artifact
  changed. The accepted schedulers, consumers,
  transactional Outbox, K02 and K01 boundaries are reused without bypass.
- The sequential orchestration exists only under `tests/e2e/`. No automatic chaining,
  customer-data path, paid Provider, hosted activation, K05 publication or new
  deployable service was introduced.

## Senior Review

- **Contract parity:** PASS for the isolated workflow. AI-01 establishes N and
  downstream commands pin N; the full journey now runs under `aria_worker`.
  Open Critical Gap blocks scheduling before an AI-05 Job/Usage attempt. Dismissal
  is an authorized human-action command, not SQL mutation.
- **Recovery and safety:** PASS for the isolated workflow. Existing PostgreSQL tests execute changed-input
  fail-closed, post-AI mismatch, duplicate delivery, atomic rollback/recovery,
  existing Draft and Tenant A/B denial. The local queue is consumed and deleted;
  a Redis DB-15 scan found no `aria_0077_*` keys after the gate.
- **Privacy:** PASS. Fixture and generated text are barred from API/Worker output;
  queue envelope permits exactly `message_version`, `outbox_event_id`, `job_id`.
  No Provider credential, customer content or hosted runtime is used.
- **Corrections during review:** Moved Alembic upgrade outside the event loop,
  bound the required trace context, corrected a keyword-only repair policy,
  fixed Kombu queue cleanup and replaced an English marker with a versioned
  synthetic Persian fixture. A subsequent least-privilege review exposed a
  pre-existing runtime defect: AI-02 executes `LOCK TABLE public.context_items IN
  SHARE MODE`, but `aria_worker` cannot acquire that lock. AI-03 likewise directly
  locks `context_items` and `requirements` without the required privileges.
  A read-only, rolled-back PostgreSQL permission check confirmed both denials.
  No broad table privilege was granted to make this test green. A dedicated
  NOLOGIN owner with RLS-scoped `FOR SHARE` helpers now locks only eligible rows.
  The downgrade first failed because `USAGE` on `public` had not been revoked;
  that cleanup was corrected and downgrade/re-upgrade passed.

## Verification

See [test-report.md](./test-report.md). The Redis-backed 0077 command was rerun
under `aria_worker` after the scope clarification and passed its full journey
and 4 API + 9 Worker PostgreSQL cases. Full `npm test` passed with API 608
passed/1 hosted-only skip and Worker 188 passed/0 skipped. `npm run lint` and
`npm run typecheck` passed. `npm run validate` passed after both records were
finalized.

## Remaining Risks

- The Job-bound helpers prevent cross-tenant targeting through their API, but
  existing raw `aria_worker` SELECT policies on Context Items and Requirements
  remain permissive across tenants. The owner explicitly deferred this shared
  credential/RLS concern to a separate security architecture contract; 0077
  makes no claim that raw Worker SELECT is tenant-scoped.
- One hosted Supabase upload-security test remains intentionally skipped because
  `RUN_HOSTED_UPLOAD_SECURITY` was not enabled. This local increment neither
  authorizes nor claims hosted evidence.
- Fake Providers can prove wiring and deterministic regression only, not model quality.
- This is not full Login-to-Scope product acceptance or human UX validation.
