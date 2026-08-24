# Development Record: 0016 Membership Resolution

- Increment ID: `0016-membership-resolution`
- Date: 2026-08-24
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B03 — Membership Resolution`
- [Test report](./test-report.md)

## Scope

Implement the internal Identity Application resolver for selecting one requested Account only when
the authenticated subject has an active Membership in that Account. Support users with multiple
active Memberships, resolve Role and Status from PostgreSQL, and use a read-only tenant-scoped query.

Tenant transport or persistence, request headers/cookies/session behavior, Tenant Context middleware
(`S1-B04`), `/me`, `/accounts`, entitlement behavior, Account suspension policy, invitation flows,
Membership mutation, and M010 RLS policies are explicitly out of scope.

## Source Documents

Canonical Google Drive documents reviewed on 2026-08-24:

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-B03` acceptance criteria and `S1-B04` boundary.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Identity and Account execution sequence.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — Tenant resolution trust boundary and error baseline.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Membership identifiers and Role vocabulary.
- [Access Control & Authorization Matrix v1.0](https://docs.google.com/document/d/1Vc_THPDe1T4gF-np9dnBTibf9pW70wkIj0UvpXlYk70/edit) — active Membership authority, inactive denial, tenant isolation, and server-side Role authority.
- [Security & Threat Model v1.0](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit) — cross-tenant protection baseline.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — `TC-ID-003`, `TC-ID-004`, and tenant fixture requirements.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md),
  [data model](../../architecture/data-model.md), and
  [document-driven development policy](../../governance/document-driven-development.md).
- Current official Supabase changelog and PostgreSQL query/index guidance reviewed on 2026-08-24.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-057 | S1-B03 AC: multiple active Account Memberships | `ResolveActiveMembershipUseCase` selects the requested active Membership | TC-1601, TC-1606 |
| REQ-058 | S1-B03 AC; Access Control sections 2, 4, 17 | Candidate Account is accepted only after subject+Account Membership validation | TC-1602, TC-1604, TC-1606, TC-1611 |
| REQ-059 | Access Control sections 4 and 20; `TC-ID-003` | Infrastructure returns persisted Role and Status; Application accepts no client Role/Status | TC-1601, TC-1605, TC-1606 |
| REQ-060 | Access Control sections 3, 6 and 18; `TC-ID-004` | invited and suspended Memberships raise the same active-Membership denial | TC-1602, TC-1607 |
| REQ-061 | Architecture v2 layering | Application port/use case and SQLAlchemy adapter remain inside Identity module | TC-1605, TC-1608, TC-1611 |
| REQ-062 | S1-B04 backlog boundary; documentation-driven rule | No Header, Cookie, Session, endpoint, or Tenant middleware contract is invented in S1-B03 | TC-1603, TC-1608 |
| REQ-063 | Supabase/PostgreSQL query guidance; existing M001 constraints | Equality query uses the existing unique `(account_id,user_id)` index; no speculative migration | TC-1606, TC-1609 |
| REQ-064 | AGENTS.md quality gate; `.gitignore` generated-data boundary | Architecture validation ignores generated `.data` caches while preserving repository checks | TC-1608, TC-1612 |

## Assumptions and Clarifications

The canonical documents define the validity rule but do not define how a client communicates or
persists the current Account. That transport decision belongs to the separately planned `S1-B04`.
This increment therefore implements only the documented internal Membership resolution boundary and
does not add a public API contract.

The owner previously established `active|invited|suspended` as the approved Membership vocabulary,
with Access Control authoritative over the conflicting historical Data Dictionary value.

**Unapproved assumptions:** None

## Changes

- Added a shared Application Membership projection port and immutable `ResolvedMembership` DTO.
- Added `ResolveActiveMembershipUseCase`, which receives only verified Identity and a candidate
  Account identifier, loads Role/Status server-side, accepts only `active`, and fails closed when an
  adapter returns identifiers outside the requested subject+Account pair.
- Added a read-only SQLAlchemy adapter whose equality predicate is covered by the existing M001
  `UNIQUE(account_id,user_id)` index. No schema revision or dependency was added.
- Preserved Account Bootstrap behavior while moving its shared Membership DTO and inactive-state
  exception to the general Membership Application boundary.
- Added six focused Unit cases, five repository Contract cases, and three real PostgreSQL S1-B03
  cases covering multiple accounts, cross-user selection, inactivity, persisted Role, and no writes.
- Updated the API/module developer notes and added this linked development/test record pair.
- Corrected architecture validation to exclude the existing Git-ignored `.data/` evidence/cache
  directory, preventing third-party audit package Markdown from being treated as repository docs.

## Architecture and Design Decisions

No ADR is required: the change remains inside the documented Identity & Membership module and adds
no deployable, public endpoint, database schema, dependency, provider, or cross-module write.

## Structure Preservation

- The modular-monolith Identity boundary remains unchanged:
  Application Use Case → Application Port ← SQLAlchemy Infrastructure Adapter.
- Domain and Application import no FastAPI, SQLAlchemy, Supabase SDK, Header, Cookie, or Session API.
- No public route, OpenAPI shape, database migration, RLS policy, deployable, dependency, or event
  schema changed.
- `S1-B04` retains ownership of Account transport and Tenant Context propagation; `/me` and
  `/accounts` remain unimplemented because their exact payload and active-account transport are not
  specified for this Story.

## Senior Review

Senior review completed after the first full regression run:

1. **Resolved — fail-closed adapter boundary (HIGH):** the SQL predicate correctly constrained both
   identifiers, but the Application initially trusted the adapter result. The use case now rejects a
   returned Membership whose `user_id` or `account_id` differs from the requested pair, and a focused
   test proves this invariant.
2. **Verified — inactive states:** invited and suspended rows remain persisted but cannot create an
   operational Membership Context; both use the same non-enumerating denial.
3. **Verified — multi-account correctness:** no first/oldest/arbitrary Membership fallback exists;
   only the explicitly supplied candidate Account is evaluated.
4. **Verified — server authority:** Role and Status originate from the database adapter. The use case
   has no client Role/Status input and accepts no JWT custom claim as Membership authority.
5. **Verified — query/index fit:** the subject+Account equality query uses the existing M001 unique
   composite index; adding a migration or duplicate index would be speculative and unnecessary.
6. **Verified — scope and structure:** no transport contract, endpoint, middleware, Account state
   policy, RLS policy, logging event, or dependency was invented.
7. **Resolved — generated-cache validation boundary:** the dependency audit populated `.data/uv-cache`
   with third-party Markdown whose relative links are intentionally incomplete outside its package.
   The architecture walker now skips the already Git-ignored `.data` root, and a Contract Test locks
   that boundary without weakening checks on any publishable repository artifact.
8. **Verified — hosted delivery:** PR #9 and post-merge `main` CI passed independently. Railway
   deployed the API from exact merge SHA `04bf101d0bc4ab617a8f3d24bc6ba492716f9a02`;
   live/readiness returned 200 with configuration, database, and queue passing. The Worker correctly
   reported no deployment needed because its watched paths did not change.

## Verification

Focused Unit/Contract checks, real PostgreSQL integration, repository lint/type checks, Web/API/Worker
regression, production builds, architecture validation, dependency audit, and secret scan passed. The
final aggregate commands and exact counts are recorded in the linked test report. The report also
records PR CI, post-merge CI, Railway commit status, and exact-SHA hosted smoke evidence.

## Remaining Risks

- The canonical documents still do not define how the current Account is carried or persisted. That
  decision remains a required clarification for `S1-B04`; this Increment intentionally exposes no
  runtime path until it is approved.
- M010 RLS policy selection remains a later documented increment. Existing Identity tables remain
  RLS-enabled and unavailable to `anon`/`authenticated` Data API roles by default.
