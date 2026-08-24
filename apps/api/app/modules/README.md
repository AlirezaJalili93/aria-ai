# Domain modules

Sprint 1 modules are added story-by-story under this directory. Each module follows `api/application/domain/infrastructure/tests` only to the depth justified by its documented behavior.

`identity/application` contains the S1-B01 provider-neutral token-verification contract and the
S1-B02 Account Bootstrap use case/ports. Identity Infrastructure implements the transactional
PostgreSQL projection; API wiring remains a dependency without a public bootstrap route.

Multi-account Membership resolution, current Account selection and Tenant Context remain reserved
for S1-B03/S1-B04.
