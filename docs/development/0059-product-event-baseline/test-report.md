# Test Report: 0059 — Product Event Baseline

- **Status:** PASS
- **Increment:** S1-L01
- **Date:** 2026-09-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js repository pin 24.11.1
- Python 3.12 repository pin via workspace UV runner
- Local PostgreSQL 16 Docker service for integration tests
- Synthetic identifiers and content only; no customer data or external analytics provider

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-5901 | REQ-5901 | Parse Product Analytics JSON schema | Required envelope, category and schema version are frozen | PASS |
| TC-5902 | REQ-5901 | Inspect Web envelope | Event ID, timestamps, account and nullable pre-project context are present | PASS |
| TC-5903 | REQ-5902 | Inspect server outcome instrumentation | All nine approved outcome names are emitted through the helper | PASS |
| TC-5904 | REQ-5902 | Inspect client event union | Only five separate interaction names are client-owned | PASS |
| TC-5905 | REQ-5903 | Unknown property/enum/UUID/version input | Contract rejects the event before emission | PASS |
| TC-5906 | REQ-5903 | Schema safe property vocabulary | Content-bearing properties are absent and additional properties are rejected | PASS |
| TC-5907 | REQ-5904 | Same logical event emitted twice | Deterministic ID is identical and logger writes one line | PASS |
| TC-5908 | REQ-5904 | Different outcome names for same logical ID | IDs remain distinct and UUID-shaped | PASS |
| TC-5909 | REQ-5905 | Context/Gap/Requirement/Scope outcome cardinality | Instrumentation is placed per persisted item, batch, Draft and version | PASS |
| TC-5910 | REQ-5906 | Pre-project type selection | Interaction remains separate and serializes `project_id=null` | PASS |
| TC-5911 | REQ-5907 | Business failure before commit | Outcome emission is not reached; successful outcomes follow commit | PASS |
| TC-5912 | REQ-5908 | Negative leakage static scan | No prompt, raw text, content, title, description, JWT or email in product event paths | PASS |
| TC-5913 | REQ-5908 | Existing regression suites | Existing Project, Context, Requirement, Gap, Scope and K05 contracts remain green | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| `node --test scripts/test/product-analytics-contract.test.js` | 3 passed | PASS |
| `npm test --workspace @aria/web` | 35 passed | PASS |
| `npm run test:api` with workspace UV cache | 369 passed, 123 skipped | PASS |
| `node --test scripts/test/scope-version-contract.test.js` | 5 passed | PASS |
| `npm run lint:api` with workspace UV cache | All checks passed | PASS |
| `npm run typecheck:api` with workspace UV cache | No issues in 141 source files | PASS |
| `npm test` with local PostgreSQL and workspace UV cache | 164 contract + 35 eval + 35 web + 493 API + 57 worker tests passed | PASS |
| `npm run build` with workspace UV cache | Web build and API/Worker compile passed | PASS |
| `npm run validate` | Architecture and development-record checks passed | PASS |
| `npm run scan:secrets` | No publishable-file findings | PASS |
| `git diff --check` | No whitespace errors | PASS |

## Senior Verification

The complete suite and focused negative tests pass. Review covered event ownership, envelope
versioning, stable-ID deduplication, allowlist enforcement, post-commit outcome placement, client
interaction separation and content-safe logging.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
