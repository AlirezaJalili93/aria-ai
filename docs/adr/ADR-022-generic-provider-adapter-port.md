# ADR-022 — Generic Provider Adapter Port

- Status: Accepted for Sprint 1 contract boundary; concrete adapters deferred
- Date: 2026-09-05
- Scope: Provider-neutral adapter boundary following S1-G01
- Source: [Aria AI — AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk)
- Supersedes: no prior concrete-provider decision exists

## Decision

The Worker Application defines one generic `ProviderAdapter` port:

```text
execute(request) -> ProviderResult
```

`request` remains an opaque provider-neutral structured mapping until a Provider Selection Decision
defines the provider-independent request schema. The normalized `ProviderResult` contains only:

```text
data
provider
model
provider_request_id
input_tokens
cached_input_tokens
output_tokens
latency_ms
status
```

The adapter maps provider failures to the existing bounded AI error classes and carries explicit
retryability. Raw SDK exceptions, response bodies and credentials never cross this boundary.

## Explicit non-decisions

- No Provider A or Provider B is selected.
- No provider name, model name, SDK, API-key environment variable, endpoint, timeout value or retry
  count is introduced.
- No concrete adapter, routing implementation, fallback behavior or Usage Ledger write is added.
- `S1-G02 — Provider Adapter A` and `S1-G03 — Provider Adapter B` are **Deferred/Blocked** until a
  Provider Selection Decision and Evaluation Gate are approved.

## Consequences

- G01 can be consumed by a future Gateway without coupling Application code to a Provider.
- Concrete adapters must implement request translation, timeout, usage extraction, request-ID
  extraction and standardized error mapping in Infrastructure.
- AI vertical-slice production readiness remains blocked until at least one concrete Provider is
  selected, evaluated and metered.

**Unapproved assumptions:** None
