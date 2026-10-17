# Test Report: 0032 Text Parser Contract

[Development record](./development.md)

## Environment

- Windows 11 host, repository worktree `staging-migrations`
- Python 3.12 Worker environment managed by `uv`
- Node.js/npm repository toolchain
- Pure parser unit tests; no Queue, database, storage or provider runtime was used.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-3201 | Contract | Inspect parser boundary | Worker Application exposes provider-neutral `TextParser` with `parse(source_version)` |
| TC-3202 | Unit | CRLF/CR, NFC, tabs, Unicode spaces and repeated spaces | Canonical text follows the approved deterministic order |
| TC-3203 | Unit | Internal blank lines, line order, ZWNJ/ZWJ and linguistic characters | Protected content remains unchanged |
| TC-3204 | Unit | Input that becomes whitespace-only after normalization | Parser rejects with `EmptyCanonicalTextError` |
| TC-3205 | Scope/Architecture | Inspect hashing and dependency boundaries | No hash algorithm, linguistic map, persistence, Queue or provider behavior is invented |
| TC-3206 | Worker regression | Run all Worker tests | Existing Worker runtime and idempotency behavior remains green |
| TC-3207 | Quality | Run lint, typecheck, build and validation | All repository quality gates pass |

## Execution Results

| ID | Command | Actual | Status |
|---|---|---|---|
| TC-3201, TC-3205 | `node --test scripts/test/text-parser-contract.test.js` | 2 contract tests passed | PASS |
| TC-3202–TC-3204 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests/test_context_parser.py` | 4 tests passed | PASS |
| TC-3206 | `node scripts/run-uv.mjs --project apps/worker run pytest -q apps/worker/tests` | 30 tests passed | PASS |
| TC-3207 (focused) | Worker Ruff and Mypy commands | Ruff passed; mypy reported no issues in 11 source files | PASS |
| TC-3206 (repository) | `npm test` | Records 6, contracts 88, Web 18, API 149 passed/33 skipped, Worker 30 passed | PASS |
| TC-3207 (repository) | `npm run lint`; `npm run typecheck`; `npm run build`; `npm run validate` | Web/API/Worker lint, strict type checks and builds passed; architecture validation passed 22/22 | PASS |

## Notes

- The first unit expectation incorrectly assumed NFC would preserve a decomposed Arabic
  letter-plus-mark sequence and that Arabic `ك` would become Persian `ک`; both were corrected to
  the approved NFC-only, non-linguistic contract.
- The first contract assertion crossed a Markdown line break; it was corrected to assert the same
  phrase with whitespace tolerance.
- Warnings were limited to the existing Windows pytest cache-permission warning.
- Full repository gates passed. The only output warnings were the existing Starlette/httpx
  deprecation and Windows pytest cache-permission warnings.

## Final Status

**Final status:** PASS
