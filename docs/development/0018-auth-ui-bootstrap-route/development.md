# Development Record: 0018 Auth UI and Bootstrap Route

- Increment ID: `0018-auth-ui-bootstrap-route`
- Date: 2026-08-25
- Owner: Codex (implementation and senior review)
- Related plan/issue: Sprint 1 backlog story `S1-B05 — Auth UI + Callback`
- [Test report](./test-report.md)

## Scope

Implement the approved Email/Password-only login, signup, confirmation callback, logout, protected
`/projects` destination, and the explicit pre-tenant Account Bootstrap command required by the
frontend journey. Record the owner-approved supersession of the earlier implicit-only Bootstrap
decision.

Magic Link, password recovery, onboarding, Project creation, legal URLs, consent persistence,
Account/Profile query payloads, and external beta/public signup are out of scope.

## Source Documents

Canonical Google Drive documents reviewed on 2026-08-25:

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — `S1-B05` acceptance criteria.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — Signup/Login states, first-use Project state, RTL and recovery-oriented errors.
- [Frontend UX State Management Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — booting, unauthenticated, Bootstrap pending and error states.
- [Sprint 0 Technical Decision v1.0](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — Next.js/TypeScript and Supabase Auth boundary.
- [Engineering Backlog v1.0](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — Auth journey; older Magic Link/onboarding/legal scope superseded for this Story by the owner clarification.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — frontend state, accessibility, identity and end-to-end coverage.
- [Dependency & Vendor Register v1.0](https://docs.google.com/document/d/1AVZdOzMahLmNL9c38q9DObuR1C4R787ROc85FBnLgHE/edit) — Supabase Auth and Vercel boundaries.
- Owner clarifications dated 2026-08-25 approving the exact S1-B05 scope, safe logging events,
  mandatory verification, `/auth/callback`, `/projects`, `POST /api/v1/auth/bootstrap`, and
  SHA-verified hosted Preview acceptance contracts.
- Repository `AGENTS.md`, [system architecture](../../architecture/system-architecture.md),
  [design-system master](../../../design-system/MASTER.md), and
  [document-driven development policy](../../governance/document-driven-development.md).
- Current official Supabase SSR/Auth guidance and npm registry versions reviewed 2026-08-25.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-073 | S1-B05; owner scope decision | Email/Password-only Login and Signup; no Magic Link or Recovery | TC-1801, TC-1802 |
| REQ-074 | Owner clarification | Mandatory verification state; Signup never enters `/projects` before callback | TC-1802, TC-1805 |
| REQ-075 | Owner clarification | Canonical `/auth/callback` resolves session, then Bootstrap, then `/projects` | TC-1803, TC-1806 |
| REQ-076 | Owner clarification | `POST /api/v1/auth/bootstrap`: Bearer-only, no tenant header/body/response data, success 204 | TC-1807–TC-1811 |
| REQ-077 | Owner guardrails | Bootstrap remains idempotent/concurrency-safe command and never becomes a hidden `/me` query | TC-1808, TC-1812 |
| REQ-078 | Existing Auth taxonomy; owner clarification | Invalid JWT 401; provider outage 503; Bootstrap failure stable retryable 503 | TC-1809–TC-1811 |
| REQ-079 | S1-B05 UX AC; Frontend State spec | Loading, confirmation, callback error/expired, protected route and logout states | TC-1801–TC-1806 |
| REQ-080 | Owner clarification; observability contract | Exact safe Auth/Bootstrap event names without credentials or identity data | TC-1813, TC-1814 |
| REQ-081 | UX IA; owner clarification | `/projects` first-use empty state contains «ایجاد اولین پروژه» without onboarding | TC-1804 |
| REQ-082 | Owner legal scope decision | No invented Terms/Privacy URL or consent version; external signup remains blocked | TC-1802, TC-1815 |
| REQ-083 | Design System; WCAG/RTL requirements | RTL-first, visible labels/focus, logical CSS, 44px targets, reduced motion | TC-1816–TC-1819 |
| REQ-084 | Owner Preview acceptance decision | Vercel Web and Railway API/Worker deploy the exact PR SHA before merge; hosted smoke and safe-log evidence pass | TC-1821, TC-1822 |

## Assumptions and Clarifications

The owner explicitly approved the pre-tenant command contract and its ADR exception after repository
inspection showed no callable route for the required frontend sequence.

**Unapproved assumptions:** None

## Changes

- Added the API command `POST /api/v1/auth/bootstrap`, registered it under `/api/v1`, and exposed
  the exact no-body/empty-204 Bearer contract in `packages/contracts/openapi.yaml`.
- Reused `BootstrapAccountUseCase` through the API dependency boundary. The command is protected by
  authenticated identity only; existing identities with invited/suspended Membership remain
  bootstrapped but receive no tenant authorization or response data.
- Added the retryable `503 ACCOUNT_BOOTSTRAP_FAILED` error envelope and safe
  `account.bootstrap_failed` infrastructure event.
- Added [ADR-009](../../adr/ADR-009-pre-tenant-account-bootstrap-command.md), updated the ADR index,
  and marked the implicit-only decision in increment 0011 as superseded.
- Added Supabase SSR clients, session Proxy, Email/Password Login and Signup Server Actions,
  mandatory-confirmation state, canonical callback, Logout command, and protected `/projects`
  route under the existing Next.js App Router.
- Added the first-use Project empty state and the approved «ایجاد اولین پروژه» CTA. The control is
  intentionally non-mutating until the separately documented Project-creation Story supplies its
  endpoint and navigation contract.
- Added safe structured frontend Auth events with generated request/correlation identifiers and no
  credential, email, raw subject, callback query, or token fields.
- Disabled framework incoming-request logging for `/auth/callback`, scrubbed callback credentials
  before redirects, and marked Auth redirects private/no-store.
- Extended the existing primitive-to-semantic-to-component token chain for the Auth shell and added
  RTL-first, responsive, focus-visible, 44px-target and reduced-motion styles.
- Added API behavior tests, Web contract tests, Bootstrap contract regression tests, dependency
  updates and non-secret environment placeholders.

## Architecture and Design Decisions

- The browser never writes Identity projections directly. Its only bootstrap integration is the
  provider-neutral API command: Web → API dependency → Application use case → Infrastructure UoW.
- The pre-tenant command is a narrow lifecycle exception documented by ADR-009. It does not require
  `X-Account-ID`, and it does not authorize tenant operations.
- Bootstrap remains a command, not a query: no `/me`, Account ID, Profile, Membership list, role, or
  preferences are returned.
- Supabase-specific session handling stays in `features/auth/supabase`; API verification remains in
  the existing Supabase infrastructure adapter. No Domain package imports framework/provider code.
- The earlier Magic Link/onboarding/legal wording is superseded only for S1-B05 as explicitly
  approved. No synthetic legal URL, consent version, recovery flow, or onboarding route was added.

## Structure Preservation

- Preserved the modular-monolith Identity boundaries and reused the existing transactional
  Bootstrap application service and UoW; no schema, migration, cross-module direct write, or new
  deployable was introduced.
- Preserved the documented Next.js/React/TypeScript and Python/FastAPI-compatible stacks.
- UI remains under the existing App Router and imports canonical design tokens. Component CSS
  contains no raw colors, and no new icon family or structural emoji was introduced.
- Existing tenant-protected routes still require active Membership; the command's identity-only
  guard does not weaken S1-B04 authorization.
- `npm run validate` continues to enforce all repository structure and development-record rules; no
  gate was bypassed or weakened.

## Senior Review

- Corrected an initial production-build failure caused by exporting a non-function value from a
  `"use server"` module by moving shared Action state to a type-only feature module.
- Corrected the first route implementation, which used the active-Membership dependency. The final
  route uses the identity-only pre-tenant dependency and has a regression test proving a previously
  bootstrapped inactive Membership still receives empty `204` without gaining access.
- Added stable differentiation between Auth-provider outage and Bootstrap infrastructure outage in
  the frontend command adapter.
- Added callback request-log exclusion after browser evidence showed the framework would otherwise
  print the credential-bearing URL in development output. Retesting proved only the safe structured
  event remains.
- Added private/no-store response headers to Auth callback/logout redirects in line with the
  Supabase SSR cookie contract.
- Reviewed all edited TSX against the React checklist: semantic controls, stable server/client
  boundaries, no effect-derived state, accessible status/errors, and no unnecessary client modules.
- Re-ran Ruff, MyPy, ESLint, TypeScript Strict, production build, contract tests, secret scan and
  dependency audit after the corrections. No unresolved HIGH/MEDIUM implementation finding remains.

## Verification

Local gates and browser verification pass; see the linked [test report](./test-report.md) for exact
commands and case-level evidence. Supabase Staging was read-only verified as `ACTIVE_HEALTHY` in
`eu-central-1`; public Auth settings prove Email is enabled, other providers are disabled, Signup is
enabled, and `mailer_autoconfirm=false` enforces confirmation. Its public JWKS exposes the approved
EC/ES256 signing key, and the RLS-enabled Identity tables remain present without test-user data.
[GitHub Actions run 32822141009](https://github.com/AlirezaJalili93/aria-ai/actions/runs/32822141009)
passed both Quality and Security baseline on PR SHA
`e8a048e4c727b769c8d9d83f799bb711fa310232`, including all 99 API tests against the workflow's
PostgreSQL 16 service.

Hosted acceptance was repeated on 2026-08-31. Vercel deployment
`D5pcva4roeTm2b4mGAHJcsrdQCwd` is Ready and identifies the exact branch and full PR SHA. Railway's
independent `aria-staging-api` deployment `5f6e2aa1-7b54-4582-8fb8-52f1f6ceca54` and
`aria-staging-worker` deployment `03fa122f-1b35-4abc-aa3f-cab962adb756` both report success for the
same SHA. Hosted `/health/live` and `/health/ready` return that full SHA; configuration, database and
queue are all `pass`. Browser smoke verified the Login rejection path, scrubbed invalid Callback,
unauthenticated `/projects` redirect, RTL layout and 44px control. Deployment-scoped runtime logs
contain the approved safe events, no synthetic Email/password/token, and zero Warning/Error/Fatal
entries.

## Remaining Risks

- A successful delivered-email callback was not exercised because no authorized test mailbox was
  supplied. The valid callback path is covered by source-contract tests and production compilation;
  a real mailbox journey remains a hosted deployment acceptance check before external beta.
- Project creation is outside S1-B05. The approved CTA is present but deliberately disabled until
  its documented Story supplies a command/navigation contract.
- Public/real-user Signup remains blocked by the approved Legal/Consent increment even though the
  Supabase Staging project permits internal Signup.
