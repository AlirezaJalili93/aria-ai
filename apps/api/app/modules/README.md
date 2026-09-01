# Domain modules

Sprint 1 modules are added story-by-story under this directory. Each module follows `api/application/domain/infrastructure/tests` only to the depth justified by its documented behavior.

`identity/application` contains the S1-B01 provider-neutral token-verification contract, the S1-B02
Account Bootstrap use case/ports, and the S1-B03 active Membership resolver. Identity Infrastructure
implements the transactional PostgreSQL projection and read-only Membership lookup; API wiring
remains an Application dependency. ADR-009 exposes it only through the authenticated, pre-tenant
`POST /api/v1/auth/bootstrap` command with an empty 204 response.

The S1-B04 API dependency resolves request-scoped Tenant Context from `X-Account-ID` directly after
JWT verification; it does not invoke Account Bootstrap. Product routes consume it only when their
own Story and contract are approved. ADR-011 reserves Account discovery as a separate authenticated,
read-only pre-tenant query before S1-C02; it is not part of Bootstrap.

`projects/domain` owns the S1-C01 Project vocabulary and invariants. `projects/application` owns
tenant-authorized create/update/archive/soft-delete orchestration through ports, and
`projects/infrastructure` supplies the SQLAlchemy repository. Ordinary repository reads are both
tenant-scoped and soft-delete filtered; the explicit including-deleted method is internal recovery
surface only. S1-C01 exposes no HTTP route.
