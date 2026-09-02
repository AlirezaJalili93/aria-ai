# Development Record: 0022 Project Dashboard

- Increment ID: `0022-project-dashboard`
- Date: 2026-09-02
- Owner: Codex (implementation and senior review)
- Related plan/issue: `S1-C03 — Project Dashboard`
- [Test report](./test-report.md)

## Scope

Implement the RTL-first Project dashboard, single-step Project creation and metadata-only Project
overview on top of the approved S1-C02 API. The increment includes safe single-Account automatic
selection, zero/multiple-Account blocking states, incremental pagination and versioned internal
Product Analytics events. Account selection UI, Project description/client fields, fabricated
progress/counts and a third-party analytics provider remain out of scope.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — synchronized 2026-09-02; `S1-C03`.
- [Frontend UX State Specification v1.0](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) — synchronized 2026-09-02; `PL-*`, `CP-*`, `PW-*` states.
- [UX Information Architecture v1.0](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) — synchronized 2026-09-02; `SCR-06` through `SCR-08`.
- [Analytics Event & Reporting Specification v1.0](https://docs.google.com/document/d/1e77c3ZpkjgJV2Gn7OLm0vUJUZOZzTRFs5YCy3LENOhI/edit) — synchronized 2026-09-02; naming and sensitive-data constraints.
- [API Contract Specification v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — synchronized 2026-09-02; Account and Project contracts.
- Owner approval dated 2026-09-02 for the four S1-C03 clarification contracts.
- Repository `AGENTS.md`, `design-system/MASTER.md`, ADR-011, and the owner-provided `ui-ux-pro-max.md` and `design-system.md` skills.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-106 | S1-C03; UX `PL-*` | Project list loading/empty/populated/error states and create CTA | TC-2201, TC-2202 |
| REQ-107 | Owner; ADR-011 | One active Account auto-selects; zero/multiple Accounts send no tenant request | TC-2203 |
| REQ-108 | UX `PL-07`; S1-C02 API | Incremental opaque-cursor pagination without resetting loaded items | TC-2204 |
| REQ-109 | Owner; UX `CP-*` | `/projects/new`, title/type only, validation, pending guard and retry-stable idempotency | TC-2205, TC-2206 |
| REQ-110 | Owner; UX `CP-04` | Successful create redirects to `/projects/{projectId}` | TC-2207 |
| REQ-111 | Owner; UX `PW-*` | Metadata-only Project overview, safe missing state and disabled future sections | TC-2208, TC-2209 |
| REQ-112 | Owner; Analytics spec | Versioned `project_created`, `project_opened`, `project_type_selected` events without content | TC-2210 |
| REQ-113 | Design System; UX baseline | RTL, semantic controls, visible focus, 44px targets, responsive and reduced motion | TC-2211, TC-2212 |
| REQ-114 | Repository governance | Mandatory records, full quality gates and structure preservation | TC-2213 |

## Assumptions and Clarifications

The owner explicitly approved single-Account automatic selection, a generic blocked state for
multiple Accounts, a one-step title/type form, a metadata-only overview and internal Product
Analytics without a new provider. The current API has no Account label, client/description field,
progress, readiness score, stage aggregate or downstream module counts, so none are introduced.

**Unapproved assumptions:** None

## Changes

- Added a server-only Web API adapter that validates the exact Account/Project response vocabulary,
  forwards the access token only after `getClaims()` verification, creates request/correlation IDs
  and surfaces only safe error references.
- Added zero/multiple/single Account state resolution. Tenant Project calls are made only for the
  single selected Account; Account discovery remains pre-tenant and sends no `X-Account-ID`.
- Replaced the placeholder Projects screen with loading, empty, populated, recovery and incremental
  opaque-cursor states. Client serialization is restricted to the five fields used by the list.
- Added `/projects/new` with only title and the three approved Project types. The form enforces
  validation, focuses server error summaries, blocks double submission and retains the same
  Idempotency-Key for an unchanged retry; an edited retry receives a new key.
- Added `/projects/{projectId}` with only persisted metadata, archived/read-only messaging, safe
  not-found behavior and explicit not-started shells for Context, Requirements, Gaps and Scope.
- Added a dedicated versioned Product Analytics schema for Web events and the authoritative
  server-side `project_created` outcome. No third-party analytics provider was introduced.
- Added Web contract/privacy/a11y tests and API tests for the authoritative analytics event.

## Architecture and Design Decisions

The existing API remains the identity, tenant and Project authority. Access tokens never cross the
Server Component/Server Action boundary into browser props. The Web adapter parses external JSON as
`unknown` and rejects vocabulary/schema drift. Account resolution is deliberately not cached because
the API exposes current active Membership authority and all requests are `no-store`.

Project create idempotency is owned by the API; Web preserves the key across an unchanged retry and
does not treat it as Product data. Product Analytics is represented by a dedicated event category and
versioned safe schema. `project_created` is emitted only after the new transaction commits and not on
an idempotent replay; browser events cover open/type-selection. The existing internal structured-event
sink is used, so the approved provider deferral is preserved.

## Structure Preservation

- Next.js App Router and the existing `/projects` route hierarchy are preserved; no deployable,
  endpoint, database field, migration or public API contract was added.
- Auth/Supabase access remains in the server-side feature boundary. Client Components receive no JWT,
  session, owner identifier or unused Account/Project fields.
- Identity Account Discovery remains pre-tenant; all Project requests use the existing
  `X-Account-ID` tenant contract and the API independently re-verifies authorization.
- Primitive → semantic → component design tokens, logical RTL CSS, one primary action, 44px controls,
  visible focus and reduced-motion behavior are preserved. Component CSS contains no raw color.
- Description/client, status mutations, account labels/selection and downstream Project data remain
  absent rather than being inferred from older or incomplete documents.

## Senior Review

- **HIGH — corrected:** Server Actions initially caught Next.js redirect exceptions while mapping API
  failures. Auth resolution now returns an explicit state; redirect occurs outside catch blocks.
- **MEDIUM — corrected:** initial page code returned JSX inside `try/catch`, which React cannot use as
  a render error boundary, and applied unsupported `aria-disabled` to a section. Data is now assigned
  before rendering and unavailable modules communicate state through text without invalid ARIA.
- **Data minimization — corrected:** the first list boundary serialized complete API Project objects.
  It now passes only `id/title/project_type/status/updated_at` to the Client Component.
- **Idempotency/recovery:** PASS. An unchanged failure retry retains the same key and form contents;
  editing the payload intentionally rotates the key. Pending UI prevents duplicate interactive submit.
- **Security/isolation:** PASS. Zero/multiple Accounts cannot issue tenant requests; invalid/missing and
  cross-tenant Projects converge on the existing generic not-found state; JWTs never reach Web events.
- **Analytics/privacy:** PASS. Events contain only approved identifiers/vocabulary and schema metadata.
  Title, JWT, callback data, raw request bodies and Project content are absent.
- **React/performance:** PASS. Server Components own initial data, Server Actions re-authorize
  mutations/pagination, list appends are deduplicated by ID and no third-party client bundle was added.
- **UI/accessibility:** PASS. Browser checks found no overflow or framework/console error at 375, 768
  and 1024 widths. Axe WCAG A/AA reported zero violations; reduced-motion resolved to `1ms`.

## Verification

Full monorepo lint/typecheck/build, 18 Web tests, focused API analytics tests and browser QA passed.
The mandatory repository-wide `npm test` passed (6 record tests, 53 CI contracts, 18 Web tests,
114 API tests with 19 documented integration skips, and 16 Worker tests). `npm run validate` passed
all 22 architecture/development-record checks. After the final accessibility hardening, the complete
`npm run quality` pipeline was repeated and passed. GitHub PR #16 then passed Quality, Security and
Vercel Preview on exact commit `1260fea9c4de822acf48c7e76cfce5f2d9cb8bf4`; exact results are in
the linked test report.

PR #16 was subsequently squash-merged to `main` as
`40bca5ad302a43f2f8bbf342ec938cecf60d86ed`. The post-merge CI run passed Quality and Security,
Vercel completed the deployment for that exact SHA, and both Railway API and Worker deployments
reported success. Hosted `/health/live` and `/health/ready` returned HTTP 200 with the exact merge
SHA; readiness reported configuration, database and queue as `pass`.

## Remaining Risks

- Multi-Account selection is intentionally blocked until an approved Account label and selection UX
  contract exists.
- Product Analytics currently uses the internal event sink. Provider delivery remains deferred by the
  owner and therefore external analytics dashboard evidence is outside this increment.
- The Vercel Preview is protected by Vercel Authentication. Its SHA-bound deployment status passed,
  but an unauthenticated hosted journey smoke cannot cross that protection; local browser journey
  states and the production build are the executable UI evidence for this branch.
