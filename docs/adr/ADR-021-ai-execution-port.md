# ADR-021 — Provider-Neutral AI Execution Port

- Status: Accepted for Sprint 1 G01
- Date: 2026-09-05
- Scope: Worker Application boundary for structured AI execution
- Source: [Aria AI — AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit?usp=drivesdk)
- Supporting sources: [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk), [Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit?usp=drivesdk)

## Decision

The Worker Application exposes an asynchronous, provider-neutral `AIExecutionPort` with the
canonical operation:

```text
execute_structured(
  task_type,
  workflow_version,
  prompt_version,
  output_schema,
  input_context,
  routing_policy,
  cost_budget,
  timeout_policy,
  metadata,
)
```

The standardized response contains exactly the approved execution fields:

```text
data
provider
model
provider_request_id
input_tokens
cached_input_tokens
output_tokens
latency_ms
retry_no
workflow_version
prompt_version
estimated_cost
status
```

`status` follows the Data Dictionary usage vocabulary: `success`, `failed`, or `partial`.
`provider_request_id` is nullable as defined by the Usage Record contract. The response data remains
untrusted candidate output; validation and persistence are downstream stages.

The Application boundary also exposes standardized provider failure classes:

```text
timeout | rate_limited | auth_error | invalid_response |
safety_block | provider_unavailable | quota_error | unknown_provider_error
```

Retryability is explicit on the mapped error. The port does not infer retryability, perform
backoff/jitter, select a provider, or persist Usage Records.

## Boundary rules

- Provider SDKs and provider-specific exceptions stay in Infrastructure adapters.
- `input_context` contains only task-required data and source references; secrets, credentials and
  unrelated project data are forbidden.
- `output_schema`, `routing_policy`, `cost_budget`, `timeout_policy` and `metadata` remain structured
  provider-neutral mappings; their detailed policies belong to later stories where specified.
- The port does not implement provider adapters, routing selection, fallback, retry execution,
  schema/business validation, Usage persistence or model evaluation.
- The limited G04 routing-policy contract is recorded in [ADR-023](ADR-023-limited-routing-policy-contract.md);
  task mapping, escalation, fallback and provider selection remain deferred.

## Consequences

- Application workflows can depend on one stable port while provider adapters change independently.
- Standardized response and error metadata is available for later metering and observability.
- The generic adapter boundary is recorded in [ADR-022](ADR-022-generic-provider-adapter-port.md);
  G02/G03 must later implement adapter translation, timeout, usage extraction, request ID extraction
  and error mapping without leaking provider types.
- G04 must define routing policy behavior; G05/G06 must persist usage and price semantics.

**Unapproved assumptions:** None
