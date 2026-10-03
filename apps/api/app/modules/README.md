# Domain modules

Sprint 1 modules are added story-by-story under this directory. Each module follows `api/application/domain/infrastructure/tests` only to the depth justified by its documented behavior.

`identity/application` contains the S1-B01 provider-neutral token-verification contract, the S1-B02
Account Bootstrap use case/ports, and the S1-B03 active Membership resolver. Identity Infrastructure
implements the transactional PostgreSQL projection and read-only Membership lookup; API wiring
remains an Application dependency. ADR-009 exposes it only through the authenticated, pre-tenant
`POST /api/v1/auth/bootstrap` command with an empty 204 response.

The S1-B04 API dependency resolves request-scoped Tenant Context from `X-Account-ID` directly after
JWT verification; it does not invoke Account Bootstrap. Product routes consume it only when their
own Story and contract are approved. ADR-011 reserves canonical `GET /api/v1/accounts` as a
separate authenticated, read-only pre-tenant query before S1-C02; it is not part of Bootstrap.

`projects/domain` owns the S1-C01 Project vocabulary and invariants. `projects/application` owns
tenant-authorized create/update/archive/soft-delete orchestration through ports, and
`projects/infrastructure` supplies the SQLAlchemy repository. Ordinary repository reads are both
tenant-scoped and soft-delete filtered; the explicit including-deleted method is internal recovery
surface only. S1-C01 exposes no HTTP route.

`context/domain` owns the S1-D01 Source/Version vocabulary and immutable-ready invariants.
`context/application` admits only text Sources in this increment and records safe lifecycle events;
`context/infrastructure` implements tenant/project-scoped persistence and derives the current ready
Version. No Context HTTP route, parser, queue or file ingestion is exposed by S1-D01.

`requirements/domain` owns the Requirement vocabulary, creator and Source Reference invariants.
The I01 Application boundary validates the selected integer Context Version and semantic
provenance before persistence. The shared S1-I02 Application workflow snapshots eligible Context
Items, invokes only the provider-neutral AI port, validates and optionally repairs candidates,
merges only exact duplicate groups, preserves existing Requirement decisions, and atomically
persists the batch plus safe conflict Outbox signals. Infrastructure implements tenant-safe
PostgreSQL persistence. Replay resolves only a same-tenant terminal Job and then reads its
`generation_job_id` Requirement rows; no result-mapping table or historical payload snapshot is
introduced. I02 exposes no HTTP route, concrete provider, Gap model or conflict table.

`scope/domain` owns the K01 Working Scope Draft and strict `scope_content_schema_v1` validation.
`scope/application` exposes only the Domain/Repository boundary; `scope/infrastructure` persists
one tenant-scoped Draft per Project/Context Version with `updated_at` CAS. Historical Drafts are
protected after Context advances. `scope/domain/readiness.py` owns the K02 pure readiness policy;
it consumes tenant-scoped authoritative Gap metadata and computes `ready_for_share` without
persistence, HTTP, UI or content scoring. The provider-neutral K03 Application boundary resolves
an exact ready snapshot, accepts only draft/confirmed Requirements, maps AI-05 into the twelve K01
sections, meters every AI/repair call, and conflicts instead of overwriting an existing Draft.
Public API/UI, concrete Providers, Worker wiring, regeneration and immutable Scope Snapshots remain
deferred to later increments.
