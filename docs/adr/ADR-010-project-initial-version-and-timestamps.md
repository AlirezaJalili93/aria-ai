# ADR-010: Project Initial Context Version and Mutable Timestamps

- **Status:** Accepted
- **Date:** 2026-09-01
- **Story:** S1-C01 — Project Domain + Repository
- **Supersedes:** Detailed Data Dictionary v1.0 statement that `current_context_version` is `>=1`

## Context

A newly created Project has no Context Version yet. The previous Data Dictionary lower bound of one
would claim a Version that does not exist. The database architecture also required one explicit
owner for `updated_at`; mixing application writes with database defaults would make raw SQL,
migrations and future writers inconsistent.

## Decision

- A newly created Project has `current_context_version = 0`.
- The database enforces `current_context_version >= 0` and owns the default value of zero.
- The canonical Detailed Data Dictionary was corrected in place on 2026-09-01; the developer mirror
  and M002 use the same contract.
- PostgreSQL owns `updated_at` for mutable Sprint 1 tables through one `BEFORE UPDATE` trigger
  function. M002 attaches that trigger to `accounts`, `profiles` and `projects`.
- The trigger function uses a fixed empty `search_path`; execute authority is revoked from `PUBLIC`.
- Application code does not set `updated_at` for ordinary mutations.

## Consequences

The zero value means “no Context Version exists” without fabricating a related row. Every database
writer observes the same timestamp behavior. M002 owns both the Project table and the previously
deferred Identity timestamp triggers, so a fresh migration chain and downgrade/re-upgrade test are
required.

## Rejected

- Start at one without a Context Version row: violates the domain meaning and referential timeline.
- Let every application caller set `updated_at`: does not cover SQL migrations or other trusted
  writers and creates clock/implementation drift.
- Add trigger logic in M001 after it has shipped: violates migration immutability.

## Sources

- Detailed Data Dictionary v1.0, corrected 2026-09-01
- Production Data Architecture & Database Schema v2.0
- Database Migration Execution Plan v1.0 — M002
- Owner approvals dated 2026-08-31 and 2026-09-01
