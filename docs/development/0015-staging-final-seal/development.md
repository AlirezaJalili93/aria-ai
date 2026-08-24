# Development Record: Staging Final Seal

- Increment ID: `0015-staging-final-seal`
- Date: 2026-08-24
- Owner: Backend / Platform / Security
- Related plan/issue: S1-A03 and S1-B02 post-merge acceptance
- [Test report](./test-report.md)

## Scope

Seal the post-merge Staging state of increment 0014 with exact commit, pipeline, runtime-health,
database, security-advisor, and deployment evidence. This increment is documentation-only and does
not change application code, migrations, infrastructure configuration, product behavior, or
Production.

## Source Documents

- User instruction on 2026-08-24 to continue documentation-driven development, retain development
  and test Markdown for every increment, and complete senior review/debugging before delivery.
- [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit) — FINAL; synced 2026-08-24; exact-head verification, post-merge Staging execution, security/advisor gates, and evidence retention.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — synced 2026-08-24; S1-A03 hosted health/runtime evidence and S1-B02 Staging data prerequisites.
- [ADR-008](../../adr/ADR-008-alembic-migration-strategy.md) — Alembic ownership, main-only controlled Staging execution, and M001 deny-by-default Data API state.
- [Railway Variables Reference](https://docs.railway.com/variables/reference#git-variables) — read 2026-08-24; Git commit metadata is provided for GitHub-triggered deployments.
- [Pull request #7](https://github.com/AlirezaJalili93/aria-ai/pull/7), merge SHA `f8f94d30af5a8814e20cde29ff2526bebf350a43`, and its linked GitHub/Railway/Vercel deployment evidence.
- Supabase Staging project `hqgfqlvfwflbazsuhazs` direct catalog and advisor readback on 2026-08-24.

## Requirement Traceability

| Requirement | Source | Implementation or evidence | Tests |
|---|---|---|---|
| REQ-073 | Migration Plan: exact merged source passes CI and controlled Staging migration | main CI `32725919269`; migration run `32725919119` | TC-1501 |
| REQ-074 | S1-A03: hosted runtime proves deployed commit and internal readiness | Railway API/Worker deployment contexts and exact-SHA health payloads | TC-1502 |
| REQ-075 | ADR-008/Migration Plan: Staging is exact head, RLS protected, and not exposed to Data API roles before M010 | direct catalog/grant/policy/advisor readback | TC-1503 |
| REQ-076 | Quality rules: final evidence is linked, assumption-free, and passes repository gates | this development record and test report | TC-1504 |

## Assumptions and Clarifications

- Runtime SHA means the commit used by the deployed API/Worker images. A later documentation-only
  merge is not a runtime deployment and does not invalidate the sealed runtime SHA.
- The four `rls_enabled_no_policy` security-advisor INFO entries are the documented M001
  deny-by-default state. M010, not this increment, owns tenant policy selection.
- The two unused-index performance INFO entries are retained because the approved schema defines
  those membership lookup indexes and Staging has no representative workload yet.
- The 16 provider-owned table default-ACL entries are not current table grants. The current grant
  count is zero; every future public-table migration must retain the explicit-revoke guardrail until
  M010 defines approved Data API access.

**Unapproved assumptions:** None

## Changes

- Added this final evidence record and linked test report only.
- Recorded exact GitHub, Railway, Vercel, Supabase, health, migration, and advisor results without
  credentials or customer/product content.

## Architecture and Design Decisions

- No ADR is required because this increment records evidence and changes no decision.
- The final seal distinguishes repository `main`, deployed runtime source, and database migration
  head instead of treating them as one ambiguous version.
- Railway health excludes AI provider availability and continues to check only required internal
  infrastructure on readiness.

## Structure Preservation

- Only `docs/development/0015-staging-final-seal/` is added.
- No source, migration, deployment configuration, dependency, contract, schema, token, service, or
  product document is changed.
- Modular-monolith, API/Worker/Web topology, linear Alembic chain, and approved domain structure are
  preserved.

## Senior Review

- PR #7 Quality, Security baseline, Vercel Preview, main CI, controlled migration, Railway API, and
  Railway Worker all completed successfully.
- Hosted API live/ready payloads report the same full 40-character SHA as the active Railway
  GitHub deployment; both comparisons are true.
- Direct database readback confirms exact Alembic head, RLS on all four public tables, zero current
  `anon`/`authenticated` table grants, and zero policies as required before M010.
- Advisor state has no ERROR. INFO findings are explicitly routed and are not silently closed.
- No blocking senior-review finding remains for this sealed increment.

## Verification

The linked test report contains exact run IDs, deployment IDs, health payload results, database
counts, advisor routing, commands, and final status.

## Remaining Risks

- Provider-owned public-table defaults require explicit grant revocation in later public-table
  migrations until M010.
- Supabase Free and the current Railway trial are Staging-only; Production availability, backup,
  capacity, and budget approval remain outside this increment.
