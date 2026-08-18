# Aria API

Python 3.12+/FastAPI modular-monolith boundary.

Dependency direction is `API/Presentation -> Application -> Domain`; infrastructure adapters implement ports and remain outside Domain.

The bootstrap exposes only two unauthenticated operational endpoints:

- `GET /health/live` proves that the process is alive without probing a dependency.
- `GET /health/ready` checks validated configuration, PostgreSQL connectivity, and the Redis-compatible queue binding. It does not probe an AI provider.

Every request receives safe UUID `X-Request-ID` and `X-Correlation-ID` response headers. Safe client values are preserved; malformed values are replaced. Request completion/failure events use the shared JSON logger and never include headers, query values or raw content.

Auth, Tenant Context, product persistence and async jobs remain separate documented stories.
