# Development Record: 0061 — Cross-Tenant Security Suite

- **Status:** COMPLETE
- **Increment:** S1-L03
- **Source sync date:** 2026-09-13
- [Test report](./test-report.md)

## Scope

Implement the approved Tenant A/B security regression suite across account selection, Project,
Context, Requirement, Gap, Scope and Job boundaries; preserve uniform safe-not-found behavior;
verify tenant-scoped repositories and fail-closed RLS/Data API access; and add a generic audit event
that never performs an out-of-Tenant existence probe.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-L03; revision `ANLCKQlujALNdyJZbNLOedCGxjlG8UwcE_pkF1cT3bEgoVASWO7u08ikQ51FIfnZfHk9DV_8iMg67AayWjRPBbEjFROHXn7_gAUAEruNFw`; synchronized 2026-09-13
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — authorization flow, safe not found, audit and release blockers; revision `ANLCKQlS3_bYh2cD71jfVcTyj8djXHY92OX7_gKc_VgOVkmgB4TgRXRHcpCuVCm9BAurjPpXLMaISwY5MrurJggBWGbg5YH6-ONApOYfKQ`; synchronized 2026-09-13
- [Security & Threat Model v1.0](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit) — T-TEN-01 through T-TEN-04 and T-DB-01; revision `ANLCKQnAsByzIs7mkwvTE9FP2_NELh8mYSLtuZFs4J2ksuYtXoW0hdxlBOwkCXTQHsWg9ARcWz6g2M0Y8pRA3o-4F_wnJrIKLCDfxihE_g`; synchronized 2026-09-13
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — Tenant A/B fixture and TC-TEN-001 through TC-TEN-010; revision `ANLCKQk-ctJjgTZekdOapwEktt_MSGfZgAlNPiIZdhPj_TqA9rvIIfhXe3CzdKsGubMOZlMCGMm6mdGb2dd5LwBXcEm1tXtst0G58c2juQ`; synchronized 2026-09-13
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — account context, private-resource error and canonical Scope selectors; revision `ANLCKQmi4ajmAQKOqmEChZFQ1DwG9dhMvKVcmjndEFCmrTjgmGqehXiuwbku8FBkZfoJDrR9dfi7RmSZ57KvMGDYeXn5kcbYzVMlzJwjlQ`; synchronized 2026-09-13
- Owner-approved 0061 contract and refinement dated 2026-09-13
- [ADR-048](../../adr/ADR-048-cross-tenant-security-suite.md) — implementation decision

Drive documents remain canonical; this record is the developer-facing implementation mirror.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6101 | S1-L03; TC-TEN fixture rule | Simultaneous independent Tenant A/B PostgreSQL fixtures | TC-6101 |
| REQ-6102 | Account/API contract | Missing/empty/malformed Account selector is 400; unauthorized valid Account is 403 | TC-6102 |
| REQ-6103 | T-TEN-01; TC-TEN-001/002 | Project read/update/delete tampering equals missing safe 404 | TC-6103 |
| REQ-6104 | T-TEN-02; TC-TEN-003/004/005 | Context, Requirement and Gap child-resource tampering equals missing safe 404 | TC-6104 |
| REQ-6105 | Owner Scope refinement; TC-TEN-006/007 | Scope public selectors and Job identifiers remain tenant-scoped | TC-6105 |
| REQ-6106 | AUTHZ-12; TC-TEN-009/010 | Repository internal UUID filtering, RLS and Data API denial | TC-6106 |
| REQ-6107 | Owner logging refinement | Bounded `resource.access_denied` with no lookup/existence/content leakage | TC-6107 |
| REQ-6108 | Release blocker policy | Suite is wired into CI and preserves public routes/contracts | TC-6108 |

## Assumptions and Clarifications

- The owner confirmed that public Scope tests use `project_id + version_no`; internal Scope UUIDs
  remain Repository/Database/RLS-only.
- The owner confirmed that missing and foreign resources are indistinguishable, and audit logging
  must not perform a secondary lookup.
- Artifact, Share and Storage resources are not publicly implemented in the current increment and
  are not silently substituted with test-only endpoints.

**Unapproved assumptions:** None

## Changes

- Added a real PostgreSQL Tenant A/B fixture and a single security suite covering Account selector
  tampering and Project, Context Source/Item, Requirement, Gap, Scope Draft/Version and Job IDOR.
- Asserted identical missing/foreign `404 RESOURCE_NOT_FOUND` envelopes and verified every attempted
  mutation leaves Tenant B state unchanged.
- Added Repository checks for internal identifiers and database checks for RLS, zero Data API grants
  and denial of an exact internal Scope Version UUID under the `authenticated` role.
- Added bounded `resource.access_denied` logging at the shared safe-not-found boundary. The handler
  maps only route templates to a controlled resource vocabulary and is fail-open.
- Removed guessed Requirement, Gap, Clarification and Job identifiers from denial trace/log paths;
  resolved resource IDs continue to be logged only after successful tenant-scoped resolution.
- Wired a static security contract into `test:ci` and recorded the decision in ADR-048.

## Structure Preservation

- No endpoint, deployable, Domain field, resource selector or provider integration is introduced.
- Authorization remains Bearer identity, active Membership, tenant-scoped Application/Repository
  query and RLS/Data API defense in depth.
- Public Scope addressing remains `project_id + version_no`; UUIDs do not leak into the API.

## Senior Review

**Status:** PASS.

Senior review traced the full authorization order, inspected every modified logging path, verified
the shared handler cannot access a Repository/Database, and checked that only route templates and
bounded fields reach the generic audit event. The first real Tenant A/B execution exposed guessed
child-resource IDs in legacy Requirement/Gap denial logs and a guessed Job ID enriched before
authorization. Those findings were corrected and regression-tested. Review also added fail-open
isolation around the new audit emission so observability cannot replace a safe 404 with a 500.

## Verification

Focused contract, API and real PostgreSQL tests pass. Full repository lint, strict type checking,
tests, builds, architecture validation, development-record validation, secret scan and whitespace
check pass; exact evidence is recorded in [test-report.md](./test-report.md).

## Remaining Risks

- Artifact, Share and Storage public-resource suites remain deferred until those routes exist.
- Safe missing/foreign behavior is contractually identical; no timing-equivalence threshold exists
  in approved documents and none was invented.
