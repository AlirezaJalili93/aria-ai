# Development Record: 0004 Repository Bootstrap

[Test report](./test-report.md)

## Scope

Bootstrap the approved Sprint 1 repository shape for a Next.js/TypeScript web app, Python 3.12+/FastAPI API, and Python worker without implementing product features, external integrations, queue selection, or persistence.

## Source Documents

- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit)
- [Aria AI — Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit)
- [Aria AI — Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit)
- [Aria AI — Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit)
- [Aria AI — Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit)
- [Aria AI — Coding Standards & Engineering Conventions v1.0](https://docs.google.com/document/d/1aDMdM0VXYf6widpZL5bnZkyzoV98yxXHaAGytiDiRjo/edit)
- [Aria AI — Engineering Definition of Ready & Definition of Done v1.0](https://docs.google.com/document/d/1_2XaZvFw8mDKve3_FMBxpQfaG4AOW64ZVntCiHTdQns/edit)
- `design-system/MASTER.md`
- User-approved decisions: Architecture v2 supersedes the legacy JavaScript backend; use npm workspaces and uv with stable pinned versions; keep historical development records.

## Requirement Traceability

| Requirement | Source | Implementation | Test evidence |
|---|---|---|---|
| REQ-004 | S1-A01 Repo Bootstrap | Root workspace, `apps/*`, `packages/*`, `infra`, `evals`, `tests/e2e` | TC-0401, TC-0409 |
| REQ-005 | S1-A01 clean local Web/API/Worker build | `apps/web`, `apps/api`, `apps/worker`, exact manifests and lockfiles | TC-0402, TC-0403, TC-0404, TC-0409 |
| REQ-006 | S1-A01 setup README, environment example, no committed secret | `README.md`, `.env.example`, `.gitignore`, `infra/compose.yaml` | TC-0405, TC-0409 |
| REQ-007 | Architecture v2 and repository dependency boundaries | Python boundary skeletons, contracts, Architecture v2 mirrors, ADR-004, fitness validator | TC-0401, TC-0406, TC-0409 |
| REQ-008 | Design System Master: RTL-first, token layers, focus and reduced motion | `packages/design-tokens`, `apps/web/src/app/*` | TC-0407, TC-0410 |
| REQ-009 | User rule: development and test evidence in Markdown | This record, linked report, record validator | TC-0408, TC-0409 |

## Assumptions and Clarifications

**Unapproved assumptions:** None

- Queue framework, Auth integration, database migrations, storage provider, analytics vendor, and AI provider are explicitly deferred because their implementation stories or ADR decisions are outside this increment.
- Package managers and superseding of the legacy JavaScript backend were explicitly approved by the user on 2026-08-17.

## Changes

- Replaced the incompatible legacy JavaScript backend baseline with the approved Architecture v2 repository shape while retaining all prior development records.
- Added an npm workspace for the Next.js web application and shared packages, plus independently locked uv projects for API and worker.
- Added a strict, endpoint-free FastAPI application factory and typed runtime settings. No undocumented product route was introduced.
- Added a queue-neutral worker bootstrap. No queue framework was selected before the documented spike and ADR.
- Added exact direct dependency pins and reproducible `package-lock.json`/`uv.lock` files.
- Added the documented three-layer design-token model and a minimal RTL-first web shell with semantic landmarks, skip link, visible focus styling, 44px target sizing, AA color pairs, and reduced-motion handling.
- Updated local product, system architecture, and data model mirrors with their canonical Google Drive source links and synchronization date.
- Added Architecture v2 API/event contract baselines, local loopback-only infrastructure, environment template, ADR-004, repository setup documentation, and automated quality scripts.
- Retired the active legacy `packages/core` implementation and old contract content; historical development documentation was preserved.

## Structure Preservation

- The top-level and module layout follows the Repository & Code Structure Specification: `apps/web`, `apps/api`, `apps/worker`, shared `packages`, `infra`, `evals`, `tests/e2e`, and `docs`.
- API placeholders keep `core`, `api`, `modules`, `shared`, `infrastructure`, and `migrations` boundaries without inventing domain modules or endpoints.
- Worker placeholders keep `consumers`, `tasks`, and `runtime` boundaries without choosing a queue adapter.
- Domain/Application import fitness checks, tenant anchor naming (`accountId`), `/api/v1`, and the transactional-outbox/worker architectural rules are retained.
- Existing ADRs and development records `0001` through `0003` remain intact as historical evidence.

## Senior Review

- Reviewed manifests, lockfiles, application factories, test code, contracts, token references, CSS, repository boundaries, environment handling, and documentation links.
- Corrected ESLint 10 incompatibility with the Next.js lint stack by using the latest compatible exact ESLint 9 pin.
- Removed generated TypeScript build metadata and added it to `.gitignore`.
- Disabled Next.js automatic agent-rule files (`agentRules: false`) and added a regression test so local development does not alter the documented repository structure.
- Confirmed the API exposes no accidental default documentation or product routes and the worker stays queue-neutral.
- Confirmed no unresolved `TODO`, `FIXME`, legacy generation-state code, or old `workspaceId` tenant anchor remains in active source files.

## Verification

- Root quality gate passed: lint, strict type checks, 13 automated tests, Web production build, Python bytecode compilation, and 20 architecture checks.
- Dependency installation completed with zero npm audit vulnerabilities.
- Browser QA passed at 375x812 and 1440x900: RTL direction, Persian language, one H1, main landmark, no horizontal overflow, and no console warnings/errors.
- Detailed commands, test cases, environment, and actual results are recorded in [test-report.md](./test-report.md).

## Remaining Risks

- Queue framework selection remains intentionally open pending the documented spike and ADR.
- Authentication, persistence migrations, object storage, AI providers, analytics, and product endpoints are intentionally absent because this increment does not authorize their implementation.
- Browser automation confirmed the skip-link structure and focus CSS, but did not produce a reliable interactive Tab-focus observation in the background browser session; keyboard journey verification remains part of the first interactive UI story.
