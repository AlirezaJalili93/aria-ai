# Development Record: 0093 Scope Review Projections and Secure Browser Bootstrap

- Increment ID: `0093-scope-review-projections-browser-bootstrap`
- Date: 2026-10-05
- Owner: Platform/API/Web Engineering
- Related domain: Scope Sharing / Public Review Bootstrap
- [Test report](./test-report.md)

## Scope

Add safe authenticated read projections for exact-version Share Links and the terminal public
decision, expose exact-version `decision_status` in public resolution, and add a fragment-only,
volatile-memory-only browser bootstrap at `/scope-review`. Defer SCR-14..17 functional UI and all
new mutations to 0094 or the existing 0090/0091 commands.

## Source Documents

- Owner-approved frozen `0093 Scope Review Projections & Secure Browser Bootstrap` contract,
  2026-10-05.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-08 Sharing and Guest Review; synchronized 2026-10-05.
- [Engineering Backlog v1.0](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — EP-E3/E4; synchronized 2026-10-05.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — SCR-14..17; synchronized 2026-10-05.
- [Frontend UX State Management Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — SH/GA states; synchronized 2026-10-05.
- [ADR-080](../../adr/ADR-080-scope-review-projections-and-browser-bootstrap.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9301 | Owner 0093.1 | Exact-version Share projection with role/creator visibility and server `can_revoke` | TC-9301, TC-9306 |
| REQ-9302 | Owner 0093.2 | Exact-version discriminated decision projection; comment only in authorized response | TC-9302, TC-9307 |
| REQ-9303 | Owner 0093.3 | Public resolve returns status from the bound immutable ScopeVersion | TC-9303, TC-9306 |
| REQ-9304 | Owner 0093.4 | Fragment bootstrap clears URL before body-token resolution and persists nothing | TC-9304, TC-9308 |
| REQ-9305 | Owner 0093.5 | Static public title; no live Project/Client lookup or 0094 controls | TC-9305 |
| REQ-9306 | Owner security guardrails | Allowlisted DTOs, safe 404 and no token/hash/comment telemetry | TC-9301, TC-9302, TC-9307, TC-9308 |

## Assumptions and Clarifications

The owner froze the projection fields, role visibility, exact-version status source, fragment URL,
bootstrap order, volatile-memory-only behavior, intentional refresh loss, static public title and
0093/0094 boundary.

**Unapproved assumptions:** None

## Changes

- Added ADR-080 and OpenAPI projection/resolve contracts.
- Added authenticated tenant-scoped Share/Decision query methods and allowlisted API DTOs.
- Added exact bound-Version `decision_status` to public resolver output.
- Added `/scope-review` secure fragment consumer and body-token resolve adapter without the 0094
  review/decision UI.
- Added contract, Application/API/PostgreSQL and Web bootstrap tests.

## Structure Preservation

- Domain remains free of FastAPI, SQLAlchemy, browser and framework imports.
- No new deployable service, schema migration, public DB grant or mutable endpoint was added.
- Read projections use existing Application ports; SQLAlchemy remains Infrastructure-only.
- Raw capability is never placed in path/query, persistent storage, response, logs or Analytics.
- Existing 0090/0091 mutation and 0092 revision boundaries remain unchanged.

## Senior Review

- PASS: authenticated queries resolve and re-check the exact tenant/project/version and never
  infer a latest ScopeVersion.
- PASS: Member visibility is repository-filtered by creator; Owner/Admin receive all links and
  `can_revoke` remains presentation-only.
- PASS: public resolution returns the status of the historical bound Version after a newer Version
  exists and the bound Version becomes superseded.
- PASS: the fragment is removed before the body-token network call; no browser persistence or
  Analytics path exists in the bootstrap.
- PASS: API DTOs exclude token, token hash, version hash, creator identity and Account internals;
  Change Request comment is absent from observability output.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- The full Share Settings and Guest Review experience remains explicitly deferred to 0094.
- Browser extensions or same-page JavaScript can observe a fragment before bootstrap; 0094 must
  preserve the no-third-party-before-clear ordering.

**Final status:** PASS
