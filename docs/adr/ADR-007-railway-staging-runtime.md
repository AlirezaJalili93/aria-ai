# ADR-007: Railway Trial Staging Runtime

- **Status:** Accepted for Sprint 1 staging only
- **Date:** 2026-08-18
- **Story:** S1-A03 — Staging Runtime
- **Supersedes:** The Render-specific portion of the S1-A03 deployment proposal

## Context

The approved architecture requires three deployables (`web`, `api`, and `worker`), an independent
staging environment, a durable Redis-compatible queue, managed infrastructure, dependency-aware
readiness, and SHA-verifiable releases. It does not mandate a hosting vendor. The original Render
proposal could not create API, Worker, or Key Value resources because identity verification required
a payment card. The owner then explicitly requested replacing Render with a usable free tool.

The replacement must preserve the Python 3.12 FastAPI and Worker code, keep API and Worker as
separate deployables, avoid selecting the still-open queue framework, keep credentials outside Git,
and provide enough runtime evidence to complete the Sprint 1 staging gate.

## Decision

1. Keep the Web deployment on Vercel and Supabase PostgreSQL/Auth/Storage unchanged.
2. Replace the uncreated Render API and Worker services with two Railway services sourced from the
   same GitHub repository and the verified `agent/staging-runtime` branch.
3. Use Railway's card-free 30-day/$5 Trial only for the temporary Sprint 1 staging deployment and
   hosted smoke evidence. Remove the Trial deployment after evidence capture unless a separately
   approved budget establishes an ongoing environment.
4. Deploy API and Worker independently in Railway EU West Metal
   (`europe-west4-drams3a`, Amsterdam), the nearest available Railway region to the existing
   Frankfurt Supabase project.
5. Replace Render Key Value with a separately managed Redis-compatible free database in Frankfurt.
   The application continues to receive only `QUEUE_BROKER_URL`; no provider SDK or queue framework
   enters Application or Domain.
6. Store deployment behavior in separate repository-owned Railway Config-as-Code files and locked
   Dockerfiles. Runtime variables and secrets remain dashboard-owned.
7. Keep `/health/live` dependency-free. Use `/health/ready` as the API deployment admission check;
   it requires PostgreSQL and Queue but deliberately excludes AI providers.
8. Use Railway's `ON_FAILURE` policy with at most ten restarts because `ALWAYS` is unavailable on
   Free/Trial. The Worker remains truthful about `queue_adapter_configured=false` until its dedicated
   queue story is implemented.
9. Treat this decision as Staging-only. It does not approve Railway Trial, Upstash Free, sleeping,
   limited credits, or cross-region traffic for Production/Closed Beta.

## Options considered

- **Render Starter:** compatible but blocked by mandatory card verification and not free.
- **Koyeb Free:** one free Web Service only; Free cannot run a Worker Service and still requires
  payment-method validation for broader use.
- **Northflank Developer Sandbox:** sufficient service/job shape but requires a payment method before
  resource creation.
- **Railway Free/Trial:** supports persistent API and background-worker services, GitHub deployment,
  custom Dockerfiles, health checks, and an EU region without an initial card. Its credit is bounded,
  so it is acceptable only for temporary staging verification.
- **Hugging Face Spaces:** free hardware sleeps and does not provide the required durable private
  worker runtime semantics.
- **Cloud Run / IBM Code Engine:** technically suitable serverless containers, but account billing
  verification and larger platform setup do not solve the immediate no-card staging blocker.

## Consequences

- The architecture retains exactly three deployables and independent API/Worker scaling.
- The platform change is reversible because all provider-specific behavior stays under
  `infra/railway` and environment variables.
- API and Worker are in Amsterdam while Supabase and Queue are in Frankfurt. This adds staging
  latency and disqualifies the topology as a Production region decision.
- The Railway Trial is not an always-free production runtime. It is adequate for hosted validation
  only; continuous Worker operation requires a later capacity and cost decision.
- GitHub PR checks remain the source gate, but Railway's branch and deployed SHA must be verified in
  hosted evidence because source-branch selection is dashboard-owned.

## Verification

- Contract tests validate separate API/Worker configs, region, locked Python/uv builds, non-root
  containers, readiness admission, bounded restart behavior, and absence of credentials.
- Hosted completion additionally requires Railway build logs, exact deployed SHA, TLS health calls,
  Worker startup evidence, Queue connectivity, and rollback-source readback.

## Sources

- Google Drive `Aria AI — Final System Architecture v2.0`
- Google Drive `Aria AI — Engineering Execution Master Plan v1.0`
- Google Drive `Aria AI — System Architecture Creation & Governance Plan v1.0`
- Owner request on 2026-08-18 to replace Render with a usable free tool
- Railway official Free Trial, pricing, services/worker, monorepo, Config-as-Code, healthcheck,
  restart-policy, and region documentation reviewed on 2026-08-18
- Upstash official Redis pricing, persistence, TLS, and region documentation reviewed on 2026-08-18
