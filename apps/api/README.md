# Aria API

Python 3.12+/FastAPI modular-monolith boundary.

Dependency direction is `API/Presentation -> Application -> Domain`; infrastructure adapters implement ports and remain outside Domain.

The bootstrap exposes only two unauthenticated operational endpoints:

- `GET /health/live` proves that the process is alive without probing a dependency.
- `GET /health/ready` checks validated configuration, PostgreSQL connectivity, and the Redis-compatible queue binding. It does not probe an AI provider.

Every request receives safe UUID `X-Request-ID` and `X-Correlation-ID` response headers. Safe client values are preserved; malformed values are replaced. Request completion/failure events use the shared JSON logger and never include headers, query values or raw content.
The request logger is pure ASGI so downstream job/account/project enrichment remains visible to the
completion event. Tenant identifiers may be enriched only after successful authorization.

S1-B01 adds a provider-neutral access-token verification contract. Hosted API instances bind it
to the Supabase JWKS adapter, which accepts only ES256, verifies issuer/audience/expiry/subject,
uses the approved 30-second clock skew, and refreshes cached JWKS when a new `kid` appears.
Missing, malformed, expired, or otherwise invalid bearer tokens map to the stable `AUTH_REQUIRED`
401 envelope. JWKS network, DNS, timeout, or malformed-provider failures use an explicit five-second
timeout and map to the retryable `AUTH_PROVIDER_UNAVAILABLE` 503 envelope. Auth telemetry records
only approved reason/provider/timing and trace fields; it never records bearer tokens, headers,
claims, raw subjects, emails, or provider URLs. Health routes remain public.

Account bootstrap, membership resolution, Tenant Context, product persistence and async jobs
remain separate documented stories.
