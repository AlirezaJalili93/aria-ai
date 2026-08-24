# Domain modules

Sprint 1 modules are added story-by-story under this directory. Each module follows `api/application/domain/infrastructure/tests` only to the depth justified by its documented behavior.

`identity/application` contains the S1-B01 provider-neutral token-verification contract, the S1-B02
Account Bootstrap use case/ports, and the S1-B03 active Membership resolver. Identity Infrastructure
implements the transactional PostgreSQL projection and read-only Membership lookup; API wiring
remains a dependency without a public bootstrap route.

Current Account transport and Tenant Context remain reserved for S1-B04.
