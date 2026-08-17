# Test Report: 0004 Repository Bootstrap

[Development record](./development.md)

## Environment

- Status: verified on 2026-08-17
- OS: Windows
- Node.js: 24.11.1
- npm: 11.6.2
- Python: 3.12.13
- uv: 0.12.5 (approved stable pin)

## Test Cases

| Test ID | Requirement | Test | Expected result |
|---|---|---|---|
| TC-0401 | REQ-004 | Repository structure validation | Required monorepo paths exist |
| TC-0402 | REQ-005 | Next.js production build | Web build succeeds |
| TC-0403 | REQ-005 | FastAPI unit/static checks | API tests, lint and types pass |
| TC-0404 | REQ-005 | Worker unit/static checks | Worker tests, lint and types pass |
| TC-0405 | REQ-006 | Secret and environment scan | Example config has no real secret; ignored env files are not required |
| TC-0406 | REQ-007 | Architecture fitness checks | Forbidden Domain/Application imports are absent |
| TC-0407 | REQ-008 | Web shell accessibility/RTL/token checks | RTL semantics, focus, reduced motion, and token import are present |
| TC-0408 | REQ-009 | Development record validator | Linked records and traceability pass |
| TC-0409 | REQ-004 | Full repository quality gate | `npm test` and `npm run validate` pass |
| TC-0410 | REQ-008 | Browser QA at mobile and desktop viewports | No overflow or console errors; RTL landmarks and heading hierarchy are correct |

## Execution Results

| Test ID | Command or method | Actual result | Status |
|---|---|---|---|
| TC-0401 | `npm run validate` | Architecture v2 skeleton and required artifacts accepted | PASS |
| TC-0402 | `npm run build --workspace @aria/web` | Next.js production build completed; `/` rendered statically | PASS |
| TC-0403 | API Ruff, mypy strict, pytest, and `compileall` through uv | Ruff clean; mypy clean; 2 tests passed; compilation succeeded | PASS |
| TC-0404 | Worker Ruff, mypy strict, pytest, and `compileall` through uv | Ruff clean; mypy clean; 1 test passed; compilation succeeded | PASS |
| TC-0405 | Architecture config/secret checks plus `npm ci` | Required secret placeholders empty; loopback ports enforced; npm audit reported 0 vulnerabilities | PASS |
| TC-0406 | `npm run validate` | Python dependency boundaries, queue deferral, API base path, event tenant anchor, token references, contrast, and local links accepted | PASS |
| TC-0407 | `npm test --workspace @aria/web` and `npm run lint --workspace @aria/web` | 4 shell tests passed; ESLint completed with zero warnings | PASS |
| TC-0408 | `npm run test:records` | 6 documentation-governance tests passed | PASS |
| TC-0409 | `npm test` and `npm run validate` | 13 automated tests passed; 20 architecture checks passed | PASS |
| TC-0410 | In-app browser DOM/computed-style/console inspection at 375x812 and 1440x900 | `dir=rtl`, `lang=fa`, one H1, main landmark, viewport width equals scroll width, console warnings/errors empty | PASS |

The senior correction for `agentRules: false` and ignored TypeScript build metadata was included before the final root quality-gate run.

## Final Status

**Final status:** PASS
