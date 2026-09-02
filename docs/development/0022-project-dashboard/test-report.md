# Test Report: 0022 Project Dashboard

- Increment ID: `0022-project-dashboard`
- Date: 2026-09-02
- [Development record](./development.md)

## Environment

Windows workspace; Node.js 24+; Next.js 16/React 19; Python 3.12/FastAPI. Secrets are not recorded.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2201 | Component/Contract | Project list has loading, empty and populated states | State-specific semantic UI and canonical create CTA |
| TC-2202 | Recovery | Account/Project fetch fails | Safe retry UI includes a non-sensitive request reference when available |
| TC-2203 | Security/Contract | Zero, one or multiple active Accounts | Only one Account enables tenant requests; other states are safely blocked |
| TC-2204 | Component/API | Load the next opaque cursor page | Existing rows remain and new rows append without duplicate identifiers |
| TC-2205 | Form/Validation | Submit title/type form | Only trimmed title `1..255` and approved type are accepted |
| TC-2206 | Resilience | Double-submit or retry failed create | Pending submission is disabled and the same Idempotency-Key is reused |
| TC-2207 | Integration | API returns `201` | Redirect to `/projects/{projectId}` |
| TC-2208 | Component/API | Open an active or archived Project | Only real metadata and explicit unavailable-module states are shown |
| TC-2209 | Security | Missing/cross-tenant Project | Same generic not-found experience; no existence disclosure |
| TC-2210 | Privacy/Analytics | Create/open/type-select events | Versioned Product Analytics schema; no title, token or raw content |
| TC-2211 | Accessibility | Keyboard, labels, live regions and targets | Semantic/labelled controls, focus visibility and minimum 44px targets |
| TC-2212 | Visual/Responsive | 375px, 768px, 1024px and reduced motion | No horizontal overflow; RTL hierarchy remains usable |
| TC-2213 | Repository gate | Full tests, build and architecture validation | All mandatory gates pass and records are final |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-2201–TC-2211 | `npm run test:web` | 18/18 Web contract, state, privacy and accessibility tests passed | PASS |
| TC-2205–TC-2211 | `npm run lint:web` | ESLint completed with zero warnings/errors | PASS |
| TC-2201–TC-2211 | `npm run typecheck:web` | Strict TypeScript check passed | PASS |
| TC-2210 | focused `pytest` for `test_project_application.py` | 9/9 Project Application tests passed, including server outcome schema/privacy | PASS |
| TC-2201–TC-2211 | `npm run build:web` | Next.js production build passed; all three Project routes compiled dynamic | PASS |
| TC-2212 | Chrome headless at 375px list, 768px create and 1024px overview | Meaningful semantic content, no horizontal overflow, no Next error overlay or page errors | PASS |
| TC-2211, TC-2212 | axe 4.12.1 WCAG A/AA on create and overview | 0 violations and 0 incomplete checks; 23/21 checks passed respectively | PASS |
| TC-2212 | Chrome `prefers-reduced-motion` on overview | `--primitive-duration-fast` resolved to `1ms` | PASS |
| TC-2213 | `npm run lint` | Web ESLint and API/Worker Ruff passed | PASS |
| TC-2213 | `npm run typecheck` | Web TypeScript plus API/Worker mypy passed | PASS |
| TC-2213 | `npm run build` | Next.js production build and API/Worker compile passed | PASS |
| TC-2213 | `npm test` | 6 record + 53 CI + 18 Web + 114 API + 16 Worker tests passed; 19 configured API integration tests skipped | PASS |
| TC-2213 | `npm run validate` | All 22 architecture and development-record checks passed | PASS |
| TC-2201–TC-2213 | final `npm run quality` | Lint, typecheck, full tests, all builds and 22 architecture checks passed after the last code correction | PASS |
| TC-2210, TC-2213 | `npm run scan:secrets` | 265 publishable text files inspected; no secret detected | PASS |

## Failures and Corrections

- The first Web lint run found JSX returned inside `try/catch` and invalid `aria-disabled` on a
  section. Rendering was moved outside catch blocks and the unsupported ARIA attribute was removed;
  the repeated lint run passed.
- A later full quality run rejected unsupported `aria-invalid` on an individual radio control. The
  redundant attribute was removed while the group error association and first-radio focus recovery
  were retained; the full quality command was repeated.
- The first focused API test command could not initialize the user-level uv cache. The unchanged test
  was repeated with a task-local cache and all 9 cases passed.
- Full API/Worker test execution reported existing pytest cache-permission warnings; test execution
  completed successfully and the authoritative result remained 114 API plus 16 Worker tests passed.
- The first temporary visual fixture path began with `__` and Next returned 404. The uncommitted
  fixture was exposed once at a conventional temporary path; all browser checks passed, then the
  fixture and proxy exception were removed before the final code/test run.

## Final Status

**Final status:** PASS
