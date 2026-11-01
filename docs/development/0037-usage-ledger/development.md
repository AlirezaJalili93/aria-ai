# Development Record: 0037 Usage Ledger

- Increment ID: `0037-usage-ledger`
- Date: 2026-09-05
- Owner: AI/Platform Engineering
- Related plan/issue: `S1-G05 — Usage Ledger`
- [Test report](./test-report.md)

## Scope

Implement the approved provider-neutral, append-only Usage Ledger: physical PostgreSQL schema,
worker-only least-privilege authority, Application append port, Worker infrastructure adapter and
database/contract tests. No public endpoint, provider adapter, pricing catalog or G06 logic is in
scope.

## Source Documents

- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit?usp=drivesdk) — UsageRecord fields, ledger ownership, index/RLS/retention baselines; modified 2026-09-01 and read 2026-09-05.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk) — provider-neutral execution and traceability; read 2026-09-05.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-G05 scope; read 2026-09-05.
- [Production Data Architecture v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit?usp=drivesdk) — append-only Usage and historical retention; read 2026-09-05.
- [AI FinOps & Cost Governance v1.0](https://docs.google.com/document/d/1s7aXZAIiZl4SOY4PtMO9KHoVbQ9GDQ-W8Zd4ilItquc/edit?usp=drivesdk) — usage trace fields and cost precision intent; read 2026-09-05.
- [Canonical API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit?usp=drivesdk) — raw Usage remains internal and no public endpoint is added; modified 2026-09-01 and read 2026-09-05.
- Owner-approved S1-G05 contract and clarification dated 2026-09-05 — exact schema tightening,
  `aria_worker`, access matrix and `ON DELETE RESTRICT` decisions.
- [ADR-024](../../adr/ADR-024-usage-ledger-and-worker-role.md).
- [Current Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security) — grants/RLS and bypass-role behavior; read 2026-09-05.
- Repository `AGENTS.md` — documentation-driven development and quality gates.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3701 | Data Dictionary §22; approved G05 table contract | `0007_usage_records.py` creates the exact required/nullable fields and precisions | TC-3701 |
| REQ-3702 | G05 tightening | `prompt_version` and `correlation_id` are NOT NULL; `retry_no` is canonical | TC-3701, TC-3704 |
| REQ-3703 | G05 numeric/status contract | DB CHECKs enforce non-negative token/latency/retry/cost and three statuses; cost has no default | TC-3702 |
| REQ-3704 | G05 append-only contract | Trigger rejects UPDATE/DELETE; Application exposes only `append()` | TC-3703, TC-3707 |
| REQ-3705 | G05 security clarification; Supabase RLS guidance | RLS + worker insert policy; `aria_worker` non-bypass INSERT-only; API/Data API denied | TC-3704, TC-3705 |
| REQ-3706 | G05 FK clarification | Account/Project/Job use `ON DELETE RESTRICT` | TC-3701, TC-3706 |
| REQ-3707 | AI Workflow; G05 Provider/Model decision | Provider/model remain data; no provider branching/SDK in Application | TC-3707 |
| REQ-3708 | API Contract; G05 non-goals | No public raw Usage endpoint; G02/G03/G06 remain deferred | TC-3707 |
| REQ-3709 | Migration quality gate | Fresh upgrade and downgrade/re-upgrade preserve grants and schema safely | TC-3708 |

## Assumptions and Clarifications

The owner explicitly selected `aria_worker` as the only direct writer and `ON DELETE RESTRICT` for
all three parent links. The migration creates/normalizes that role without a password; secret
provisioning and rotation remain external. The role is retained on downgrade to avoid deleting a
pre-existing/external runtime principal. `aria_api` is denied if present but is not created by G05.

**Unapproved assumptions:** None

## Changes

- Added Alembic revision `0007_usage_records` with exact fields, constraints, indexes, RLS,
  privileges, insert policy, append-only trigger and restrictive FKs.
- Added provider-neutral Worker `UsageRecord` and `UsageLedger.append()` Application contract.
- Added SQLAlchemy Worker adapter that emits INSERT without implicit RETURNING/raw read authority.
- Added PostgreSQL, Worker unit and repository contract tests.
- Added ADR-024 and synchronized developer-facing data/migration/Worker documentation.
- Added exact Worker SQLAlchemy/asyncpg dependency pins and refreshed the lockfile.

## Architecture and Design Decisions

- Metering stays inside the modular monolith/Worker boundary; no deployable service was added.
- Application does not know the database role, SQLAlchemy or any Provider identity.
- The adapter accepts Provider/Model strings as recorded data and contains no branching.
- RLS and explicit grants jointly enforce the worker-only append path.
- Pricing catalog/FK, actual Provider adapters and public/raw Usage queries remain deferred.

## Structure Preservation

- Existing Web/API/Worker deployables and modular-monolith boundaries are unchanged.
- Migration ownership remains Alembic under ADR-008.
- Worker Application depends only on a provider-neutral port; SQLAlchemy remains in Infrastructure.
- OpenAPI is unchanged because G05 explicitly forbids a public raw Usage endpoint.
- No Provider SDK/model name, pricing table, task vocabulary, retry policy or external service was added.

## Senior Review

- PASS: schema types, precision, nullability, status vocabulary and non-negative constraints match
  the approved contract; `estimated_cost` has no default.
- PASS: `aria_worker` is LOGIN-capable but non-superuser/non-bypass and has exactly one Ledger table
  privilege (`INSERT`) plus one insert-only RLS policy.
- PASS: `anon`, `authenticated` and any existing `aria_api` role have no Ledger grants; no public
  Usage endpoint or OpenAPI surface was added.
- PASS: trigger-level append-only enforcement blocks owner-level UPDATE/DELETE, while all three
  historical parent links use indexed `ON DELETE RESTRICT` foreign keys.
- PASS: Worker Application contains no persistence/Provider SDK import; Infrastructure emits only
  INSERT, disables implicit RETURNING so SELECT authority is unnecessary, and maps persistence
  failures to the declared boundary error.
- PASS: downgrade removes the policy and table grant before the Ledger table, while retaining the
  durable externally credentialed runtime principal.
- PASS: focused tests, full regression suites, lint, typecheck and builds passed. Final repository
  record/architecture gates are captured in the linked report.

## Verification

See [test-report.md](./test-report.md). Contract, PostgreSQL, API, Worker, Web, lint, typecheck and
build verification passed; the final repository record and architecture gates passed after these
records were finalized.

## Remaining Risks

- Production/Staging must provision and rotate the `aria_worker` credential outside source control
  before a real Provider runtime can append records.
- G02/G03 remain deferred, so no paid AI call exists yet. G06 must define the pricing catalog and
  cost calculation policy before Provider release.
- Usage correction/retention workflows remain separate future contracts; history cannot be rewritten.

**Final status:** PASS
