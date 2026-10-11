# Test Report: 0097 Controlled Generation Exportability

- Increment: `0097-controlled-generation-exportability`
- Date: 2026-10-10
- [Development record](./development.md)
- [Clean-room evidence](./clean-room-evidence.json)

## Environment

- Windows / PowerShell
- Node.js `v24.11.1`
- npm `11.6.2`
- Next.js clean-room candidate `16.4.0`
- React / React DOM `19.2.8`
- OS temporary clean-room directories outside the repository

## Commands

```powershell
npm run test:generation-exportability
npm run proof:generation-exportability
npm test
npm run build
npm run validate
git diff --check
```

## Test Cases

| ID | Expected | Actual | Status |
|---|---|---|---|
| TC-9701 | Static-export config and only local vendored tarball dependencies | Exact config/dependencies verified | PASS |
| TC-9702 | One fixed wrapper per canonical Page; no AST-generated executable source | All wrappers generated from bounded template | PASS |
| TC-9703 | No remote/server/runtime surface in generated source | Source scan clean | PASS |
| TC-9704 | Unsafe/duplicate paths rejected and temp cleanup guaranteed | Negative tests and `finally` cleanup pass | PASS |
| TC-9705 | Candidate lockfiles contain no Workspace, parent or absolute repository dependency | All three lockfiles portable | PASS |
| TC-9706 | Landing/corporate/portfolio independently install and build | 3/3 `npm ci` and `next build` pass | PASS |
| TC-9707 | Static output serves all Pages, uses local Assets, contains no submit/external active resource/secret | 7/7 Pages served; scans clean | PASS |
| TC-9708 | Candidate dependency audit has no high/critical blocker | All three report zero vulnerabilities at every severity | PASS |
| TC-9709 | Tarball versions/hashes and bounded results retained; package/build output removed | Evidence retained and cleanup=`completed` | PASS |
| TC-9710 | Repository regression gates | `npm test`, `npm run build` and `npm run validate` pass | PASS |

## Clean-room Results

| Project Type | Pages | Install | Audit | Build | Static Serve |
|---|---|---|---|---|---|
| landing | `/`, `/contact` | PASS | PASS (0) | PASS | PASS |
| corporate | `/`, `/services`, `/contact` | PASS | PASS (0) | PASS | PASS |
| portfolio | `/`, `/work`, `/contact` | PASS | PASS (0) | PASS | PASS |

Tarball SHA-256:

- `@aria/generation-renderer@0.1.0`: `3ea4ad8bce6dcdd1a5de3e4111cc4c03a021ebc030c63f0764722bd4c7bd4d9f`
- `@aria/design-tokens@0.1.0`: `cdb59f9dc6d33412ef0a9e2736833f871ac17bce6d4fcb74bb047a5e9b858383`

The output scan found 24 URL-like literals in framework/library bundles and recorded a bounded
sample. None were active external HTML/CSS references. No secret marker was found.

## Failure/Recovery Evidence

- The first run rejected `/synthetic-assets/` because ADR-083 permits only
  `/generation-fixtures/`; the implementation reused the narrower existing allowlist.
- The next harness run exposed an extensionless static-route mapping defect; the local server now
  maps `/path` and `/path/` to `path/index.html`.
- The dependency Gate rejected Next.js `16.3.5` due to a current Critical advisory. Candidate
  `16.4.0` subsequently passed with zero audit findings.

## Execution Results

- `npm run test:generation-exportability`: 5/5 contract tests passed.
- `npm run proof:generation-exportability`: all three clean-room candidates installed, audited,
  built, served and scanned successfully; cleanup completed.
- `npm test`: all enabled repository suites passed, including 213 CI contract tests, 35 Eval
  tests, 47 Web tests, 543 API tests and 208 Worker tests. Environment-dependent coverage remained
  explicitly reported as 175 API and 36 Worker skips rather than being counted as failures or
  silently presented as executed coverage.
- `npm run build`: Renderer TypeScript build, Next.js production build, API compile and Worker
  compile all passed.
- `npm run validate`: architecture and development-record validation passed after this report was
  finalized.
- `git diff --check`: passed with no whitespace errors.

## Final Status

**Final status:** PASS

0097 proves that the controlled canonical AST can be packaged into three independent Next.js
static-export candidates with only local vendored Aria packages and local allowlisted Assets. It
does not authorize Artifact persistence, ExportJob, Hosted Preview, Customer Content or runtime
security acceptance; `SPIKE-F1-05` remains the next independent Gate.
