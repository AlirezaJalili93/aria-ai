# Aria API

Python 3.12+/FastAPI modular-monolith boundary.

Dependency direction is `API/Presentation -> Application -> Domain`; infrastructure adapters implement ports and remain outside Domain. The bootstrap intentionally exposes no product endpoint. Health, Auth, Tenant Context, persistence and async jobs are separate documented stories.
