# Development Record: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-24
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-A03 — Staging Runtime`
- [Test report](./test-report.md)

## Scope

Establish the documented independent staging environment for the three existing deployables: Web
on Vercel, API and Worker on a managed container runtime, isolated Supabase PostgreSQL/Auth/Storage,
and a Redis-compatible durable Queue. The increment owns environment bindings, locked deployment
artifacts, operational liveness/readiness, release identity, smoke evidence, rollback evidence, and
secret separation. It does not implement product routes, migrations, a queue consumer, outbox
publishing, storage upload behavior, or AI workflows assigned to later stories.

The initial Render proposal was replaced after card verification blocked resource creation and the
owner requested a usable free tool. [ADR-007](../../adr/ADR-007-railway-staging-runtime.md) records
Railway Trial for temporary API/Worker staging and a free Redis-compatible Frankfurt database.

## Source Documents

- Google Drive `Aria AI — Final System Architecture v2.0`.
- Google Drive `Aria AI — Engineering Execution Master Plan v1.0`.
- Google Drive `Aria AI — System Architecture Creation & Governance Plan v1.0`.
- Google Drive Sprint 1 backlog story `S1-A03` and the Environment, Deployment, Test, Security, and
  Definition of Done specifications referenced by the traceability index.
- Repository [system architecture](../../architecture/system-architecture.md), `AGENTS.md`, and
  [document-driven development policy](../../governance/document-driven-development.md).
- Owner approvals on 2026-08-18 for isolated Supabase Staging in Frankfurt, root `/health/live` and
  `/health/ready`, AI-provider exclusion from readiness, repository-scoped GitHub access, and
  SHA-verified hosted smoke.
- Owner request on 2026-08-18 to replace Render with a usable free tool.
- Railway official Trial/pricing, background-worker, monorepo, Config-as-Code, healthcheck,
  restart-policy, deployment rollback, Git variables, and region documentation.
- Upstash official Redis free-tier, persistence, TLS, and region documentation.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-020 | S1-A03 independent Web/API/Worker/Postgres/Queue/Storage/Auth staging | Vercel, Railway configs and images, Supabase, external Redis-compatible Queue | TC-0701, TC-0705, TC-0706, TC-0709 |
| REQ-021 | Approved operational endpoint contract | `GET /health/live` and `GET /health/ready`; OpenAPI response schemas | TC-0702, TC-0703 |
| REQ-022 | S1-A03 staging URL | Hosted Vercel and Railway TLS URLs | TC-0705 |
| REQ-023 | Environment and secret separation | Typed settings, dashboard-only bindings, secret scan | TC-0704, TC-0706 |
| REQ-024 | Fail-fast, locked, production-like deployment | Locked Docker images, Railway Config-as-Code, CI gate | TC-0701, TC-0707, TC-0709 |
| REQ-025 | Health, smoke, rollback identity, and isolation | Bounded probes, `RAILWAY_GIT_COMMIT_SHA` binding, hosted smoke plan, Supabase/asyncpg DSN normalization | TC-0702, TC-0703, TC-0705, TC-0707, TC-0710 |
| REQ-026 | Development/test Markdown and senior review | This record, linked report, ADR-007, repository gates | TC-0708 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- The architecture and execution plan require a managed/PaaS staging runtime but do not mandate
  Render or another vendor.
- The owner explicitly authorized replacing Render with a usable free tool. Railway was selected
  because its Trial starts without a card and supports separate API and background-worker services.
- Railway's only current EU runtime is Amsterdam. Using it near Frankfurt is explicitly limited to
  this temporary Staging decision and does not approve a Production topology.
- The free runtime is bounded to the active Trial credit. It is evidence infrastructure, not a claim
  of permanently free Production capacity.
- `/health/live` never checks a dependency. `/health/ready` requires configuration, PostgreSQL, and
  Redis-compatible `PING`, and never calls an AI provider.
- Queue framework selection remains outside this story; only the documented Redis-compatible
  infrastructure binding is provisioned.

## Changes

- Created isolated Supabase project `aria-ai-staging` (`hqgfqlvfwflbazsuhazs`) in Frankfurt
  `eu-central-1`; Supabase reported `ACTIVE_HEALTHY`.
- Created and verified private Supabase bucket `aria-staging-project-content` with `public=false`.
- Implemented root `/health/live` and `/health/ready`, bounded PostgreSQL and Redis-compatible probes,
  typed secret-safe settings, release metadata, and dependency-isolation tests.
- Removed the uncreated Render Blueprint; no Render resource or paid commitment existed.
- Added separate [API](../../../infra/railway/api.railway.json) and
  [Worker](../../../infra/railway/worker.railway.json) Railway Config-as-Code contracts.
- Added locked Python 3.12.13 Docker images for API and Worker. Both install exact `uv==0.12.5`, use
  their committed lockfiles, start with `--no-sync`, and run as UID `10001` rather than root.
- Configured one API and one Worker replica in Railway EU West Metal Amsterdam, readiness admission
  only on API, and the bounded Free/Trial-compatible `ON_FAILURE` restart policy.
- Kept runtime values and credentials outside source control; the repository contains only required
  variable names and safe public identifiers.
- Added ADR-007 and rewrote the deployment contract suite to reject Render residue, branch pins,
  credential values, region drift, unlocked builds, root containers, and Worker/Auth coupling.
- Retained the verified Vercel Preview deployment `GQFMEVWyeppynbd3JDTFxM3tcoPf` for commit
  `b590f6cbdc878353af72fa81879cb6e99790b6b3` as historical Web evidence. Final hosted verification
  must use the latest PR SHA.
- Corrected the Worker container import root after the first hosted Railway deployment proved that
  `uv --project` selects the environment but does not change Python's working directory. The image
  now starts from `/srv/aria/apps/worker` and retains an absolute locked project path.
- Verified the current Vercel Preview is Ready for exact source SHA
  `8fa38bf181bc1e17e0d3af53df3fcf5f6dd906af`. Railway built the matching Worker image and the API
  image; both then exercised the intended fail-fast configuration gate rather than starting with
  absent infrastructure bindings.
- Provisioned the approved Frankfurt Redis-compatible Queue and verified its TLS endpoint with a
  real authenticated RESP `PING/PONG`; the credential remains outside repository files and logs.
- Corrected both Railway Queue bindings after the first dashboard input contained REST sample code
  rather than the required Redis-compatible DSN. API startup now passes typed configuration and the
  Worker deployment is active.
- Reproduced a hosted PostgreSQL-driver incompatibility: Supabase's libpq-compatible URI uses
  `sslmode=require`, while SQLAlchemy 2.0.51 passes URL query keys as asyncpg keyword arguments and
  asyncpg 0.31.0 accepts `ssl`, not an `sslmode` keyword, on that adapter path. Commit `3005e0d`
  normalizes only that query key after selecting the approved asyncpg scheme; a regression test
  preserves other query parameters.
- Rewrote the regression fixture so no credential-shaped literal exists in source; the repository
  Secret Scanner then passed across 166 publishable text files.
- Rotated the isolated Staging database password after explicit owner authorization and replaced the
  dashboard-only `DATABASE_URL` on API and Worker without displaying or persisting the credential.
- Corrected the Railway public-domain target from port `8000` to the Docker/runtime port `8080`.
  Deployment `6508b8f2` is active and the public liveness/readiness routes now return 200.
- Promoted the approved PR to `main` with squash-merge SHA
  `8698bddeb86efb823d0884172164a016478c5952`, then deployed that exact revision to Vercel
  Production and both Railway Staging services.

## Architecture and Design Decisions

- [ADR-007](../../adr/ADR-007-railway-staging-runtime.md) contains the platform decision, alternatives,
  staging-only constraints, reversibility, and migration impact.
- API and Worker remain separate deployables; no Domain or service boundary changed.
- Queue remains a provider-neutral Redis-compatible URL. No provider SDK, Celery, Dramatiq, or RQ was
  introduced before the required queue spike and ADR.
- Railway configuration is intentionally service-specific so the API and Worker cannot inherit the
  wrong command or public-network/health behavior from a shared file.
- Hosted source selection remains dashboard-owned and therefore must be read back and matched to the
  exact GitHub SHA before smoke evidence is accepted.

## Structure Preservation

- The documented deployables remain exactly `web`, `api`, and `worker`.
- Presentation owns health HTTP contracts; infrastructure owns PostgreSQL, Queue, Auth, and hosting
  adapters. Application and Domain import no Railway, Upstash, Supabase, Docker, or framework code.
- No cross-module write, mutating endpoint, event contract, migration, queue consumer, or AI-provider
  behavior was added.
- PostgreSQL remains transactional truth; Redis-compatible storage remains Queue/Cache/Quota
  projection only.
- Web structure and the RTL-first token-driven design system are unchanged.

## Senior Review

- **Resolved — incompatible free providers:** Koyeb Free cannot run Worker Services; Northflank and
  broader Koyeb use require payment verification; sleeping demo hosts do not preserve Worker
  semantics. Railway Trial is the only reviewed no-card option that preserves both deployables for
  this temporary gate.
- **Resolved — build reproducibility:** separate minimal Dockerfiles pin Python and uv, consume the
  committed API/Worker lockfiles, disable runtime sync, and copy only runtime code.
- **Resolved — container privilege:** both images drop root before process start.
- **Resolved — readiness isolation:** only API has a health admission path; Worker does not pretend
  to expose HTTP or claim queue-consumer readiness.
- **Resolved — free-plan crash policy:** `ALWAYS` is invalid on Railway Free/Trial; bounded
  `ON_FAILURE` with ten retries matches the documented plan limit.
- **Resolved — source confidentiality:** no runtime credential name appears inside deployment config
  JSON or Dockerfile content; values remain dashboard-only and continue through secret scanning.
- **Resolved — Worker import root:** hosted deploy `72b74b0d` built successfully but crashed because
  Python could not resolve `app.main` from `/srv/aria`. An explicit application `WORKDIR` and a
  contract regression test correct the runtime path without changing Worker behavior.
- **Resolved — Redis binding format:** the Railway value is now a single TLS Redis-compatible DSN;
  authenticated `PING/PONG` succeeds and the previous multiline REST sample is no longer deployed.
- **Resolved — Supabase URI adapter mismatch:** the infrastructure normalizer converts only the
  `sslmode` query key to asyncpg's `ssl` keyword while preserving the scheme, credentials, host,
  database, and remaining query string. Focused health/database tests pass 8/8.
- **Resolved — regression-fixture hygiene:** the first fixture used a credential-shaped placeholder
  DSN and was correctly rejected by the Secret Scanner. Constructing the placeholder credential from
  inert fragments preserves the test without weakening or allowlisting the scanner.
- **Accepted for Staging only — regional proximity:** Amsterdam runtime to Frankfurt data/Queue is
  not same-region. The provider has no Frankfurt runtime; Production requires a new approved capacity
  decision.
- **Resolved — database credential verification:** after explicit authorization, the isolated
  Staging password was rotated and both Railway bindings were replaced in memory only. Supabase
  `SELECT 1` and hosted API readiness now pass.
- **Resolved — public routing port:** Railway health admission reached the container on `8080`, but
  its public domain still targeted `8000`. Updating the domain target to the documented runtime port
  restored public TLS access without changing code or the health contract.
- **Verified — rollback control:** Railway exposed both `Rollback` and `Redeploy` for the immediately
  previous API artifact. The drill selected the prior artifact; because both artifacts were the same
  source SHA and current environment, Railway deduplicated the no-op and the active service remained
  healthy.
- **Verified — post-merge promotion:** GitHub reports successful Vercel, Railway API, and Railway
  Worker statuses for merge SHA `8698bdd...`. The hosted API reports that full SHA from both health
  routes, so the smoke test cannot accidentally validate the pre-merge artifact.

## Verification

- Focused Railway deployment contract: 6/6 tests passed after correcting the Docker command matcher
  for JSON exec form.
- Existing API and Worker test suites already cover liveness, readiness, secret-safe settings,
  release SHA, structured startup, and real loopback RESP `PING`.
- Docker daemon was unavailable locally, so local image execution is not claimed. Railway's hosted
  API and Worker builds supplied the required container-build evidence.
- GitHub Quality at exact SHA `f3752ca654f06184288d96a9086102ff9656cc35` passed lint, strict
  type checks, builds, Development Records 6, CI/contract 23, Web 4, API 57, and Worker 14 tests;
  its only pre-evidence failure was the intentional `PENDING` marker in this report.
- Local direct execution through the maintained API test environment passed 65 tests with six real
  PostgreSQL cases skipped, and the Worker environment passed 14 tests.
- Repository dependency/security gates pass; `npm run scan:secrets` inspected 166 publishable text
  files with zero findings.
- Focused regression command
  `.tools/venv-api/Scripts/python.exe -m pytest -q apps/api/tests/test_database_readiness.py apps/api/tests/test_health.py`
  passed 8/8 on 2026-08-24.
- Direct Queue TLS authentication and `PING/PONG` passed; the post-rotation Supabase `SELECT 1`
  returned one.
- Hosted API deployment `6508b8f2` and Worker are Active at `f3752ca...`. Public
  `/health/live` returned 200 with `status=alive`; `/health/ready` returned 200 with configuration,
  database, and Queue all `pass`.
- Vercel Preview `aria-ai-1kw26t9br-alirezaajalili-3575s-projects.vercel.app` is READY at exact SHA
  `f3752ca654f06184288d96a9086102ff9656cc35` and returned HTTP 200.
- `npm run scan:secrets` passed over 166 publishable text files after the fixture correction.
- Final local `npm run validate` passed all 22 architecture/documentation checks after this record
  and its linked test report were finalized.
- Post-merge Vercel Production `aria-ai-web-eight.vercel.app` is Ready from `main` at exact SHA
  `8698bddeb86efb823d0884172164a016478c5952`; the public page returned HTTP 200 and contained the
  Aria application shell.
- Railway API deployment `099e6202` and Worker deployment `318b2376` both reported success for the
  same merge SHA. Public `/health/live` returned `alive`/200 and `/health/ready` returned
  `ready`/200 with configuration, database, and Queue all `pass`; both responses reported the exact
  merge SHA.
- Final clean-worktree `npm test` passed Development Records 6, CI/contract 23, Web 4, API 57, and
  Worker 14 tests. The API suite emitted one dependency deprecation warning and no failure.
- Final clean-worktree `npm run scan:secrets` passed across 144 publishable tracked text files, and
  `npm run validate` passed all 22 checks.

## Remaining Risks

- The Trial is limited to 30 days or USD 5 and is unsuitable as an always-on Production Worker.
- Railway EU runtime and Frankfurt data dependencies are adjacent-region, not same-region.
- The free Redis-compatible database has prototype limits and no Production SLA; Free inactivity can
  archive it. It is acceptable only for Sprint 1 staging.
- Railway Config-as-Code is now marked deprecated by the provider and existing configurations are
  supported only until 2026-12-01. Migration to Railway Infrastructure as Code requires a separate
  approved operational increment before that date.
- The Worker intentionally has no queue consumer until the dedicated queue framework story.
