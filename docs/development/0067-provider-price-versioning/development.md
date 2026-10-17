# Development Record: 0067 Provider Price Versioning

- Increment ID: `0067-provider-price-versioning`
- Date: 2026-09-20
- Owner: AI/Platform Engineering
- Related plan/issue: `S1-G06 — Provider Price Versioning`
- [Test report](./test-report.md)

## Scope

Implement the approved provider-neutral, immutable Price Catalog; deterministic effective-time
resolution; Decimal token-cost calculation; exact Price identity linkage from the Usage Ledger;
least-privilege Worker reads; and migration/application/integration evidence. Real Provider/model
selection, real prices, a public management API and G02/G03 adapter behavior are excluded.

## Source Documents

- Owner-approved and frozen `0067 — S1-G06 Provider Price Versioning` contract, 2026-09-20.
- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), S1-G05/G06; synced 2026-09-20.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit), `usage_records`; synced 2026-09-20.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), Provider Adapter, metering and change-management rules; synced 2026-09-20.
- [ADR-024](../../adr/ADR-024-usage-ledger-and-worker-role.md) and
  [data model mirror](../../architecture/data-model.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-6701 | Frozen G06 catalog contract | Migration `0023_provider_price_versions`; ADR-054 | TC-6701, TC-6705 |
| REQ-6702 | Frozen uniqueness refinements | Unique Provider/Model/Version and Provider/Model/effective-time constraints | TC-6701, TC-6702 |
| REQ-6703 | Deterministic resolution | `ProviderPriceCatalog`; PostgreSQL ordered resolver | TC-6702 |
| REQ-6704 | Token accounting formula | `TokenUsage`, Decimal calculator, `ROUND_HALF_UP` | TC-6703, TC-6704 |
| REQ-6705 | Exact historical price identity | Composite Usage FK with RESTRICT; priced Usage factory | TC-6706, TC-6707 |
| REQ-6706 | No price before paid invocation | Explicit not-found preflight error; no fallback/default Price | TC-6703 |
| REQ-6707 | Platform ownership/least privilege | RLS, read-only `aria_worker`, public/API role revocation, immutable trigger | TC-6705 |
| REQ-6708 | No real Provider or price | Empty Catalog migration and synthetic-only fixtures | TC-6701, TC-6705 |
| REQ-6709 | Documentation and quality gates | ADR, mirrors, development/test records and repository validation | TC-6708 |

## Assumptions and Clarifications

The owner approved per-one-million rates, exact composite identity, deterministic effective-time
selection, cached-input subset semantics, Decimal calculation with one final eight-place
`ROUND_HALF_UP`, Platform ownership, read-only Worker authority, an empty initial Catalog and no
public API. The migration uses `NOT VALID` only for the two constraints added to existing Usage
history: new rows are enforced immediately, while historical synthetic rows are neither rewritten
nor assigned fabricated prices.

**Unapproved assumptions:** None

## Changes

- Added Alembic revision `0023_provider_price_versions` with immutable global Catalog schema,
  uniqueness, RLS, grants, Worker read policy and Usage Ledger linkage.
- Added provider-neutral Application types, resolver port, token invariant, Decimal calculator and
  authoritative priced-Usage factory in `aria_backend_application.provider_pricing`.
- Added Worker SQLAlchemy read adapter with exact effective-at query and declared unavailable/not
  found errors.
- Tightened `UsageRecord` Application validation so cached tokens cannot exceed total input.
- Added contract, unit, real-PostgreSQL, permission, upgrade-preservation and regression tests.
- Added ADR-054 and synchronized data, migration, Worker and ADR indexes.

## Architecture and Design Decisions

- Pricing stays inside the existing Worker/Application and PostgreSQL boundaries; no service,
  endpoint or Provider SDK was added.
- The Catalog is global Platform configuration rather than tenant data. RLS plus grants prevents
  public/API access while allowing only `SELECT` to the non-bypass Worker role.
- Resolution is a required preflight capability. A future G02/G03 orchestration must retain the
  resolved immutable Price through the call and use the priced-Usage factory afterward.
- Provider output is not authoritative for cost, currency or Price Version in the new G06 path.
- Existing synthetic workflow fixtures do not establish paid-Provider readiness; G02/G03 remain
  explicitly deferred.

## Structure Preservation

- The modular monolith and Web/API/Worker deployables are unchanged.
- Application code imports no SQLAlchemy, Supabase or Provider SDK; SQL stays in Worker
  Infrastructure and Alembic.
- The append-only `UsageLedger.append()` boundary and public OpenAPI remain unchanged.
- The existing Migration chain is extended by one reversible revision without editing released
  migrations or seeding environment-specific data.

## Senior Review

- PASS: Catalog identity and effective-time uniqueness eliminate hidden tie-breaking.
- PASS: full-precision Decimal arithmetic uses normal input (`input-cached`), cached input and output
  independently, with one final `ROUND_HALF_UP` operation.
- PASS: Application and DB both reject invalid cached-token accounting.
- PASS: Runtime permissions are fail-closed; no runtime role can mutate Price history and Data API
  roles receive no access.
- PASS: new Usage rows require the exact Catalog tuple and parent Price deletion is restricted.
- PASS: `NOT VALID` preserves historical rows without weakening enforcement for new writes; the
  follow-up validation condition is documented rather than silently inventing prices.
- PASS: no real Provider/model/price, public endpoint, tenant identifier or content-bearing log was
  introduced.
- PASS: focused and full tests, lint, typecheck, build, secret scan and dependency audits passed.

## Verification

See [test-report.md](./test-report.md). Contract-first red tests failed on missing artifacts, then
all focused tests and the complete repository regression suite passed against local PostgreSQL 16.

## Remaining Risks

- G02/G03 must wire the preflight Price resolution into actual Provider selection before any paid
  invocation is allowed.
- The historical `NOT VALID` constraints may be validated only after every retained Usage row has
  an authoritative Catalog match; fake backfill prices are prohibited.
- The Catalog is intentionally empty, so real Provider execution remains disabled.

**Final status:** PASS
