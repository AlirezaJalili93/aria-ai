# Domain modules

Sprint 1 modules are added story-by-story under this directory. Each module follows `api/application/domain/infrastructure/tests` only to the depth justified by its documented behavior.

`identity/application` contains the S1-B01 provider-neutral token-verification contract, the S1-B02
Account Bootstrap use case/ports, and the S1-B03 active Membership resolver. Identity Infrastructure
implements the transactional PostgreSQL projection and read-only Membership lookup; API wiring
remains an Application dependency. ADR-009 exposes it only through the authenticated, pre-tenant
`POST /api/v1/auth/bootstrap` command with an empty 204 response.

The S1-B04 API dependency now resolves request-scoped Tenant Context from `X-Account-ID`; product
routes consume it only when their own Story and contract are approved.
