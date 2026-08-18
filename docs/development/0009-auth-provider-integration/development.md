# Development Record: 0009 Auth Provider Integration

- Increment ID: `0009-auth-provider-integration`
- Date: 2026-08-18
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B01 — Auth Provider Integration`
- Architecture decision: [ADR-006](../../adr/ADR-006-supabase-jwt-verification.md)
- [Test report](./test-report.md)

## Scope

Implement the documented server-side Auth provider boundary: a provider-neutral Application port,
a Supabase asymmetric-JWT infrastructure adapter, strict ES256/JWKS verification, a reusable
FastAPI authentication dependency, and the stable safe 401 error envelope. This increment does
not implement Account Bootstrap, Membership Resolution, Tenant Context, roles, `/me`, login UX,
database writes, a product route, or authorization.

## Source Documents

- Google Drive `Aria AI — Sprint 1 Technical Backlog v1.0`, story `S1-B01`.
- Google Drive `01 — Aria AI — API Contract Specification v1.0`, Bearer JWT, status, error,
  security and contract-test sections.
- Google Drive `03 — Aria AI — Security & Threat Model v1.0`, T-ID-01 and SEC-01.
- Google Drive `06 — Aria AI — Test Strategy & Test Case Master v1.0`, TC-ID-001/002 and API
  security gates.
- Google Drive `11 — Aria AI — Coding Standards & Engineering Conventions v1.0`, layer and Auth
  adapter rules.
- Google Drive `12 — Aria AI — Dependency & Vendor Register v1.0`, Supabase abstraction,
  dependency admission and pinning rules.
- Google Drive `Aria AI — Repository & Code Structure Specification v1.0`, Identity module and
  Infrastructure Auth boundary.
- Current Supabase JWT/JWKS and signing-key documentation reviewed on 2026-08-18.
- Current PyJWT 2.13.0 API, release and security documentation reviewed on 2026-08-18.
- Explicit owner approval on 2026-08-18: `PyJWT[crypto]==2.13.0`, 30-second clock skew, fixed
  ES256 allowlist, unknown-`kid` refresh, contract-first delivery, and B02/B03/B04 exclusion.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md), and
  [document-driven development policy](../../governance/document-driven-development.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-033 | S1-B01: verify JWT server-side | `AccessTokenVerifier` and `SupabaseJwtVerifier` | TC-0901 |
| REQ-034 | T-ID-01: signature/issuer/audience/expiry with bounded skew | Fixed ES256, required claims and exactly 30-second leeway | TC-0902, TC-0903 |
| REQ-035 | Invalid, expired and malformed credentials return safe 401 | FastAPI dependency and centralized `AUTH_REQUIRED` handler | TC-0904, TC-0905 |
| REQ-036 | Provider code remains behind an adapter | Identity Application Protocol plus infrastructure-only PyJWT import guard | TC-0906 |
| REQ-037 | `kid` selects JWKS key and rotation works without restart | 600-second JWKS cache with unknown-`kid` refresh | TC-0907, TC-0908 |
| REQ-038 | Health remains public; later Identity/Tenant stories stay excluded | Auth dependency is reusable but no product route or global product behavior is inferred | TC-0909, TC-0910 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- The product documents did not choose a Python JWT library or numeric clock skew. Development
  paused, the active public JWKS was checked, and the owner explicitly approved PyJWT 2.13.0 and
  30 seconds before implementation.
- The active project JWKS publishes an EC P-256 key with `alg=ES256`; allowed algorithms are still
  fixed in code and are never copied from an unverified token header.
- `AUTH_PROVIDER_URL` already contains the canonical Supabase issuer path `/auth/v1`. The adapter
  uses that configured value exactly after trailing-slash normalization.
- S1-B01 establishes external identity only. Role, membership, account and tenant authority are
  deliberately not read from JWT claims.

## Changes

- Added the provider-neutral `AuthenticatedIdentity`, `InvalidAccessToken`, and asynchronous
  `AccessTokenVerifier` Application contracts.
- Added the Supabase JWKS adapter with fixed ES256, required `kid`, issuer/audience/expiry/UUID
  subject validation, 30-second leeway, bounded JWKS caching, and automatic unknown-key refresh.
- Added a fail-closed verifier when Auth configuration is absent.
- Added the reusable Bearer dependency and centralized safe `AUTH_REQUIRED` 401 response with the
  request ID and `WWW-Authenticate: Bearer`.
- Wired hosted configuration into the adapter without adding any product endpoint.
- Pinned `PyJWT[crypto]==2.13.0`, updated the uv lock graph, and added static CI ownership and
  version checks.
- Added [ADR-006](../../adr/ADR-006-supabase-jwt-verification.md) and updated API boundary docs.

## Structure Preservation

- Application exposes only a Protocol, a UUID identity value and a neutral invalid-token error; it
  imports no FastAPI, Supabase, PyJWT, HTTP or infrastructure code.
- PyJWT is imported only by `apps/api/app/infrastructure/auth/supabase_jwt.py`; a CI architecture
  test prevents it from spreading into Application or Domain.
- FastAPI credential parsing and HTTP error mapping remain in the API layer.
- The active modular monolith gains no deployable, database table, migration, queue, provider SDK
  in Domain, cross-module write, mutation endpoint or tenant behavior.
- Account Bootstrap (`S1-B02`), Membership (`S1-B03`), Tenant Context (`S1-B04`) and `/me` remain
  untouched.

## Senior Review

- **Resolved — incorrect issuer composition (High):** the first factory appended `/auth/v1` to
  `AUTH_PROVIDER_URL`, although Runtime configuration already contained that path. This would have
  rejected every valid hosted token. The configured issuer is now used exactly and a wiring
  regression assertion protects it.
- **Resolved — exception handler type mismatch:** the initial handler signature was narrower than
  Starlette's registered exception callback contract. It now accepts `Exception`, validates the
  registered type, and passes strict MyPy.
- **Verified — algorithm confusion resistance:** only the code-owned ES256 allowlist is passed to
  decode; wrong token algorithms and JWK/token algorithm mismatch are rejected.
- **Verified — key rotation:** the integration contract serves two JWKS generations and proves an
  unknown `kid` triggers exactly one refresh and verifies without process restart.
- **Verified — claim authority:** only UUID `sub` crosses the adapter; role and provider metadata do
  not become authorization inputs.
- **Verified — secret handling:** raw bearer values are absent from responses and structured logs.
- **Verified — scope:** no `/me`, account, membership, tenant, database or product route was added.

## Verification

- Contract-first Red phase was executed before implementation and failed on the expected missing
  Adapter/dependency modules.
- Auth/API focused suite passed after implementation and senior-review corrections.
- Static CI contracts verify the exact dependency pin, Infrastructure-only JWT import and public
  Health exceptions.
- Full repository quality, dependency, secret and architecture results are recorded in the linked
  [test report](./test-report.md).

## Remaining Risks

- S1-A03 hosted runtime evidence remains independent from this increment; its original Render
  proposal was later superseded by ADR-007. This increment does not claim Hosted Auth smoke evidence
  or close S1-A03.
- JWKS availability is required on a cold cache. Cached asymmetric keys keep normal verification
  local, while operational monitoring of Auth/JWKS availability belongs to the staging/runtime
  observability work.
- Account state, session revocation semantics, membership, tenant authorization and login UX are
  intentionally deferred to their documented stories.
