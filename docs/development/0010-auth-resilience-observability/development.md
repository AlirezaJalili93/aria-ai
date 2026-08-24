# Development Record: 0010 Auth Resilience and Observability

- Increment ID: `0010-auth-resilience-observability`
- Date: 2026-08-18
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B01 — Auth Provider Integration`
- Architecture decisions: [ADR-006](../../adr/ADR-006-supabase-jwt-verification.md)
- [Test report](./test-report.md)

## Scope

Harden the existing S1-B01 authentication boundary so invalid credentials remain a safe 401 while
Supabase/JWKS infrastructure failures return the approved retryable 503. Add the approved five-second
JWKS timeout, safe Auth events, pure ASGI request observability, downstream trace enrichment, exception
metadata, and logging schema version 1. Account bootstrap, membership, tenant resolution, `/me`, AI
provider execution, database writes, and product endpoints remain out of scope.

## Source Documents

- Owner-provided mandatory Auth/observability correction document on 2026-08-18.
- Owner approval on 2026-08-18 for a five-second JWKS timeout and the exact 503 error contract.
- Google Drive `01 — Aria AI — API Contract Specification v1.0`.
- Google Drive `07 — Aria AI — Environment & Configuration Specification v1.0`.
- Google Drive `Aria AI — Repository & Code Structure Specification v1.0`.
- Current Supabase JWT/JWKS documentation and Auth changelog reviewed on 2026-08-18.
- PyJWT 2.13.0 `PyJWKClient` and exception contracts.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md), and
  [document-driven development policy](../../governance/document-driven-development.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-039 | Invalid tokens and Auth infrastructure failures are distinct | Neutral exceptions plus centralized 401/503 mapping | TC-1001, TC-1002 |
| REQ-040 | JWKS access has an explicit five-second timeout | Fixed `PyJWKClient(timeout=5)` adapter boundary | TC-1003 |
| REQ-041 | Auth emits safe success/rejection/unavailable/refresh events | Dependency and adapter events through allowlisted logger | TC-1004, TC-1005 |
| REQ-042 | HTTP observability uses pure ASGI context propagation | Direct ASGI `scope/receive/send` middleware | TC-1006, TC-1007 |
| REQ-043 | Trace context supports explicit downstream enrichment | Validating `enrich_trace_context` contract | TC-1008 |
| REQ-044 | Unhandled failures log safe exception metadata | Type/component/operation-only failure fields | TC-1009 |
| REQ-045 | Every structured event carries `schema_version="1"` | Immutable base log field | TC-1010 |
| REQ-046 | Future AI telemetry fields are safe and content-free | Positive allowlist for approved metadata only | TC-1011 |

## Assumptions and Clarifications

The source correction required a short timeout but did not choose a number. Work paused and the owner
approved exactly five seconds. The owner also approved HTTP 503, stable code
`AUTH_PROVIDER_UNAVAILABLE`, `retryable=true`, and the safe English message used by this increment.

**Unapproved assumptions:** None

## Changes

- Added `AuthProviderUnavailable` beside `InvalidAccessToken` in the provider-neutral Identity
  Application contract; both carry bounded safe reason codes and no provider payload.
- Added explicit five-second JWKS timeout and deterministic error classification to the Supabase
  adapter. Successful unknown-key refresh emits `auth.jwks_refreshed` and still rejects an absent key.
- Added safe Auth success, rejection and provider-unavailable events plus the approved retryable 503
  envelope. No event receives a JWT, Authorization header, claim, subject, email, or provider URL.
- Replaced Starlette `BaseHTTPMiddleware` with pure ASGI middleware, preserving trace enrichment and
  response headers while adding safe unhandled-exception metadata.
- Added version 1 to every structured event, explicit validated trace enrichment, and approved
  content-free AI telemetry fields for later adapters. No AI adapter or provider behavior was added.
- Updated ADR-006, API/shared-package READMEs, static architecture contracts, integration tests and
  this development evidence set.

## Architecture and Design Decisions

- ADR-006 was amended rather than creating a competing decision: this hardening completes the same
  S1-B01 provider boundary and introduces no vendor, data model, or deployable.
- Infrastructure/JWKS failures are identified only while resolving public keys. Once a key was
  resolved, every signature/claim/subject failure remains credential rejection and maps to 401.
- Auth HTTP mapping and event timing stay in Presentation; provider-specific JWKS parsing stays in
  Infrastructure; Application exposes only neutral identity and failure contracts.
- The logger continues to discard unknown fields rather than sanitize arbitrary caller objects.
  Future AI metadata is schema-ready, but prompts and responses are not legal fields.
- Trace enrichment is explicit and context-local. Its contract states that account/project IDs may
  be attached only after authorization; S1-B01 does not attach either tenant identifier.

## Structure Preservation

- Domain remains untouched and imports no framework, provider, logger, or infrastructure code.
- PyJWT remains imported only by the Supabase Infrastructure adapter; static CI enforces this.
- No account, membership, role, Tenant Context, `/me`, database, queue, mutation, or product route was
  inferred from the correction document.
- Health readiness remains independent from Supabase/AI availability, so a transient Auth provider
  outage does not remove the API process from the load balancer.
- The shared observability package remains framework-neutral and non-deployable.

## Senior Review

- **Resolved — subject reason misclassification (Medium):** PyJWT validates a non-string `sub`
  before adapter UUID parsing. `InvalidSubjectError` is now mapped explicitly to `invalid_subject`,
  and both non-string and non-UUID subjects are covered.
- **Resolved — stale virtual-environment coupling (Tooling):** focused verification initially loaded
  an old installed copy of the shared package. Final tests use a clean uv 0.12.5 environment and a
  workspace-local cache/tool directory.
- **Verified — 401/503 boundary:** malformed, expired, wrong signature/issuer/audience/algorithm,
  missing/unknown `kid` after successful refresh, and invalid subject all raise `InvalidAccessToken`;
  network and malformed JWKS raise `AuthProviderUnavailable`.
- **Verified — safe observability:** token, subject, exception message, raw path/query/header, prompt
  and provider response fixtures are absent from captured logs.
- **Verified — context behavior:** pure ASGI execution exposes downstream job enrichment to the outer
  completion event and resets the ContextVar at request exit.
- **Verified — structure:** no deployable, persistence contract, tenant behavior, product route, or
  provider SDK dependency outside Infrastructure was introduced.

## Verification

Contract-first Red failed the three new static requirements as expected. The final focused suite,
repository tests, lint, strict type checks, production builds, secret scan and bounded Python/npm
dependency audits pass. Exact commands and counts are recorded in the linked test report.

## Remaining Risks

- Hosted Supabase outage evidence is not claimed; deterministic loopback JWKS and PyJWT exception
  contracts cover this increment, while hosted smoke evidence remains part of the staging record.
- FastAPI 0.141.1 emits the existing TestClient/httpx deprecation warning. It is unrelated to this
  change and requires a separately documented dependency migration.
- Account/project trace enrichment remains a contract only until the approved Membership/Tenant
  stories implement authorization and call it.
