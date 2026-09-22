# Development Record: 0031 Job Status API

[Test report](./test-report.md)

## Scope

- Increment ID: `0031-job-status-api`
- Story: `S1-E05 — Job Status API + SSE Enhancement`, API source-of-truth slice
- Status: Completed
- Scope: Tenant-scoped `GET /api/v1/jobs/{job_id}` with the approved minimal response contract,
  safe cross-tenant not-found behavior and sanitized persisted error fields.
- Explicitly deferred: SSE, frontend polling UI, progress-stage persistence/taxonomy, retry
  classification, Queue transport behavior and exposure of operational Job fields.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-E05 Job Status API and optional SSE; read 2026-09-05.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk) — Job Status API as client source of truth and polling fallback; read 2026-09-05.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit?usp=drivesdk) — TC-JOB-010 and async-state verification; read 2026-09-05.
- Repository `docs/architecture/system-architecture.md` — approved Job state vocabulary and source-of-truth boundary.
- [ADR-013 — Jobs and Transactional Outbox Boundary](../../adr/ADR-013-jobs-outbox-persistence.md)
- [ADR-018 — Job Status API Contract](../../adr/ADR-018-job-status-api-contract.md)
- Repository instructions (`AGENTS.md`)

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3101 | S1-E05; ADR-018 | `GET /api/v1/jobs/{job_id}` route with approved envelope | TC-3101 |
| REQ-3102 | Owner approval 2026-09-05; Data Dictionary | Canonical public `job_type` and documented status vocabulary | TC-3101, TC-3102 |
| REQ-3103 | API Contract; tenant authorization baseline | Account-scoped repository query and safe `404` | TC-3102, TC-3103 |
| REQ-3104 | API Contract; owner approval | Public fields limited to id, job_type, status, progress_stage, retryable and error | TC-3101, TC-3104 |
| REQ-3105 | API Contract; Data Dictionary | Only persisted sanitized `error_code`/`error_detail` are mapped to `error` | TC-3101 |
| REQ-3106 | Owner approval; ADR-018 | No invented retry policy, stage field, SSE transport or operational-field exposure | TC-3104, TC-3105 |

## Changes

- Added `JobStatusApplicationService` and a provider-neutral status view.
- Added `JobRepository.get_for_account` and SQLAlchemy Account-scoped filtering.
- Added the authenticated `GET /api/v1/jobs/{job_id}` router and exact response models.
- Registered the service and router in the API composition root.
- Added ADR-018 and contract/API tests.
- Kept `progress_stage` nullable because no approved persistence source exists; did not add a
  migration or invent a progress taxonomy.

## Structure Preservation

- FastAPI remains in the API adapter; the Application service depends on the Jobs UoW port.
- Tenant filtering is enforced in the Infrastructure repository query, not inferred from a client
  response or performed only after an unscoped public read.
- Domain and Job persistence structures remain unchanged; no new table, column or deployable was
  added.
- The public response excludes payload, account/project identifiers, attempts, correlation IDs and
  timestamps as required by the approved contract.
- SSE and frontend polling behavior remain deferred; no transport or UI assumption was introduced.

## Senior Review

- PASS: `job_type` is the only Job type exposed; `task_type` is rejected.
- PASS: missing and cross-tenant Jobs map to the same safe `404 RESOURCE_NOT_FOUND` response.
- PASS: response models use `extra="forbid"` and contain only approved public fields.
- PASS: `progress_stage` is explicitly nullable rather than backed by an unapproved field.
- PASS: retryability remains `false` until a separately approved classification exists.
- PASS: persisted error detail is exposed only through the approved sanitized error shape; no
  payload, traceback, provider response or secret is added.
- PASS: no SSE, retry, Queue or frontend polling policy was invented.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner approved the response contract and canonical `job_type` on 2026-09-05. The approved
contract deliberately leaves progress-stage persistence and retry classification for later
increments.

## Verification

See [test-report.md](./test-report.md). Focused API and contract tests passed; repository-wide
quality gates are recorded there after the final run.

## Remaining Risks

- A future increment must define the source and taxonomy of `progress_stage` if non-null progress
  is required.
- Retryable classification and SSE/Frontend polling require separate approved contracts.
- No hosted runtime evidence is claimed by this increment.

**Final status:** PASS
