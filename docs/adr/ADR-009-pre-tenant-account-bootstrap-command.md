# ADR-009: Pre-tenant Account Bootstrap Command

- **Status:** Accepted
- **Date:** 2026-08-25
- **Story:** S1-B05 — Auth UI + Callback
- **Supersedes:** the implicit-only/no-route decision recorded in increment 0011 (`REQ-055`)

## Context

Increment 0011 intentionally exposed Account Bootstrap only as a dependency because no approved
frontend caller existed. S1-B05 now requires the explicit sequence `Session → Account Bootstrap →
/projects`. With no callable command, the frontend cannot complete that sequence. Tenant Context
also cannot precede this operation because the Account is created or resolved by the operation
itself.

## Decision

- Expose exactly one authenticated pre-tenant lifecycle command:
  `POST /api/v1/auth/bootstrap`.
- Require the existing Bearer JWT verification dependency; do not require `X-Account-ID`.
- Accept no request body and return `204 No Content` for both first execution and already-complete
  execution.
- Protect the command with authenticated identity only. An existing `invited` or `suspended`
  Membership is resolved as already bootstrapped and still returns `204`; this command grants no
  operational access, and tenant-authorized routes continue to require `active` Membership.
- Reuse the existing transactional, idempotent and concurrency-safe `BootstrapAccountUseCase`.
- Return no Account, Profile, Membership, role, identity or preference data. This command must not
  evolve into a hidden `/me` query.
- Map invalid credentials to `401 AUTH_REQUIRED`, Auth-provider infrastructure failure to
  `503 AUTH_PROVIDER_UNAVAILABLE`, and Bootstrap infrastructure failure to retryable
  `503 ACCOUNT_BOOTSTRAP_FAILED`.
- Preserve the existing safe Bootstrap events. JWT, Email, raw subject and Profile data remain
  prohibited from logs.
- Treat this as a narrow exception to the normal tenant-authorization rule: Tenant Context does not
  yet exist because the Account is created or resolved in this command. Any future pre-tenant
  mutation requires a separate accepted ADR.

## Consequences

The frontend can deterministically complete Bootstrap before entering `/projects`. Repeating the
command after a timeout or failure is safe. The API surface gains a command but no identity query,
Account selector, new data field, deployable, provider coupling or cross-module write path.

## Rejected

- Keep Bootstrap dependency-only: cannot satisfy the approved frontend sequence.
- Return Account or Profile data from the command: mixes command/query concerns and creates a hidden
  `/me` contract.
- Bootstrap directly from Next.js through Supabase/Postgres: bypasses the API Application boundary.
- Require Tenant Context: impossible before the operation creates or resolves the Account.

## Sources

- Sprint 1 Technical Backlog v1.0 — S1-B05
- Frontend UX State Management Specification v1.0
- System Architecture v2 and repository `AGENTS.md`
- Owner approvals dated 2026-08-25 defining the exact route, error, logging and no-payload contract
