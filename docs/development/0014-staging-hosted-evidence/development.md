# Development Record: Staging Hosted Evidence

- Increment ID: `0014-staging-hosted-evidence`
- Date: 2026-08-24
- Owner: Backend / Platform / Security
- Related plan/issue: S1-A03 and S1-B02 hosted verification
- [Test report](./test-report.md)

## Scope

Record the controlled Staging migration, database-security, CI, and API-runtime evidence after
increments 0012 and 0013 reached `main`. Correct the developer-facing description of Supabase
provider-owned default ACL behavior and map Railway's documented native Git commit variable to the
provider-neutral release identity. This increment adds no product behavior, schema, endpoint,
policy, integration, service, or Production change.

## Source Documents

- User instruction on 2026-08-24 to continue development from the current approved documents,
  retain complete development/test records, and perform final senior review/debugging.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — FINAL; synced 2026-08-24; controlled Staging delivery, immutable revisions, exact-head verification, RLS/security exit gates, and evidence retention.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — synced 2026-08-24; S1-A03 hosted health and environment evidence and S1-B02 account-bootstrap infrastructure scope.
- [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md) — Alembic ownership, no dashboard DDL, no M001 Data API access, and main-only controlled Staging execution.
- [Documentation-driven development policy](../../governance/document-driven-development.md).
- [Railway Variables Reference](https://docs.railway.com/variables/reference#git-variables) — read 2026-08-24; `RAILWAY_GIT_COMMIT_SHA` is injected for GitHub-triggered builds and deployments.
- GitHub pull requests [#5](https://github.com/AlirezaJalili93/aria-ai/pull/5) and [#6](https://github.com/AlirezaJalili93/aria-ai/pull/6), plus the linked CI/CD artifacts.
- Supabase Staging project `hqgfqlvfwflbazsuhazs` hosted readback on 2026-08-24.

## Requirement Traceability

| Requirement | Source | Implementation or evidence | Tests |
|---|---|---|---|
| REQ-068 | Migration Plan: merge to `main` is the only Staging migration trigger | PR #5/#6 merge SHAs and successful main-only migration workflow runs | TC-1401 |
| REQ-069 | Migration Plan: Staging must reach the exact repository head | Alembic readback `0001_identity_access_hardening` | TC-1402 |
| REQ-070 | ADR-008: M001 has RLS and no Data API access before M010 | hosted RLS, grant, policy, and advisor readback | TC-1403 |
| REQ-071 | S1-A03/Railway reference: health exposes the GitHub-triggered deploy identity | native `RAILWAY_GIT_COMMIT_SHA` mapping with provider-neutral output | TC-1404 |
| REQ-072 | Quality rules: complete traceable records and mandatory gates | corrected 0013/README wording; this record and linked report | TC-1405 |

## Assumptions and Clarifications

- No tenant policy is selected here. The four `rls_enabled_no_policy` advisor entries are the
  documented deny-by-default M001 state; policy selection remains M010.
- Hosted `supabase_admin` default ACL entries are provider-owned and remain visible. They do not
  grant access to the current M001 tables after the explicit revoke. Until M010, every later Aria
  public-table migration must explicitly revoke current `anon`/`authenticated` privileges.
- The two unused-index advisor entries are INFO observations on an empty Staging dataset; no
  documented requirement authorizes removing the M001 membership lookup indexes.

**Unapproved assumptions:** None

## Changes

- Corrected the migration README and increment 0013 records to distinguish current-table grants,
  migration-owner defaults, and Supabase provider-owned defaults.
- Added API and Worker configuration mapping from Railway's native `RAILWAY_GIT_COMMIT_SHA` to the
  provider-neutral release identity, with native platform metadata taking precedence over a legacy
  literal `RELEASE_COMMIT_SHA`.
- Added this hosted evidence record and linked test report.

## Architecture and Design Decisions

- Alembic remains the migration authority and the single linear revision chain is preserved.
- No dashboard DDL, public policy, grant, service-role path, new deployable, or M010 behavior was
  introduced.
- The Railway change only restores documented runtime metadata mapping; health semantics remain
  unchanged.

## Structure Preservation

- Existing Alembic revisions, domain boundaries, deployment topology, and approved schema are
  unchanged.
- API and Worker keep their existing configuration objects and provider-neutral
  `release_commit_sha` output; only the documented Railway input mapping is added.
- No endpoint, event schema, domain module, dependency, deployable, database table/column, policy,
  or product flow is added or removed.

## Senior Review

- PR #6 uses a forward revision and leaves already-applied M001 immutable.
- Hosted current grants to `anon` and `authenticated` are zero on all four public tables, and RLS is
  enabled on all four, including `alembic_version`.
- The earlier wording overstated migration authority over provider-owned defaults. The corrected
  wording treats that boundary as an explicit forward guardrail and does not claim a capability the
  runtime role lacks.
- Advisor INFO findings are routed to their documented later step or retained index purpose; no
  blocking ERROR remains.
- Repository results and the current hosted preflight are recorded in the linked report; the
  exact-SHA post-merge acceptance is explicitly routed to increment 0015.

## Verification

See the linked test report for workflow IDs, exact revisions, advisor results, health payloads,
commands, and final status.

## Remaining Risks

- The native Railway mapping requires a `main` deployment before its exact hosted SHA can be
  accepted; the post-merge final seal and exact-SHA smoke are owned by increment 0015.
- Provider-owned default ACLs require an explicit current-table revoke in every future Aria public
  migration until M010 establishes the approved Data API access model.
- Supabase Free remains non-production Staging infrastructure with its documented availability and
  backup limitations; Production provisioning is outside this increment.
