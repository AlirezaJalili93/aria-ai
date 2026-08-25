# Development Record: 0017 Tenant Context

- Increment ID: `0017-tenant-context`
- Date: 2026-08-25
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B04 — Tenant Context Middleware`
- [Test report](./test-report.md)

## Scope

Implement the approved Account selector and Tenant Context dependency for future Account-scoped API
routes. Parse `X-Account-ID`, compose verified Identity/Bootstrap with the S1-B03 Membership Resolver,
return a server-authorized Tenant Context, emit the approved safe denial events, and enrich trace
metadata only after active Membership authorization.

Product endpoints, `/me`, `/accounts`, Project repositories, RLS policy batch M010, Account suspension
operation policy, frontend Account selection, and persistence of the selected Account are out of scope.

## Source Documents

Canonical Google Drive documents reviewed on 2026-08-25:

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-B04` AC and cross-account security case.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Tenant trust boundary, Header Contract, Error Envelope, and API security.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — Active Account Context, Membership authority, non-enumeration, and `AUTHZ-11`.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — `TC-ID-003`, `TC-ID-004`, tenant fixtures, and release blockers.
- Owner clarification dated 2026-08-25 approving exact 400/403 cases, safe message,
  `retryable=false`, denial reason codes, log event names, trace enrichment timing, and
  non-enumerating 403 behavior.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md),
  [data model](../../architecture/data-model.md), and
  [document-driven development policy](../../governance/document-driven-development.md).
- Current official Supabase changelog and PostgreSQL composite-index, pooling, and short-transaction
  guidance reviewed on 2026-08-25.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-065 | S1-B04 AC; owner clarification | `X-Account-ID` is the request-scoped Account selector, never authority | TC-1701, TC-1708 |
| REQ-066 | Owner clarification | missing/empty/invalid UUID → 400 `ACCOUNT_CONTEXT_REQUIRED` with exact safe envelope | TC-1702, TC-1703, TC-1704 |
| REQ-067 | Access Control; owner clarification | valid UUID with not-found/invited/suspended Membership → identical 403 `MEMBERSHIP_REQUIRED` | TC-1705, TC-1706, TC-1707 |
| REQ-068 | Owner clarification | `tenant.context_rejected` and `tenant.membership_denied` use exact safe reason codes | TC-1702–TC-1707 |
| REQ-069 | Access Control authorization flow | JWT → Bootstrap → Header parse → active Membership → Tenant Context | TC-1701, TC-1708 |
| REQ-070 | Owner clarification; observability contract | `account_id` enters Trace Context only after successful authorization | TC-1702–TC-1708 |
| REQ-071 | S1-B04 AC; Architecture v2 | Future repositories receive server-authorized Tenant Context; no product repository is invented | TC-1708, TC-1709 |
| REQ-072 | Supabase security guidance; S1-B04 scope | DB Membership remains authority; no JWT metadata authorization, schema, grant, or RLS change | TC-1709, TC-1710 |

## Assumptions and Clarifications

The owner approved the previously open transport/error/logging contract on 2026-08-25. This Story
creates the reusable dependency and Application Context but does not add a product route whose
response payload is not yet approved.

**Unapproved assumptions:** None

## Changes

- Added the provider-neutral `TenantContext`, resolver port, and Application use case in the Identity
  module. The context carries only the verified subject and the persisted Membership identifiers,
  role, and status.
- Added the FastAPI `ensure_bootstrapped_identity` and `require_tenant_context` dependency chain.
  `X-Account-ID` is parsed as a UUID, active Membership is resolved server-side, and trace enrichment
  occurs only after authorization succeeds.
- Added stable 400 `ACCOUNT_CONTEXT_REQUIRED` and reused the stable non-enumerating 403
  `MEMBERSHIP_REQUIRED` envelope. The OpenAPI components now define the approved header and errors;
  no unapproved product route was added.
- Added exact structured denial events and reason codes without JWT, subject, requested Account ID,
  or Membership data in log fields before authorization.
- Reused the existing `(account_id, user_id)` Membership lookup through a short pooled SQLAlchemy
  session. No migration, schema, RLS policy, grant, provider authority, or new deployable was added.
- Added contract-first API, Application, observability, non-enumeration, inactive-Membership, and real
  PostgreSQL cross-account coverage.

## Architecture and Design Decisions

- Dependency flow: Bearer verification → persistence bootstrap → header validation → requested
  Membership resolution → Tenant Context → trace enrichment.
- Bootstrap persistence and Account authorization remain separate. An already-bootstrapped identity
  with no active Membership may reach the Account-specific resolver, allowing the approved
  `invited`/`suspended` denial reason to be recorded without granting operational context.
- Application depends on the existing `MembershipResolver` port. Infrastructure owns SQLAlchemy
  session construction, and the API dependency owns HTTP/header/error adaptation.
- The externally visible 403 envelope is identical for missing Account, missing Membership,
  `invited`, and `suspended`; internal safe reason codes remain distinguishable in structured logs.

## Structure Preservation

- Modular-monolith Identity boundaries are unchanged; Domain/Application import no framework,
  SQLAlchemy, Supabase, or API code.
- The documented Python/FastAPI stack, existing database schema, Identity projection, and composite
  Membership uniqueness are preserved.
- No endpoint, UI, database field, default, provider, service, migration, or authorization role was
  invented. OpenAPI changes are reusable components only.
- No ADR is required because no consequential approved architecture decision was changed.

## Senior Review

- Confirmed fail-closed behavior for missing, empty, and malformed selectors and all non-active
  Membership states.
- Found and corrected an authorization-order defect during review: the original dependency reused
  the B02 active-context guard, which could stop `invited`/`suspended` identities before the selected
  Account resolver and suppress the required Tenant denial event. The final design preserves
  Bootstrap while deferring Account-specific authorization to S1-B04.
- Confirmed the requested Account ID never reaches Trace Context on 400/403 and is attached only
  after an active Membership result.
- Confirmed Account existence and Membership status cannot be inferred from the 403 response body.
- Confirmed database lookup uses the existing subject/account composite predicate and performs no
  write or schema mutation.
- Reviewed the complete diff for layering, exception safety, log privacy, enumeration resistance,
  type safety, and regression risk; no unresolved review finding remains.

## Verification

All required repository gates pass. The linked report contains the exact commands, environment,
expected/actual results, initial failures, corrections, and final status.

## Remaining Risks

- No product endpoint currently consumes the reusable Tenant Context dependency; endpoint-level
  adoption will be tested with each approved Account-scoped Story.
- Hosted Supabase/Railway runtime evidence is not required for this in-process authorization
  increment; real PostgreSQL behavior is covered using the repository's isolated integration target.
- The existing Starlette `httpx` deprecation and restricted pytest cache warnings remain non-blocking
  dependency/environment warnings and do not affect the authorization results.
