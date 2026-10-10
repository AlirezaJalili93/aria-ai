# Test Report: 0058 — Scope Version Snapshot

- **Status:** PASS
- **Increment:** S1-K05
- **Date:** 2026-09-12
- [Development record](./development.md)

## Environment

- Windows / PowerShell workspace
- Node.js and Python 3.12 repository pins
- Local PostgreSQL 16 Docker service bound to loopback
- Synthetic Scope payloads only; no customer content or external Provider

## Test Cases

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| TC-5801 | REQ-5801 | Migration/schema inventory | Exact fields, checks, restrictive FKs, unique version and indexes | PASS |
| TC-5802 | REQ-5802 | Current ready Draft | Exact validated Draft deep-copy committed | PASS |
| TC-5803 | REQ-5802 | Missing/stale current Draft | Safe 404 or atomic VERSION_CONFLICT; no write | PASS |
| TC-5804 | REQ-5803 | Open Critical Gap | 422 CRITICAL_GAPS_OPEN; no snapshot | PASS |
| TC-5805 | REQ-5804 | Same JSON with different object-key order | Same canonical bytes/hash | PASS |
| TC-5806 | REQ-5804 | Trace or array order changes | Hash changes; valid prefixed lowercase SHA-256 | PASS |
| TC-5807 | REQ-5805 | New key with same latest snapshot | 409 SCOPE_VERSION_UNCHANGED | PASS |
| TC-5808 | REQ-5806 | Same key and normalized request | Exact original success replay before duplicate detection | PASS |
| TC-5809 | REQ-5806 | Same key with different request | 409 IDEMPOTENCY_CONFLICT | PASS |
| TC-5810 | REQ-5807 | Concurrent freeze | One committed version number; duplicate execution suppressed | PASS |
| TC-5811 | REQ-5808 | DB update/delete attempts | Payload/delete rejected; controlled status projection allowed | PASS |
| TC-5812 | REQ-5809 | Summary/detail collection contract | Summary excludes payload/creator; detail includes exact snapshot | PASS |
| TC-5813 | REQ-5809 | Cross-tenant/missing and mutation route probes | Safe 404; PATCH/DELETE absent | PASS |
| TC-5814 | REQ-5810 | RLS/grant catalog and downgrade/re-upgrade | RLS on, Data API denied, recovery clean | PASS |
| TC-5815 | REQ-5810 | Event source inspection | No snapshot, trace, full hash or customer content emitted | PASS |

## Execution Results

| Command | Actual result | Status |
|---|---|---|
| Focused K05 Python suite with local `TEST_DATABASE_URL` | 15 passed | PASS |
| `node --test scripts/test/scope-version-contract.test.js` | 5 passed | PASS |
| `npm run lint:api` with workspace UV cache | All checks passed | PASS |
| `npm run typecheck:api` with workspace UV cache | No issues in 140 source files | PASS |
| Complete `npm test` with local PostgreSQL | 161 contract + 35 eval + 35 web + 486 API + 57 worker tests passed | PASS |
| Complete `npm run validate` | 22 architecture checks passed after final record completion | PASS |
| `npm run build` with workspace UV cache | Web production build and API/Worker compile passed | PASS |
| `npm run scan:secrets` | Publishable-file scan passed with no findings | PASS |
| `git diff --check` | No whitespace errors | PASS |

## Senior Verification

Complete-suite verification is passing. Focused review has covered canonical hash behavior,
idempotency precedence, concurrency, DB immutability, safe API exposure and tenant isolation.

## Final Status

**Final status:** PASS

**Unapproved assumptions:** None
