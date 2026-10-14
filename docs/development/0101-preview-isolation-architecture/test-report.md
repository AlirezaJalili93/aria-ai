# Test Report: 0101 Preview Isolation Architecture

- Increment: `0101-preview-isolation-architecture`
- Date: 2026-10-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell
- Node.js/npm constrained by the repository
- Google Chrome headless with Browser-level CDP and OOPIF target sessions
- Three synthetic loopback sites using distinct registrable test domains
- Synthetic ArtifactVersion only; no Provider, customer content or Hosted runtime
- Task-specific pytest temp directory inside the worktree, removed after the run

## Commands

```powershell
npm run test:preview-isolation
npm run proof:preview-isolation
npm run lint
npm run typecheck
npm run build
npm test
npm run validate
git diff --check
```

## Test Cases

| ID | Expected | Actual | Status |
|---|---|---|---|
| TC-10101 | Separate registrable sites and exact immutable version namespace | Contract test passed | PASS |
| TC-10102 | Opaque sandbox has only `allow-scripts`; no bridge | Contract test passed | PASS |
| TC-10103 | CSP hashes exact bytes and sends `frame-ancestors` by header | Contract test passed | PASS |
| TC-10104 | Approved CORP candidate loads only exact Manifest resources without CORS | JS/CSS/image loaded; ACAO absent | PASS |
| TC-10105 | System Font only; font files, `@font-face`, preload and network requests absent | `system-ui` rendered; zero Font requests | PASS |
| TC-10106 | Core state, API, form, popup, download, top navigation and unauthorized embed denied | All OOPIF negative assertions passed | PASS |
| TC-10107 | Disposable cleanup and no sensitive/customer data | Browser profile and test temp cleanup completed | PASS |
| TC-10108 | Repository quality gates | Full test, lint, typecheck, build and validation passed | PASS |

## Execution Results

- 0101 Contract suite: PASS, 5 tests.
- Real-Chromium proof: PASS. Universal `CORP: same-origin` remained incompatible as expected;
  approved manifest-bound `CORP: cross-origin` passed every resource and isolation assertion.
- Font policy: PASS; `font-src 'none'`, System Font rendering and zero Font requests verified.
- `npm run lint`: PASS.
- `npm run typecheck`: PASS; API 203 and Worker 87 source files.
- `npm run build`: PASS for Renderer, Web, API and Worker.
- `npm test`: PASS; API `558 passed, 182 skipped`; Worker `211 passed, 40 skipped`; all Node,
  Renderer and Web suites passed.
- Skipped environment-gated tests are recorded as skipped, not PASS.
- `npm run validate`: PASS after final documentation sync.
- `git diff --check`: PASS after final documentation sync.

## Final Status

**Final status:** PASS
