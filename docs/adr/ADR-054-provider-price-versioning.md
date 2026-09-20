# ADR-054 — Immutable Provider Price Versioning

- Status: Accepted
- Date: 2026-09-20
- Decision owner: Product and Engineering
- Extends: ADR-024

## Context

S1-G05 made `usage_records` the authoritative append-only AI Usage Ledger but intentionally
deferred its price catalog, deterministic price selection and cost calculation to S1-G06. The
approved S1-G06 contract requires reproducible historical cost without choosing a real Provider or
placing Provider-specific SDK behavior in Domain/Application code.

## Decision

- `provider_price_versions` is a global Platform catalog, not a tenant-owned table.
- Catalog identity is `UNIQUE(provider, model, pricing_version)`. A changed price always creates a
  new version.
- Resolution uses the latest row where `effective_from <= provider_execution_at`. The additional
  `UNIQUE(provider, model, effective_from)` constraint prevents ambiguous ties.
- Rates are non-negative `NUMERIC(20,8)` values per one million normal-input, cached-input and
  output tokens. Currency is an explicit three-character code.
- Catalog rows are append-only. Runtime roles cannot insert, update or delete them. `aria_worker`
  has read-only access; `anon`, `authenticated` and `aria_api` have none.
- The normalized Provider result defines cached input as a subset of total input. Both Application
  and PostgreSQL enforce `cached_input_tokens <= input_tokens`.
- Cost calculation uses `Decimal` without intermediate rounding. The final total is rounded once
  to eight decimal places with `ROUND_HALF_UP`.
- `usage_records(provider, model, pricing_version)` references the exact Catalog identity with
  `ON DELETE RESTRICT`. The new FK and cached-token check are introduced as `NOT VALID`: they
  enforce all new writes without rewriting or fabricating prices for historical test records.
- Provider price resolution is a preflight operation. No matching price stops a future paid call;
  zero-cost fallback, arbitrary latest price and post-call resolution are forbidden.
- The Application pricing factory accepts an already resolved Price Version and builds the final
  immutable `UsageRecord`; Provider output cannot supply `estimated_cost`, `currency` or
  `pricing_version` through that path.
- No public management API, real Provider/model name or real price is introduced. Controlled
  Platform migration/administration owns future Catalog inserts.

## Consequences

G02/G03 must select a Provider/model, resolve its Price Version before invocation, retain that
resolution through execution, and use it to append Usage afterward. Existing deterministic fake
workflows are not evidence of paid-provider readiness. A later controlled data migration may
validate the two `NOT VALID` constraints only after every historical row has an authoritative
Catalog match; inventing a backfill price remains forbidden.
