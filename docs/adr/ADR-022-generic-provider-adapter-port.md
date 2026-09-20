# ADR-022 — Generic Provider Adapter Port

- Status: Accepted; concrete evaluation adapters added by ADR-055
- Date: 2026-09-05
- Scope: Provider-neutral adapter boundary following S1-G01
- Source: [Aria AI — AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk)
- Supersedes: no prior concrete-provider decision exists

## Decision

The Worker Application defines one generic `ProviderAdapter` port:

```text
execute(request) -> ProviderResult
```

ADR-055 now constrains `request` to the exact provider-neutral keys `instructions`, `input` and
`output_schema`. The normalized `ProviderResult` contains only:

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

## Original non-decisions and later refinement

- This ADR did not select a provider or adapter. ADR-055 later selected two evaluation-only
  candidates and their SDK/timeout/accounting contracts.
- Runtime routing, primary/fallback promotion and customer-data use remain undecided.
- The generic port and normalized result are unchanged.

## Consequences

- G01 can be consumed by a future Gateway without coupling Application code to a Provider.
- Concrete adapters must implement request translation, timeout, usage extraction, request-ID
  extraction and standardized error mapping in Infrastructure.
- AI vertical-slice production readiness remains blocked until at least one concrete Provider is
  selected, evaluated and metered.

**Unapproved assumptions:** None
