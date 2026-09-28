# ADR-064: Scoped AI-02/AI-03 Generation Input Locks

- **Status:** Accepted for limited Worker lock remediation — owner approval 2026-09-28
- **Date:** 2026-09-28
- **Extends:** ADR-060, ADR-061 and ADR-063

## Problem

AI-02 and AI-03 used `LOCK TABLE ... IN SHARE MODE` during short finalization
transactions. PostgreSQL does not permit that mode with `SELECT` alone, so the
actual `aria_worker` runtime principal could not complete AI-02. The earlier
database-owner E2E concealed the privilege failure. Broad `UPDATE`, ownership or
RLS-bypass grants to `aria_worker` are prohibited by the owner-approved contract.

## Decision

Migration 0030 introduces two fixed, non-Data-API functions in the non-public
`aria_internal` schema. Each accepts typed Job, Account, Project and Context
Version identifiers, validates that exact running Job and its Project/version,
and locks only eligible Context Item rows; AI-03 additionally locks eligible
Requirement rows. The functions return `void`, never content. No relation name,
SQL text or arbitrary predicate is accepted. PostgreSQL releases the row locks
at transaction end.

The `aria_generation_lock_owner` role is `NOLOGIN`, non-superuser and
`NOBYPASSRLS`. It holds only the column-level read and row-lock privileges
required by these functions. RLS policies for that role are account-scoped via
a transaction-local setting established inside the validated function. Function
execution is revoked from `PUBLIC` and granted only to `aria_worker`; the Worker
receives no broad write grant. Both functions use an empty `search_path` and
schema-qualified references. The Worker remains non-owner and `NOBYPASSRLS`.

The existing finalization transaction first takes the tenant-scoped Project
`FOR UPDATE` lock. The composite Project foreign key prevents concurrent child
inserts while that lock is held, and scoped row `FOR SHARE` locks prevent updates
to the pinned eligible rows. Exact revision comparison then fails closed if the
eligible set changed before the lock was obtained. No external Provider call is
made while these locks are held.

This ADR changes neither the public API nor product behavior. The owner's
2026-09-28 scope clarification explicitly limits tenant scoping to this new
helper/Job path. The shared `aria_worker` role's pre-existing raw `SELECT`/RLS
policies remain unchanged, are out of scope for 0077, and do not block this
limited remediation. Their cross-tenant capability is a separate security
architecture concern requiring its own contract; this ADR neither claims raw
per-tenant SELECT nor authorizes a shared-credential or broad RLS redesign.

## Verification contract

- Complete 0077 under `aria_worker`, not database-owner authority.
- Positive helper calls for AI-02 and AI-03; wrong Job/Account/Project tuple
  rejected without returning content.
- Another tenant's rows remain mutable while the pinned tenant's rows are
  locked; pinned rows are mutable again after transaction end.
- Direct Worker `UPDATE`/`DELETE` on protected tables remains denied; the
  helper owner cannot log in or bypass RLS, and function execution is denied
  to public/API roles.
- Migration downgrade removes only this helper's functions, policies, grants,
  schema and dedicated owner role; it never grants broad privileges.

## Sources

- [ADR-063](ADR-063-controlled-synthetic-context-to-scope-integration.md) and
  the owner's 2026-09-28 limited-remediation approval and scope clarification.
- [PostgreSQL 16 LOCK](https://www.postgresql.org/docs/16/sql-lock.html) —
  privilege requirements and transaction-bound lock lifetime; checked 2026-09-28.
- [Supabase Database Functions](https://supabase.com/docs/guides/database/functions)
  — restricted `SECURITY DEFINER`, safe `search_path` and function grants;
  checked 2026-09-28.
