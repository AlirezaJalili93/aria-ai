# Test Report: 0062 — TXT Upload Foundation

- **Status:** PASS
- **Increment:** S1-D03
- **Date:** 2026-09-13
- [Development record](./development.md)

## Environment

Windows / PowerShell workspace; repository-pinned Node.js and Python 3.12/uv; Docker Desktop
PostgreSQL 16 on localhost for integration evidence. No hosted Storage credentials or secrets were
used or recorded.

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-6201 | REQ-6201 | Existing JSON text request | Existing behavior remains compatible and gains relative status URL | PASS |
| TC-6202 | REQ-6201 | Exact and extra/wrong multipart parts | Exact request accepted; extra/wrong parts produce 422 | PASS |
| TC-6203 | REQ-6202 | Extension, MIME and strict UTF-8 | Only exact `.txt` plus normalized `text/plain` and valid UTF-8 pass | PASS |
| TC-6204 | REQ-6202 | NFC filename, path/dot/control attacks, executable-looking text | Safe basename passes; attacks fail; plain documentation is not keyword-blocked | PASS |
| TC-6205 | REQ-6203 | Exact/over byte and character bounds, empty/control content | Exact limits pass and each violation returns its approved failure | PASS |
| TC-6206 | REQ-6204 | Architecture imports and adapter request | Provider SDK only in Infrastructure; private PutObject contains no ACL/public/upsert | PASS |
| TC-6207 | REQ-6204 | Generated storage key and persistence | Exact environment/tenant/project/source/version path stored without filename | PASS |
| TC-6208 | REQ-6205 | Same key/bytes, changed display filename and changed bytes | Exact replay without second effect; display name ignored; changed bytes conflict | PASS |
| TC-6209 | REQ-6206 | Storage fails before DB writes | No Source/Version/Job/Outbox commit | PASS |
| TC-6210 | REQ-6206 | DB commit fails; compensation succeeds/fails | Delete attempted; cleanup failure emits critical discoverable incident | PASS |
| TC-6211 | REQ-6207 | Adapter configuration | SigV4/path-style, 5s/30s and total one attempt; no hidden retry/upsert | PASS |
| TC-6212 | REQ-6208 | Success envelope | 202 contains job ID and relative status URL | PASS |
| TC-6213 | REQ-6208 | Type/size/validation/storage failures | 415/413/422/503 and stable codes/retryable semantics | PASS |
| TC-6214 | REQ-6209 | Flag omitted/off and incomplete enabled config | Upload is 403 fail-closed; enabled runtime requires complete Storage config | PASS |
| TC-6215 | REQ-6210 | Inspect success/failure/compensation logs | Only approved bounded metadata; no filename/content/key/URL/credential | PASS |
| TC-6216 | REQ-6211 | Contract/static scope review | No PDF/DOCX/parser/public URL/automatic retry activation | PASS |
| TC-6217 | REQ-6205 | Concurrent same-key upload against PostgreSQL | Both callers receive one result; one object and one Source/Version/Job/Outbox persist | PASS |

## Execution Results

- `npm run lint` — PASS; Web ESLint plus API/Worker Ruff.
- `npm run typecheck` — PASS; Web TypeScript, API mypy (147 files) and Worker mypy
  (28 files).
- `node --test scripts/test/text-context-api-contract.test.js` — PASS; 4/4.
- Focused TXT upload/API/config suite — PASS; 49/49.
- Real PostgreSQL TXT upload concurrency suite — PASS; 2/2.
- `npm run test:ci` — PASS; 174/174.
- `npm run test:eval` — PASS; 35/35.
- `npm run test:web` — PASS; 35/35.
- `npm run test:api` with `TEST_DATABASE_URL` — PASS; 530/530.
- `npm run test:worker` — PASS; 58/58.
- `npm test` final repository gate — PASS; records 6/6, CI 174/174, Eval 35/35, Web
  35/35, API 530/530 and Worker 58/58.
- `npm run build` — PASS; Next.js production build plus API/Worker byte compilation.
- `npm run validate` — PASS; 23/23 architecture and documentation checks.
- `npm run scan:secrets` — PASS; 751 publishable text files inspected.
- Post-remediation `npm audit --json` — PASS; 0 vulnerabilities across 435 dependencies.
- `npm run scan:dependencies` — npm audit PASS; Python audit NOT RUN because PyPI terminated
  TLS while downloading the pinned `pip-audit==2.10.1` tool after repeated sandbox and approved
  network retries. No Python vulnerability PASS is claimed.
- `git diff --check` — PASS; no whitespace errors (Git only reported expected Windows LF/CRLF
  conversion notices).

Non-failing warnings: Starlette reported its documented TestClient/httpx deprecation, and pytest
could not write cache metadata in the Worktree. Neither warning changed test execution or results.

## Final Status

**Final status:** PASS — all functional, contract, database, architecture and required repository
gates passed. Hosted bucket/credential evidence remains intentionally deferred to S1-L04, and the
unavailable Python vulnerability audit is explicitly retained as a network/tooling follow-up.
