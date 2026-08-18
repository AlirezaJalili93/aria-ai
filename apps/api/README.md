# Aria API

Python 3.12+/FastAPI modular-monolith boundary.

Dependency direction is `API/Presentation -> Application -> Domain`; infrastructure adapters implement ports and remain outside Domain.

The bootstrap exposes only two unauthenticated operational endpoints:

- `GET /health/live` proves that the process is alive without probing a dependency.
- `GET /health/ready` checks validated configuration, PostgreSQL connectivity, and the Redis-compatible queue binding. It does not probe an AI provider.

Auth, Tenant Context, product persistence and async jobs remain separate documented stories.
