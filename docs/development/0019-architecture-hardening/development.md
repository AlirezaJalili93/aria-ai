# Development Record: 0019 Architecture Hardening

- Increment ID: `0019-architecture-hardening`
- Date: 2026-09-01
- Owner: Codex (implementation and senior review)
- Related review: owner-approved P1/P2/P3 corrections before `S1-C01/S1-C02`
- [Test report](./test-report.md)

## Scope

Close the approved migration, Bootstrap, Tenant Context, Web Bootstrap, timestamp, structured
logging, callback-reason, and Account Discovery contract findings before Project API work. This
increment defines but does not implement the separate read-only Account Discovery query.

## Source Documents

- Owner architecture review and ordered P1/P2/P3 corrections dated 2026-09-01.
- Existing accepted [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md),
  [ADR-009](../../adr/ADR-009-pre-tenant-account-bootstrap-command.md), and increments
  [0013](../0013-staging-data-api-hardening/development.md),
  [0017](../0017-tenant-context/development.md), and
  [0018](../0018-auth-ui-bootstrap-route/development.md).
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md),
  [data model](../../architecture/data-model.md), and
  [document-driven development policy](../../governance/document-driven-development.md).
- Current official Supabase migration/RLS guidance and changelog reviewed 2026-08-31.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-080 | Owner P1-1 | Downgrade never grants broad Data API/default privileges | TC-1901, TC-1902 |
| REQ-081 | Owner P1-2 | Bootstrap maps only declared application/infrastructure failures | TC-1903, TC-1904 |
| REQ-082 | Owner P1-3 | Tenant Context authenticates and resolves Membership without Bootstrap | TC-1905, TC-1906 |
| REQ-083 | Owner P2-4 | `/projects` does not repeat the explicit post-auth Bootstrap command | TC-1907 |
| REQ-084 | Owner P2-6 | One documented and tested `updated_at` ownership strategy | TC-1908 |
| REQ-085 | Owner P2-7 | Web events use a stable structured schema and safe fields | TC-1909 |
| REQ-086 | Owner P3-8 | Callback internal failure reasons distinguish approved failure classes | TC-1910 |
| REQ-096 | Owner P2-5 | Account Discovery stays separate from Bootstrap and exposes only the approved selection fields | TC-1912 |

## Assumptions and Clarifications

ADR-011 records Account Discovery as a separate pre-tenant query. It exposes only active
Membership `account_id` and `role`; Account naming and multi-Account selector UX remain outside
scope until independently documented. No discovery endpoint is implemented in this increment.

**Unapproved assumptions:** None

## Changes

- Made M001a downgrade asymmetric and fail-closed: it removes only its RLS state and never restores
  Data API/default privileges.
- Added the declared `AccountBootstrapInfrastructureError` boundary. SQLAlchemy failures are
  translated in Infrastructure; the API maps only declared Bootstrap failures to the stable 503.
- Removed implicit Bootstrap from `require_tenant_context`; JWT verification now feeds Tenant
  Context/Membership resolution directly.
- Removed the second Bootstrap invocation from the authenticated `/projects` page.
- Standardized Web auth events on the versioned backend-compatible structured schema and safe
  metadata allowlist.
- Split callback failures into safe invalid/expired, configuration, provider, rate-limit,
  Bootstrap, authentication and unexpected reason classes.
- Accepted ADR-010 for database-managed mutable timestamps and ADR-011 for distinct pre-tenant
  Account Discovery/Selection.

## Structure Preservation

- Identity Domain/Application remains provider-neutral; SQLAlchemy translation stays in
  Infrastructure and FastAPI mapping stays in API dependencies.
- Tenant Context remains an API dependency over an Application resolver and contains no Bootstrap
  or direct database logic.
- Bootstrap remains the command-only ADR-009 route with a 204 body; Account Discovery is a
  separate read-only contract and adds no hidden `/me` response.
- The existing modular monolith, Next.js/FastAPI stacks and deployable topology are unchanged.

## Senior Review

- **Migration safety:** PASS. The HIGH downgrade privilege escalation was removed and proven on
  real PostgreSQL across downgrade/re-upgrade.
- **Failure taxonomy:** PASS. Broad Bootstrap exception mapping was removed; an unexpected
  programming error remains an internal 500 and is not mislabeled as retryable infrastructure.
- **Identity/Tenant separation:** PASS. Tenant resolution performs one authorization lookup and no
  implicit Bootstrap write.
- **Web observability:** PASS. Event envelopes are stable and callback failure reasons remain safe;
  JWT, Email and credential-bearing callback parameters are excluded.
- **Scope:** PASS. No Account/Profile field, discovery implementation, Project endpoint or UI was
  invented.

## Verification

All focused, PostgreSQL integration, Web, contract, build, security and repository gates passed.
Exact commands and results are recorded in the linked test report.

## Remaining Risks

- ADR-011 is a contract only; its query implementation belongs to the next approved increment
  before S1-C02 consumes Account context.
- Multi-Account display labels and selector UX remain deliberately undefined.
