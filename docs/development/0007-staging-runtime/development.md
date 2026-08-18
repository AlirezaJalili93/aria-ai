# Development Record: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-18
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
| REQ-025 | Health, smoke, rollback identity, and isolation | Bounded probes, `RAILWAY_GIT_COMMIT_SHA` binding, hosted smoke plan | TC-0702, TC-0703, TC-0705, TC-0707 |
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
- **Accepted for Staging only — regional proximity:** Amsterdam runtime to Frankfurt data/Queue is
  not same-region. The provider has no Frankfurt runtime; Production requires a new approved capacity
  decision.
- **Open — hosted proof:** exact Railway deployment SHA, runtime logs, TLS API URL, Queue binding,
  Supabase connectivity, rollback source, and latest Vercel SHA remain unverified until account Terms
  are accepted and the repository changes are deployed.

## Verification

- Focused Railway deployment contract: 6/6 tests passed after correcting the Docker command matcher
  for JSON exec form.
- Existing API and Worker test suites already cover liveness, readiness, secret-safe settings,
  release SHA, structured startup, and real loopback RESP `PING`.
- Docker daemon was unavailable locally, so image execution is not claimed. Railway's hosted build
  must supply the container-build evidence.
- `npm test` passed 90 tests: Development Records 6, CI/contract 19, Web 4, API 47, and Worker 14.
- Repository lint, strict TypeScript/MyPy checks, Web/API/Worker builds, dependency scan, and a secret
  scan of 142 publishable text files passed.
- `npm run validate` passes every architecture check and remains non-zero only because this report
  truthfully retains `PENDING` until hosted Railway evidence exists.
- Hosted smoke details are recorded in [test-report.md](./test-report.md) and remain pending until
  deployment.

## Remaining Risks

- Railway Terms require owner acceptance before services can be created.
- The Trial is limited to 30 days or USD 5 and is unsuitable as an always-on Production Worker.
- Railway EU runtime and Frankfurt data dependencies are adjacent-region, not same-region.
- The free Redis-compatible database has prototype limits and no Production SLA; Free inactivity can
  archive it. It is acceptable only for Sprint 1 staging.
- Hosted TLS, connectivity, exact SHA, logs, rollback, and post-deployment smoke are still pending.
- The Worker intentionally has no queue consumer until the dedicated queue framework story.
