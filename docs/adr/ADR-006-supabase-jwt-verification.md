# ADR-006: Supabase JWT Verification Boundary

- **Status:** Accepted
- **Date:** 2026-08-18
- **Story:** S1-B01 — Auth Provider Integration

## Context

Sprint 1 requires server-side verification of Supabase access tokens while keeping provider SDKs
and provider-specific claims outside Application and Domain. The active Supabase project publishes
an asymmetric ES256 key through its public JWKS endpoint. The Security & Threat Model requires
signature, issuer, audience, expiry and subject validation, a bounded clock skew, deny-by-default
behavior, and negative tests. The product documents did not select a Python JWT library or a clock
skew value, so implementation paused until the owner explicitly approved both decisions.

## Decision

1. Define an asynchronous provider-neutral `AccessTokenVerifier` contract in the Identity
   Application layer. Its successful result contains only the canonical UUID subject.
2. Implement Supabase verification in `infrastructure/auth`; PyJWT must not be imported by
   Application or Domain.
3. Pin `PyJWT[crypto]==2.13.0` and its lock graph. This version is required because its security
   hardening binds the token algorithm to the selected JWK algorithm.
4. Accept only the code-owned `ES256` allowlist. Never derive allowed algorithms from the token
   header.
5. Require and validate `kid`, signature, `iss`, `aud`, `exp`, and UUID `sub`; apply exactly 30
   seconds of leeway.
6. Cache the JWKS for at most the Supabase Edge cache window of 600 seconds. Unknown `kid` lookup
   must force a refresh through `PyJWKClient`, allowing signing-key rotation without a restart.
7. Map missing and invalid bearer credentials to the same safe `AUTH_REQUIRED` 401 response.
   Keep `/health/live` and `/health/ready` public.
8. Do not add Account Bootstrap, Membership Resolution, Tenant Context, `/me`, or another product
   route in this story.

## Consequences

- Token verification stays local after JWKS retrieval and does not put the Auth user endpoint in
  the normal request path.
- Supabase can be replaced behind the Application port without changing Identity consumers.
- Key rotation is accepted as soon as the refreshed public JWKS contains the new `kid`.
- The API fails closed when Auth configuration is absent.
- PyJWT and `cryptography` become security-critical locked dependencies and remain subject to the
  dependency scan and upgrade policy.
- Account, membership, role and tenant authority remain unresolved until their separately approved
  Sprint 1 stories.

## Source documents

- Sprint 1 Technical Backlog v1.0 — S1-B01
- API Contract Specification v1.0 — Bearer JWT, 401 policy and error envelope
- Security & Threat Model v1.0 — T-ID-01 and SEC-01
- Repository & Code Structure Specification v1.0 — Auth adapter and dependency direction
- Dependency & Vendor Register v1.0 — Supabase abstraction and dependency admission
- Test Strategy & Test Case Master v1.0 — TC-ID-001 and TC-ID-002
- Supabase current JWT and signing-key documentation reviewed on 2026-08-18
- Owner approval in the development task on 2026-08-18
