# Test Report: 0102 Local Preview Publication and Capability

- Date: 2026-10-13
- [Development record](./development.md)

## Environment

Local Windows, Python 3.12 and Node. Scoped DB tests used fresh disposable PostgreSQL 16-alpine,
loopback-only random ports and actual aria_worker login (not DB-owner helper execution or SET ROLE).
The reproducible authority harness applied the full Alembic chain through 0040. Test containers
were deleted afterward; existing databases were untouched. General `npm test` omits DB env and
its skipped integrations are reported separately. No 0102 Browser/Hosted acceptance was performed.

## Test Cases

| ID | Scenario | Expected |
|---|---|---|
| TC-10201 | Derivative determinism/source hash preservation | PASS |
| TC-10202 | Root and nested URL mapping/browser loading | PASS |
| TC-10203 | Command authorization/cross-tenant isolation | PASS |
| TC-10204 | One-time issue, replay, expiry and revoke | PASS |
| TC-10205 | Direct-resource/traversal/Manifest protections | PASS |
| TC-10206 | Content/token/URL leakage-negative and cleanup | PASS |
| TC-10207 | Opaque-origin Browser isolation | PASS |
| TC-10208 | Atomicity, concurrency and controlled recovery | PASS |
| TC-10209 | Reviewed SQL equivalence, role ownership/grants/RLS/locked graph | Static + actual Worker authority subgate PASS |
| TC-10210 | Empty-only rollback, shared Role preservation, legacy downgrade compatibility | PASS; nonempty rejection/data preservation and full PG regression verified |
| TC-10213 | Preready active Job cancellation, terminal result preservation, binding, replay, atomic rollback and Worker finalization race | Focused PostgreSQL PASS; complete regression completion recorded below |
| TC-10214 | Controlled-only queue mapping, app-local Task, exact envelope, no implicit retry, safe outcomes and real Redis delivery | 40-case adapter/transport subgate PASS; complete PostgreSQL-to-browser E2E NOT EVALUATED |

## Execution Results

### Pre-push checkpoint verification — 2026-10-14

Owner explicitly authorizes the current checkpoint Commit/Push, not release or Hosted activation.
Fresh `npm test` PASS: API 585 passed / 246 skipped, Worker 356 passed / 55 skipped; all Node,
Renderer and Web suites PASS. `npm run validate` fails solely on PENDING 0102; other 22 checks
PASS. `git diff --check` passes; reviewed changed-file names and credential-pattern checks find
no secret file/credential pattern. This is a checkpoint of disclosed incomplete work, not a
completed 0102 acceptance report. Previous dated no-push statements describe their earlier phases.

### Controlled queue transport continuation — 2026-10-13

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| New queue contract-first collection | ERROR: adapters absent | RED before implementation |
| First focused adapter/configuration regression | 34 passed | Initial 24 new contracts + 10 existing cases; additional malformed-outcome tests then added |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/e2e/run-preview-queue-controlled.ps1` | 40 passed | 27 new contracts, 3 actual Redis/Celery worker cases and 10 existing cases |
| Actual transport modes | success / permanent failure / recoverable failure PASS | Each delivers identifiers only, invokes the synthetic executor once, persists no result, and schedules no consumer retry |
| General publisher and ordinary Celery app | Preview unavailable | Explicit controlled adapter/registration required; no shared/global task leak or general bootstrap activation |
| Secret/content diagnostic sentinels | No leak | Raw exceptions, invalid fields and non-contract outcome data rejected with existing bounded codes |
| Worker lint/typecheck | PASS; 97 source files | No dependency/framework migration or SQL/privilege change |
| Owned Redis cleanup | PASS | Removed only the container and queues created for this run; existing services untouched |
| Final `npm test`, no DB/broker env | PASS; API 585 passed / 246 skipped; Worker 356 passed / 55 skipped; Node/Renderer/Web PASS | New three Redis skips separately executed above; remaining integration skips still disclosed |
| Final `npm run validate` | FAIL only on PENDING 0102; other 22 checks PASS | Complete SQL/Outbox/Worker/HTTP/browser E2E gate not weakened |

The live task uses a synthetic executor double: these three cases prove **broker/task transport**,
not SQL domain effects, checkpoint recovery, hard-kill redelivery or browser security. Test-only
visibility/wait/shutdown values introduce no new product defaults. The pinned existing Redis image
and Celery version were reused. General npm and final validation evidence follow the last run.
Final queue-only regression evidence is recorded above. The prior PostgreSQL counts remain
historical evidence for unchanged SQL/Application boundaries, not a new queue/domain E2E claim.

### Preready revoke/cancel continuation — 2026-10-13

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| New contract-first PostgreSQL run, before revoke change | 6 failed / 59 passed | RED: active Jobs remained queued/running, wrong payload accepted, and Revoke did not wait for Job lock |
| Fresh focused authority run after implementation | 65 API + 12 Worker passed | Existing helper executions use actual aria_worker; authenticated command cancels only active exact-bound Jobs |
| Deterministic Worker-lock-first race | PASS | Observed blocked Revoke via `pg_blocking_pids`, then Worker finalization commits before Revoke; succeeded Job preserved, Publication revoked |
| Revoke-first in-flight path | PASS | Same Job cancelled, finalization and subsequent claim denied with SQLSTATE 42501; existing session can release its claim |
| Atomic rollback after flushed idempotency persistence | PASS | Publication, Job and idempotency all rolled back; explicit same-key command succeeds afterward |
| queued/running/failed/succeeded cases and replay | PASS | Only active preready Job cancelled; completion time and failure/success result remain stable on replay |
| API lint/typecheck | PASS; 207 source files | No new migration, SQL helper, grant, RLS policy or general Worker behavior |
| Required `npm test` | PASS; API 585 passed / 246 skipped; Worker 329 passed / 52 skipped; Node/Renderer/Web PASS | Seven added PostgreSQL cases are executed separately, not treated as passed skips |
| `npm run validate` | FAIL only on PENDING 0102; other 22 checks PASS | Queue/HTTP/browser acceptance remains open; gate unchanged |

Both reviewed SQL SHA-256 values remain unchanged. Complete PostgreSQL regression and owned
resource cleanup PASS: focused 65 API + 12 Worker; complete API **830 passed / 1 skipped**,
Worker **379 passed / 2 skipped**. The disposable container and task-owned temporary directories
were removed; existing services/data were preserved. No migration/helper/grant/RLS changes,
Hosted activity or commit/push occurred. This section supersedes the earlier open
preready disposition, not the independent queue/HTTP/browser or Hosted gates.

### Approved fifth-helper execution — 2026-10-13

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| Contract-first PostgreSQL RED, before 0041 | 6 failed / 52 passed; helper undefined | Expected incomplete gate; negative tests were subsequently strengthened to exact SQLSTATE 42501 |
| Contract-first Worker RED | 12 failed / 20 passed | New failure port/result handling absent before implementation |
| First 0041 local authority run | 58 API + 6 earlier Worker cases passed | Helper compiles/applies under actual role; no full/browser acceptance |
| Expanded gate intermediate run | 58 API passed; Worker collection FAILED due new test indentation | Implementation/test defect recorded; corrected only scoped test and whole gate rerun |
| Fresh complete rerun after correction | 58 API + 12 Worker cases passed | Owned failure, immutable preservation, rollback/recovery and existing access/revoke paths verified across three project types |
| Focused Worker failure/store tests | 32 passed | Known permanent vs recoverable distinction; same-session helper, allowlist and session discard |
| Static source/security/equivalence tests | 10 passed | Original four-helper snapshot remains unchanged; added migration matches fifth review SQL exactly |
| API/Worker lint/types + strict 0041 mypy | PASS | 207 API / 95 Worker / 1 migration source files |
| `npm test`, no DB env | PASS; API 585 passed / 239 skipped; Worker 329 passed / 52 skipped; Node/Renderer/Web PASS | Added 22 API + 6 Worker integration skips explicitly executed separately; no silent skip-as-PASS |

Both historical snapshots are immutable. Failure-helper review SHA-256:
`c0fe5111c40859a7e2d4d1d6e85f4be611c5633ddf922b08fdf9592b63064d09`.
0041 removes only its own function and added owner read-column on downgrade, preserving populated
Preview metadata and existing helpers. Failure commit injection tests actual precommit rollback;
they do not claim ambiguous network-commit or paid-provider recovery.
Full PostgreSQL regression completion and final cleanup are recorded after the last run below.

| Final command / evidence | Actual result | Interpretation |
|---|---|---|
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/e2e/run-preview-authority-controlled.ps1 -FullRegression` | PASS: focused 58 API + 12 Worker; complete API 823 passed / 1 skipped; Worker 379 passed / 2 skipped | Fresh isolated PostgreSQL; suites sequential; no skip-as-PASS and no Hosted/browser acceptance |
| Final review snapshot hashes | Original migration review `916b2b...e3b6`; failure review `c0fe5111...4d09`, unchanged | Historical design headers do not describe current activation state; active SQL is independently embedded |
| Final `npm run validate` | FAIL only on PENDING 0102, other 22 checks PASS | Remaining queue/HTTP/Browser/preready-revoke gates stay open |
| Exact container/temp cleanup | PASS | Removed only resources created by this invocation; existing local services/data preserved |

### Historical read-only access, before fifth-helper execution approval — 2026-10-13

Missing access/resolver modules produced RED collection before their implementations. Scoped
formatting/lint defects were corrected without touching unrelated files or weakening tests.

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| `test_preview_access.py` + `test_preview_access_store.py` | 32 passed | Exact Host/version, per-resource GET/HEAD authorization, private Manifest/file hash, uniform denial, no-CORS/CSP metadata and synthetic configuration guards |
| Fresh authority harness after adding read assertions | 36 API + 6 Worker passed | Actual aria_worker resolution/GET/HEAD/revocation behavior; not an HTTP listener/browser test |
| Failure-helper SQL review file | DESIGN ONLY / UNAPPLIED / PENDING OWNER SOURCE REVIEW | No SQL execution, migration/grant/RLS or active helper change; no DB PASS claimed |
| Worker lint / strict typecheck | PASS / PASS (95 source files) | Only scoped access adapters and tests added |
| `npm test` final continuation | PASS; API 585 passed / 217 skipped; Worker 322 passed / 46 skipped; Node/Renderer/Web PASS | Current read-only units executed; the six PostgreSQL cases were separately executed above |
| `npm run validate` final continuation | FAIL only on PENDING 0102; other 22 checks PASS | No completion/security gate weakened |
| Snapshot/diff/cleanup | PASS | Original review hash unchanged; generated container/temp directories removed; no commit/push or Hosted operation |

The original reviewed SQL hash is still
`916b2babe10e57b05d9b5fd19e4d127fae54a5c71182e757470d6333a4ece3b6`.
At this earlier phase no new Helper or column privilege had been applied. Subsequent approved
0041 execution and privilege/replay/rollback results appear above; namespace/table ownership
and direct Worker table privileges remain unchanged.

### Worker continuation — 2026-10-13

Contract-first RED collection was observed for missing publication runtime, local storage,
canonical validator and DB adapter before their respective implementations. Intermediate lint
failures were corrected only in scoped files and rechecked; no gate was weakened.

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| Focused seven Worker Preview test files | 79 passed | Existing 32 plus 47 new runtime/storage/validation/session cases |
| Disposable authority harness rerun | 36 API authority/downgrade + 6 Worker copy/recovery passed | Actual aria_worker login; ready state + source bytes + replay verified |
| Worker copy failure on each of three real Project Type bundles | PASS | Job remains recoverable, zero ready publication, claim released; explicit same-ID recovery succeeds |
| Real local destination + reused canonical validators, three bundles | PASS | No Renderer/Provider invocation during publication; source bytes unchanged |
| Fixed-helper session unit tests | 9 passed | Commit/claim failure, cancellation and release cleanup invalidates connection; wrong-event release denied |
| Canonical closed-property rejection | PASS | Unknown root/page/section/content fields and duplicate identity rejected without source repair |
| Local immutable file race | PASS | One complete winner; mismatch rejected; temporary preparation files cleaned |
| `npm run lint:worker` / `npm run typecheck:worker` final | PASS / PASS (93 source files) | No migration/grant/RLS or prior adapter change |
| `npm test` final, no DB env | PASS; API 585 passed / 217 skipped; Worker 290 passed / 46 skipped; Node/Renderer/Web PASS | Six new integration cases skipped here, but explicitly executed in the isolated harness above |
| `npm run validate` final | FAIL only on PENDING 0102; other 22 checks PASS | Incomplete gate preserved |
| Task cleanup and working tree inspection | PASS | Exact created PostgreSQL container/temp directories removed; previous containers and local changes preserved; no commit/push |

These tests do not cover broker delivery, public HTTP capability reads, browser isolation or
operational permanent-failure Job disposition. No full 0102 PASS is claimed.

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| Initial Worker/API contract-first collection | Missing preview modules caused collection failure | RED before implementation |
| Initial real synthetic bundle transformation | landing/portfolio image preload rejected; corporate passed | Closed policy enforced; required owner decision |
| Focused Worker preview tests after approved removal | 32 passed, including three real bundle Project Types | Transformer/Manifest unit proof, not Browser/DB acceptance |
| `node scripts/run-uv.mjs --project apps/api run pytest -q --tb=short apps/api/tests/test_preview_publication_service.py` | 27 passed | Command boundary/delegation and safe diagnostic tests; no DB effects |
| `node --test scripts/test/preview-publication-review.test.js` | 9/9 passed, including active SQL equivalence, guarded rollback and safe Role reuse | Static checks only; real execution evidence below |
| Fresh Alembic upgrade through `0040_preview_publication` | PASS on new disposable PostgreSQL | Reviewed SQL compiles/applies; no Hosted migration |
| Historical legacy downgrade probe before approval | 1 FAILED: 0040 rejected undefined downgrade | Contract-first history; superseded by approved implementation/rerun, not erased |
| Initial approved rollback implementation run | 2 passed / 4 failed due to fixed Outbox policy name mismatch | Implementation defect corrected; no guard bypass or skip |
| Focused guarded migration tests + old legacy downgrade | 6 passed | Nonempty preservation, round-trip, unsafe Role rejection, two-DB preservation/reuse and old failure fixed |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tests/e2e/run-preview-authority-controlled.ps1` latest | 36 passed; DB_AUTHORITY=PASS; GUARDED_DOWNGRADE=PASS; FULL_PUBLISHING_BROWSER=NOT_EVALUATED | Fresh PostgreSQL, actual Worker login, rollback/capability proof and exact container cleanup |
| First full API PostgreSQL run | 800 passed / 1 failed / 1 skipped; WinError 64 during SSL connection | FAILED environmental run, not PASS; diagnostic case and full suite explicitly rerun |
| Full API PostgreSQL rerun, local `ssl=disable` and task temp dir | 801 passed / 1 skipped | PASS executed API suite; skip disclosed; only disposable loopback transport changed |
| First full Worker PostgreSQL run | 277 passed / 3 failed / 2 skipped / 1 error | New claim FK missing from test cleanup + Windows temp path issue; recorded failures |
| Full Worker PostgreSQL rerun with FK-consistent fixture + task temp dir | 281 passed / 2 skipped | PASS executed Worker suite; no runtime privilege, automatic retry or deletion policy change |
| `npm run lint:api` / `npm run lint:worker` | PASS / PASS | Scoped final lint corrections applied; no unrelated formatter restore |
| `npm run typecheck:api` / `npm run typecheck:worker` | PASS: 207 / 89 source files | Shared Application included in normal repo check |
| Strict mypy with new service test + API/shared modules | PASS: 206 source files | Test double and Application types agree; no runtime security acceptance claim |
| Migration strict mypy | PASS: 1 source file | Additional check beyond normal Application typecheck |
| `npm test` latest rerun, no DB env | PASS; API 585 passed / 217 skipped; Worker 243 passed / 40 skipped; Node/Renderer/Web suites passed | General integration skips kept explicit; separate complete PG results above |
| `npm run validate` | FAIL: 0102 test report final status is not PASS; other 22 checks passed | Expected incomplete-increment gate retained, not bypassed |
| `git diff --check` | PASS (line-ending warnings only) | Existing 0098–0101 work preserved |

The immutable review SQL hash remains unchanged; executable statements are embedded in active
Alembic 0040 without a docs runtime dependency. The real-role gate includes direct SELECT/INSERT/
UPDATE/DELETE denial on all three new tables, owner flags/table ownership, PUBLIC/Data API EXECUTE
denial, wrong-tenant Job/Event pairs, composite source FK, active Job uniqueness, hard-delete and
identity protection, concurrent claim, exact release, atomic finalization rollback, backend death
reclaim, revoke while publishing, issue conflict/replay/concurrency, synchronous expiry and hash-only
resolution. These are SQL/metadata tests, not complete Artifact files/storage/browser acceptance.
Test-only expiry/key/token markers introduce no product defaults or customer data.
The latest 36-case harness rerun included composite FK and guarded rollback checks and cleaned its
container. The earlier manually created test container was identified by exact container ID and
removed as well. No existing local PostgreSQL, Redis, other project containers or data were removed.
Role cleanup is transactional and column-ACL-specific. Shared catalog checks preserve a Role used
outside the current database; preserved Role attributes are verified on re-upgrade. No CASCADE,
DROP OWNED, populated-table removal, broad Worker grant or change to runtime SQL helpers was used.

### Not executed / not claimed

- No claim of zero skips or external/Hosted integration acceptance; 1 API + 2 Worker skips remain.
- Full revoke-vs-HTTP-file delivery ordering; only SQL/in-flight finalization is covered so far.
- Source-profile Browser loading and 0102 capability-bound isolation gate.
- Concrete PostgreSQL/Outbox/Worker queue composition; adapter and real Redis transport now pass.
- Capability-aware HTTP file reads and full source-profile Browser gate; local copy/storage
  preparation subgate alone now passed under actual Worker login.
- Hosted/customer content, real Provider, security architecture redesign, commit or push.

The complete [historical SQL review snapshot](./migration-review.sql) stays outside the Alembic
chain as a review artifact. Its original NOT APPLIED comment is historical: approved executable
statements were applied via active 0040 solely to disposable local test databases. See the current
[authority review/evidence](./database-security-review.md). Full 0102 remains PENDING.

## Final Status

**Final status:** PENDING
