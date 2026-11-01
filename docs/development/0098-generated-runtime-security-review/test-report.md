# Test Report: 0098 Generated Runtime Security Review

- Increment: `0098-generated-runtime-security-review`
- Date: 2026-10-11
- [Development record](./development.md)
- [Security evidence](./security-evidence.json)

## Environment

- Windows / PowerShell
- Node.js 24 / npm 11
- Local Chrome or Edge headless through Chrome DevTools Protocol
- Disposable OS temporary directories outside the repository

## Commands

```powershell
npm run test:generated-runtime-security
npm run proof:generated-runtime-security
npm test
npm run build
npm run validate
git diff --check
```

## Test Cases

| ID | Expected | Actual | Status |
|---|---|---|---|
| TC-9801 | Exact 0097 candidate and reproducibility identities | Exact Prototype writer reused; suite/Registry/schema/fixture versions, tarball hashes, lock hashes and Artifact hashes recorded | PASS |
| TC-9802 | Adversarial corpus covers inert and rejected boundaries | Eight versioned cases: one inert payload and seven invalid/security mutations | PASS |
| TC-9803 | Browser observes/blocks unauthorized runtime requests and submissions | CDP observed all requests; remote control probe blocked; no form or external-navigation effect | PASS |
| TC-9804 | Read-only server, dependency policy and Artifact scans fail closed | POST control returned `405`; lifecycle scripts disabled; High/Critical audit and scans clean | PASS |
| TC-9805 | Evidence separates synthetic Gates from Production Preview | Static Artifact and Synthetic Runtime are `PASS`; Production Preview is `NOT_EVALUATED` | PASS |
| TC-9806 | All candidate installs/audits/builds/static scans pass | Four of four candidates passed with distinct recorded Artifact hashes | PASS |
| TC-9807 | Application rejects seven invalid mutations and preserves inert text | Nine Python contract tests passed | PASS |
| TC-9808 | Chromium navigates all Pages with zero forbidden runtime effect | Ten Page executions; zero forbidden requests, WebSockets, exceptions or submissions | PASS |
| TC-9809 | Temp source, profile, dependencies and Artifact are removed | Runner reported `cleanup.completed=true` after the Gate | PASS |
| TC-9810 | Repository regression Gates pass | Lint, typecheck, `npm test` and full build passed; final validate and diff check recorded below | PASS |

## Execution Results

- `npm run test:generated-runtime-security`: PASS, 5/5 Node contract tests.
- `node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests/test_generated_runtime_security.py`: PASS, 9 tests.
- `npm run proof:generated-runtime-security`: PASS for four candidates and ten Page executions.
- Renderer tarball SHA-256: `3ea4ad8bce6dcdd1a5de3e4111cc4c03a021ebc030c63f0764722bd4c7bd4d9f`.
- Design-token tarball SHA-256: `cdb59f9dc6d33412ef0a9e2736833f871ac17bce6d4fcb74bb047a5e9b858383`.
- Artifact SHA-256 values: landing `a9a4323c4d1f870cb756df0461530db904f4e7b705b8c6313dab48ab37b72250`,
  adversarial landing `6f1a1829bc8ec9c62e92c0019839eba552426376cc5fbf6531f4e68727e71cd6`,
  corporate `5316ab0d5617a3285d5d7d8382ccfe9d07f011e3de3d9fcb3fc2b06cf111bc5a`,
  portfolio `c63c88c3fa438ec562923d6b98c317a95876c13ce39e187e9533e65ccbf56929`.
- `npm run lint`: PASS.
- `npm run typecheck`: PASS (194 API and 81 Worker source files).
- `npm test`: PASS; API `552 passed, 175 skipped`, Worker `208 passed, 36 skipped`, plus all Node suites.
- `npm run build`: PASS for Renderer, Web, API and Worker.
- The skipped Python tests remain environment-gated and are not represented as executed PASS cases.
- Production Preview Security was not evaluated by this synthetic/local increment.

## Final Status

**Final status:** PASS
