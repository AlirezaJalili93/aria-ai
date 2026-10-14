# Test Report: 0102 Local Preview Publication and Capability

- Date: 2026-10-14
- [Development record](./development.md)

## Current Result — 2026-10-14

**Local/Synthetic acceptance PASS.** Final full joined/Browser matrix **12 passed in 293.22s**;
the complete ADR-089 acceptance audit is below. Historical failure/PENDING notes retain their
original stage and are superseded only by this scoped final evidence. No Hosted, Production,
customer, real-Provider, full human UX/WCAG or shared-credential security acceptance is claimed.

### Checkpoint publication — 2026-10-14

Owner "پوش کن" separately authorizes commit/push of these completion files only. The existing
Local/Synthetic evidence is unchanged; npm/validate/secret/diff checks are rerun before publication.
Historical HEAD/no-push statements below describe the preceding development checkpoint, not a
new activation permission. No Hosted/customer/real-Provider or database operation is included.

Final pre-publication verification passed on 2026-10-14: `npm test` (API **592 passed / 246
skipped; Worker **376 passed / 67 skipped; Node/Renderer/Web suites PASS), `npm run validate`
(23/23), `npm run scan:secrets` (1,233 publishable text files), and `git diff --check` (line-ending
warnings only). Skips remain excluded from PASS counts.

Initial pre-push secret scan FAIL: two existing 0086 unit-test credentialed-URL patterns containing
literal dummy passwords. No live secret was found. REQ-10218/TC-10220 removes only those dummy
passwords, preserves both full-URL and opaque credential-marker repr-negative coverage, and does
not change the scanner, runtime, Provider behavior or activate any evaluation. Focused/full checks
are rerun; the initial failure is retained here rather than reported PASS.

## Environment

Local Windows, Python 3.12 and Node. Scoped DB tests used fresh disposable PostgreSQL 16-alpine,
loopback-only random ports and actual aria_worker login (not DB-owner helper execution or SET ROLE).
The latest authority harness applied the full Alembic chain through reviewed 0040/0041. Test containers
were deleted afterward; existing databases were untouched. General `npm test` omits DB env and
its skipped integrations are reported separately. Current Local/Synthetic Browser subgate evidence
is below; no Hosted/customer/Production acceptance was performed.

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
| TC-10211 | Fifth helper's owned-session/live-lock/code allowlist, ACL and atomic failure boundary | Actual aria_worker PostgreSQL PASS |
| TC-10212 | Permanent source failure, failed failure-commit recovery, same-ID copy preparation | Real-bundle Worker PostgreSQL and bounded runtime cases PASS |
| TC-10213 | Preready active Job cancellation, terminal result preservation, binding, replay, atomic rollback and Worker finalization race | Focused PostgreSQL PASS; complete regression completion recorded below |
| TC-10214 | Controlled-only queue mapping, app-local Task, exact envelope, no implicit retry, safe outcomes and real Redis delivery | 40-case adapter/transport subgate PASS; complete PostgreSQL-to-browser E2E NOT EVALUATED |
| TC-10215 | Fixture-allocated real Relay/PostgreSQL/Redis/Worker copy, same-ID recovery and duplicate delivery for three project types | 6 executed cases PASS; authenticated command/HTTP/browser NOT EVALUATED |
| TC-10216 | Real Application Publish/Issue/Revoke, DB membership, idempotency, one-time response and capability access/revocation joined to relay/Worker | 6 command-backed joined + 7 bridge unit cases PASS; JWT/HTTP/browser NOT EVALUATED |
| TC-10217 | Controlled loopback HTTP GET/HEAD, exact raw target/Host, per-resource capability, no diagnostics and revoke/read ordering | 19 HTTP + 21 access cases and actual-role 12-case joined rerun PASS; Browser NOT EVALUATED |
| TC-10218 | Real 0100 derivatives in disposable browser: three types, root/one/two-level pages, native form, frozen isolation and safe cleanup | 12-case joined rerun including three Browser cases PASS; independent 0101 Browser PASS; not full 0102 acceptance |
| TC-10219 | Concurrent same-key second Publish, two capabilities/one ready Representation, all-file equality, no stored token and independent revocation | Final six command-backed joined cases PASS, including three Browser cases |
| TC-10220 | Pre-push legacy test-fixture hygiene without hiding or disabling secret detection | Focused repr/composition and full secret/regression verification recorded below |

## Execution Results

### Two-publication verification and final regressions — 2026-10-14

- First extended full Browser matrix: **11 passed / 1 failed in 360.62s**. The landing Browser
  failed only `zero_unexpected_network`; no raw URL was captured, so its exact destination is
  deliberately not claimed as known. All other cases passed, including real-file reuse and
  independent revoke. This failed run is not converted into a full PASS.
- Closed-counter diagnostic rerun: **3 passed / 9 deselected in 184.49s**, three Browser cases
  only; the failure did not reproduce. The runner explicitly reports full matrix NOT EVALUATED
  when `-BrowserCasesOnly` is selected. No raw destination/content diagnostic was introduced.
- Review also found interception could block the exact harness-created `data:text/plain,synthetic`
  download probe itself. The armed local non-network probe now reaches native Sandbox enforcement;
  all other non-approved requests remain denied/count as unexpected. Three static contracts verify
  exact armed-only classification, malformed/foreign denial and privacy. This is test hygiene,
  not a source-profile/data-URL permission or proof of the earlier failure's exact cause.
- Fresh `run-preview-authority-controlled.ps1 -FullRegression`: **65 API + 12 Worker focused
  cases PASS**, then **837 API passed / 1 skipped; 425 Worker passed / 17 skipped**. The 17 Worker
  skips include 12 joined/Browser and 3 Redis-only tests not supplied by this PG-only runner,
  plus the earlier two disclosed skips. Joined cases are separately executed; skips are never
  passes. The newly owned PostgreSQL container/temp data were removed.
- Initial general `npm test`: API 592/246 skipped; Worker 360/67 skipped/**15 errors** due to
  Windows access denial at the pre-existing default pytest Temp root. No test was weakened or
  that existing folder deleted. Full rerun with an owned workspace-local Temp: **PASS**, API
  **592/246 skipped**, Worker **375/67 skipped**; all Node/Renderer/Web suites PASS. A final rerun
  after the last test-only observer change remains pending below.
- An intermediate scoped lint run failed one line-length check; only that test line was wrapped.
  API/Worker lint and established types now PASS (207 API / 98 Worker source files); Python
  build/compile PASS. Additional legacy global strict diagnostics remain historical, not hidden.
- Independent unchanged 0101 Browser proof: **PASS**, same-origin compatibility=false (expected),
  approved cross-origin/System Font compatibility=true, cleanup=completed. Eighteen static
  Browser/privacy/fixed-SQL contracts PASS. Both immutable SQL review hashes remain unchanged.
- Final full `run-preview-joined-controlled.ps1 -BrowserGate`: **12 PASS in 293.22s**, six
  command-backed reuse/recovery cases plus six fixture baselines, including the three real-bundle
  Browser cases. All Manifest files are identical through two independently issued capabilities;
  second same-key commands race to one outcome, second real Worker finalization reuses unchanged
  files/Manifest, and each revoke is independently effective. Original source files remain intact.
- Final `npm test` after the last observer change, with owned workspace Temp: **PASS**, API
  **592 passed / 246 skipped**, Worker **376 passed / 67 skipped**, all Node/Renderer/Web suites
  PASS. Owned Temp/service/profile cleanup completed; existing four service containers retained.
  Final `npm run validate`: **23/23 PASS** after record finalization; the development-record
  convention was not bypassed or weakened. Diff check PASS with line-ending warnings only;
  owned `.tmp` is empty, all owned profiles/services removed, four earlier containers preserved.
  HEAD remains `a3e3a84`; no commit/push, Hosted/customer or paid-provider execution.

### Final acceptance-matrix audit — 2026-10-14

This maps every ADR-089 detailed acceptance row to executable evidence. Layered failure/rollback
tests are identified as such; they are not a claim of broker-driven process-crash E2E. Historical
PENDING/FAIL entries below retain their original time/scope and are not silently reclassified.

| ADR-089 gate | Executable evidence | Current classification |
|---|---|---|
| Same identity/versions produce identical bytes and Manifest | Worker `test_preview_manifest.py`, `test_preview_delivery.py`; TC-10219 real-file reuse | PASS |
| Source preserved through publication/read/revoke | `test_preview_real_bundle.py`, `test_preview_publication_runtime_postgres.py`, joined snapshot comparison | PASS |
| Root/one/two-level pages retain capability prefix | `test_preview_delivery.py`; Browser `preview_nested_corporate_v1`, eight pages | PASS |
| Two capabilities reuse one Representation/files | TC-10219: concurrent Application Publish, actual Relay/Worker, all Manifest files, independent revoke | PASS |
| Unsupported absolute/protocol-relative/unknown/CSS-escaped fetch | `test_preview_delivery.py` rejection corpus; known canonical root links alone are explicitly remapped | Unit PASS |
| Direct CSS/SVG requires capability | `test_preview_access.py`, `test_preview_http.py`, joined HTTP | PASS |
| Raw/encoded traversal, query/Host/version aliases | `test_preview_delivery.py`, `test_preview_http.py`, `test_preview_access.py` | Unit/HTTP PASS |
| Private Manifest/checkpoints not served | Closed route/Manifest allowlist tests in delivery/access/HTTP suites | PASS |
| Exact import removal/system font/no resource fetch | Real-bundle transform, closed CSS/SVG profile and Browser font/network observations | PASS |
| Concurrent same-key Publish/Issue | TC-10219 concurrent two-process Publish; `test_concurrent_issue_same_key_discloses_exactly_one_token` on real PostgreSQL | PASS |
| One active Job per preparing Representation | `test_active_job_uniqueness_is_database_enforced`; command active-conflict/replay checks | PASS |
| Copy/finalization failure, recovery/restart retain IDs | Real copy-failure recovery; SQL finalization rollback and backend-death reclaim; adapter ambiguous-commit invalidation and runtime unit failures | Layered PASS; no new process-kill/broker-crash claim |
| Revoke versus finalization/read | Actual SQL both race orders; command-backed held-IO/read ordering and independent second-capability revoke | PASS |
| Cross-tenant/tampered graph denied | Authority/failure helper 42501 tests, composite FK, Member ownership and command safe-404 | PASS scoped helper/command path; shared Worker compromise OUT OF SCOPE |
| Real bundles for three Project Types | Original 0100 builder -> validators/transform -> private copy -> HTTP -> disposable Browser | PASS |
| Independent 0101 isolation unchanged | Existing `run-local-proof.mjs` regression; no 0101 source modification | PASS |
| No diagnostic/content/token leakage; cleanup | Captured-pipe bridge, bounded HTTP/parser errors, closed Browser evidence, token-negative private files/command outcomes/operational stream; owned-resource cleanup | PASS |

The supported 0100 HTML/CSS/SVG source is script-free. Existing 0101 separately proves permitted
JS isolation; 0102 does not silently accept a Next.js/JS-bearing publication. Internal management
commands use a trusted synthetic identity plus real DB membership, not a new management JWT/HTTP
API. Full human UX/WCAG, Production/Hosted, customer assets and shared-Worker credential redesign
are excluded, not reported as passing or used to broaden this increment.

### Real-bundle Browser continuation — 2026-10-14

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| First fresh Browser-enabled gate | 3 failed / 9 passed, stage=pages | Test debugger failed to attach recursively to related child targets; no Browser PASS claimed |
| Second fresh gate after recursive attach | 3 failed / 9 passed | Strict checks failed for pages, embedding observation and Core-effect classification; runtime policy unchanged |
| Third fresh gate after observer corrections | 3 failed / 9 passed | All isolation/header/network/download checks pass; pages assertion still fails |
| Fourth fresh closed-label run | 3 failed / 9 passed, page_checks=images only | No URL/content diagnostic; lazy/async images were inspected before native viewport/decode readiness |
| Final `run-preview-joined-controlled.ps1 -BrowserGate` | **12 passed in 196.37s** | Three real-bundle Browser cases plus the nine retained pipeline/recovery cases under actual aria_worker; all owned services/profiles removed |
| All three types, eight pages including corporate /services/design | PASS | Original v1 fixture files unchanged; explicitly versioned in-memory test recipe supplies nested coverage before original builder |
| Normal scrolling/native decode and local SimpleForm/trusted Enter | PASS | Real CSS/SVG loading and native validation; no loading-attribute/source rewrite or network submission |
| Opaque sandbox/parent DOM-cookie-storage/Core API/form/popup/top-nav/inline code | PASS | Exactly allow-scripts, no new sandbox grants; allowed-origin negative requests are not blocked by the test interceptor |
| Download, external network, font resources, CORS | ZERO / ZERO / ZERO / ABSENT | Download observations confined to owned disposable profile; System Font/frozen CORP policy retained |
| Unauthorized Embed | DENIED | After navigating the separate attacker site, security observation plus inaccessible Preview main proves denial; no console text captured |
| Independent unchanged `0101` Browser regression | PASS; same-origin compatible=false, approved cross-origin compatible=true | Independent JS/hash-CSP proof retained; only bounded outcome fields emitted; profile cleanup completed |
| Static Browser/privacy + existing Preview/SQL contracts | 17 passed | No generic runtime activation, extra HTTP headers, new SDK/dependency, mutation endpoint or security-policy relaxation |
| Worker lint/strict types | PASS / PASS (98 source files) | Production modules/SQL unchanged in this test-only continuation |
| Final `npm test` | PASS: API 592 passed / 246 skipped; Worker 375 passed / 67 skipped; Node/Renderer/Web PASS | Twelve joined integrations explicitly executed above; remaining skips not counted as passes |
| Final `npm run validate` | FAIL only on PENDING 0102; other 22 checks PASS | Same-Representation/two-capability real-file proof and final matrix audit remain open; no completion gate weakened |
| Diff/runner parse/review SQL hash/owned cleanup | PASS / PASS / unchanged / PASS | No task Browser profile/service remains; existing local services and prior work preserved |

Four failed runs were not skipped or reclassified as PASS. Corrections affect only harness
attachment/observation: font is measured at the Renderer root, actual downloads are distinct
from permitted iframe navigation, embedding uses bounded security observations without raw text,
URL references compare with the configured Preview origin rather than the opaque security origin,
and lazy images are actually scrolled/decode-awaited. Browser input/creation capability exists only
in captured pipes and volatile wrapper state; temporary browser history/profile is destroyed under
the already accepted Local/Synthetic residual-risk contract. No trace, screenshot, raw output,
request URL or fixture body is saved as an evidence artifact. No customer/Hosted/paid activity.

Full 0102 remains PENDING for the final matrix audit and real-file reuse under two distinct
capabilities sharing one Representation. This Browser pass does not claim that missing invariant,
full human UX/WCAG or Production transport/security acceptance. Final general regression/validate
and cleanup are recorded above after execution.

### Controlled HTTP continuation — 2026-10-14

Contract-first collection failed because the HTTP adapter was not yet implemented. The initial
unprivileged invocation was blocked by uv cache permissions and was not treated as test evidence.
After implementation, the first run had **17 passed / 1 failed**: malformed HTTP version used
the standard parser's HTTP/0.9 response suppression, producing an empty response rather than a
safe 404. The bounded parser-error path was corrected without returning parser text or request data.
Initial strict types also found one missing raw-requestline byte annotation; that scoped annotation
was added. Fresh HTTP plus existing access tests pass **40 cases** (19 HTTP + 21 access), with
Worker lint and strict types PASS (**98 source files**). The prior seven API bridge tests pass.

The adapter is an explicitly constructed, temporary `127.0.0.1` listener using an ephemeral OS
port and Python standard-library HTTP parsing. It never serves directories or normalizes a raw
target into authority. Duplicate Host, wrong Host/version, absolute-form, leading double slash,
encoded/traversal/query/private-Manifest targets are denied. GET/HEAD preserve the existing response
headers; other methods cannot invoke read authorization or mutate state. Parser/request/error
diagnostics are disabled before formatting, not redacted after token-bearing URL construction.
Factory failure and normal completion close the bound socket and owned threads. Standard HTTP
parser defaults and test-client wait bounds are not new product limits or Production hardening.

ADR-089 permits internal Publish/Issue/Revoke plus controlled public capability reads, not a
management HTTP/JWT endpoint. Earlier NOT EVALUATED labels are disclosure, **not an additional
JWT feature requirement**. Full 0102 completion still requires the real-bundle Browser Gate and
all frozen acceptance assertions; customer/private-asset/Hosted/Production transport is unchanged.

| Final command / evidence | Actual result | Interpretation |
|---|---|---|
| `run-preview-joined-controlled.ps1` on fresh PostgreSQL 16/Redis | 12 passed in 203.99s | Six fixture baseline + six command-backed cases; the latter now use actual loopback HTTP and physical aria_worker resolver |
| HTTP GET/HEAD for HTML/CSS/SVG | PASS | Existing per-resource capability/Manifest/file checks; HEAD empty, no-store/no-CORS preserved |
| Deterministic revoke during authorized file IO | PASS | Authorized in-flight HTTP read finishes after revoke; new read denied; no DB transaction held while IO waits |
| Final `npm test` | PASS: API 592 passed / 246 skipped; Worker 375 passed / 67 skipped; Node/Renderer/Web PASS | Twelve joined skips executed independently; others remain disclosed |
| Worker lint / strict types | PASS / PASS (98 source files) | Only the controlled Infrastructure adapter and scoped tests added; general bootstrap unchanged |
| API process bridge regression | 7 passed | Existing closed command input, bounded diagnostic and one-time response boundary retained |
| Owned services/temp cleanup + reviewed SQL hashes | PASS + unchanged | Only task-created PostgreSQL/Redis/temp resources removed; existing local services preserved |
| Final `npm run validate` | FAIL solely on PENDING 0102; other 22 checks PASS | Browser/full acceptance remains open; architecture and local documentation links intact |
| Final diff check / controlled runner parse | PASS / PASS | Evidence labels only changed after the actual joined run; no extra execution claim |

The runner's pre-existing JWT_HTTP_BROWSER label was emitted by this executed run. It is now
clarified to HTTP-subgate PASS, Browser NOT EVALUATED, management HTTP/JWT OUT OF SCOPE; that
post-run wording change is not a second execution or a new authentication claim. Final validate/
diff verification is recorded above; full 0102 stays PENDING.

### Command-backed integration continuation — 2026-10-14

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| Initial extended joined run | 6 passed / 6 failed | API subprocess inherited Worker VIRTUAL_ENV; uv diagnostic rejected by the existing zero-diagnostic guard |
| Fresh `run-preview-joined-controlled.ps1` after scoped environment correction | 12 passed | Six retained fixture cases plus six real Application command cases; three project types, copy success/recovery, actual aria_worker and real Redis/Celery |
| Publish command replay/conflict/active guard | PASS | Same Publication/Job on replay, no duplicate logical state; different payload and new active command rejected |
| Ready-only Issue, one-time disclosure and replay | PASS | Before-ready denial; after ready token in captured creation-response pipe only, replay token absent; no raw token in idempotency outcome |
| GET/HEAD Application access and Revoke/replay | PASS | Per-read valid capability and exact bound files; subsequent read denied after the existing Revoke command |
| `test_controlled_preview_commands_bridge.py` | 7 passed | Closed input shape, owned loopback DB constraint, bounded unexpected error, captured response transport; no JWT verification claim |
| Established API mypy including bridge / Worker mypy | PASS: 208 / 97 source files | Existing configuration unchanged; scoped test additions only |
| Additional global `mypy --strict` diagnostic | FAIL: 21 errors in 16 existing files | Extra legacy diagnostic, not required-gate PASS; no unrelated refactor or configuration weakening |
| API/Worker + explicit bridge Ruff | PASS | No lint exclusion or gate bypass |
| Final `npm test`, no integration env | PASS: API 592 passed / 246 skipped; Worker 356 passed / 67 skipped; Node/Renderer/Web PASS | Twelve joined skips explicitly executed above; other skipped suites not claimed |
| Owned cleanup / historical SQL hashes | PASS / unchanged | Exact PostgreSQL/Redis/temp resources removed; existing services preserved; no new SQL authority |
| Final `npm run validate` | FAIL solely on PENDING 0102; other 22 checks PASS | Required completion gate retained; local Markdown links and architecture boundaries PASS |
| Final `git diff --check` / PowerShell runner parse | PASS / PASS | Runner label clarification only; no new execution or security-policy claim |

The bridge supplies a trusted synthetic subject to the existing identity boundary and resolves
membership from DB, never from a caller-supplied role. It runs only against the harness-owned
`aria_0102_joined` database. Raw creation capability travels in a captured response pipe and volatile
memory, not process arguments/environment, files, logs or reports. Source rendering and actor setup
remain explicit synthetic fixtures. This subgate proves Application command integration, not
JWT/HTTP authentication, a Preview HTTP listener, browser isolation or Hosted acceptance.
The runner's outcome labels were subsequently clarified to separate Application PASS from
JWT/HTTP/Browser NOT EVALUATED; only evidence wording changed after this 12-case execution.
No product runtime, migration, grant, RLS, dependency, commit or push changed in this continuation.
0102 overall remains PENDING; final architecture validation is recorded below after execution.

### Joined delivery continuation after Push — 2026-10-14

| Command / evidence | Actual result | Interpretation |
|---|---|---|
| No-env collection | 6 skipped | Required services absent; not PASS evidence |
| First joined execution | 6 failed | Harness wiring defect, no ready/finished state falsely accepted |
| Second bounded diagnostic run | 6 failed, stage=preview_runtime / class=TypeError | No raw exception/storage key/content diagnostic printed; no privilege widening |
| Corrected full fresh joined gate | 6 passed | Correct existing Transformer binding reused; real relay/broker/Celery task/Worker/private-copy pipeline |
| All three project types, success + first-copy failure | PASS | First failure remains recoverable; explicit same-ID delivery succeeds; duplicate delivery yields already_completed with no new copy |
| Physical runtime principal | aria_worker | Relay/source runtime/Preview runtime use actual worker login, not DB owner or SET ROLE |
| Source/identity/claim preservation | PASS | Same source bytes, one Preview Job/Publication, event published, no issued token, zero remaining execution claims |
| Bounded relay diagnostics | PASS | No source hash/ref or synthetic storage error marker in captured operational log |
| Container/temp cleanup | PASS | Owned PostgreSQL/Redis/temp data removed; existing local services unchanged |
| Final `npm test` | PASS: API 585 passed / 246 skipped; Worker 356 passed / 61 skipped; Node/Renderer/Web PASS | Six new joined skips explicitly executed above; remaining skipped integrations disclosed |
| Worker lint/typecheck | PASS / PASS (97 source files) | Only test/harness/doc continuation; no production source change |
| Final `npm run validate` | FAIL solely on PENDING 0102, other 22 checks PASS | Authenticated command/HTTP/browser acceptance still incomplete |

Allocation of Preview metadata is fixture-only, matching the earlier SQL-backed Worker test.
Source rendering is explicit test preparation, not an automatic chaining contract. This run
does not prove authenticated command/idempotency integration, HTTP delivery, browser isolation,
hard-kill broker redelivery or Hosted acceptance. Production code/SQL/grants/RLS are unchanged.
New work is local after the verified `a3e3a84` checkpoint Push. Final npm/validate evidence follows
the last regression run above; 0102 overall status stays PENDING.

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

- No claim of zero skips or external/Hosted integration acceptance. Latest PG-only regression
  has 1 API + 17 Worker skips; the 12 joined cases are separately executed, as detailed above.
- No claim of broker-driven whole-process crash E2E; restart/finalization evidence is the
  explicitly identified layered SQL/backend-death, adapter and runtime/copy recovery coverage.
- Full human UX/WCAG or Hosted/customer/Production access/security assessment.
- Management HTTP/JWT endpoint: outside the internal-command scope of ADR-089, not claimed.
  DB-membership-backed Application commands, both fixture/command-allocated queue compositions
  and controlled capability-aware HTTP reads now pass; current source-profile Browser subgate
  also passes independently; the final Local/Synthetic matrix is complete above.
- Hosted/customer content, real Provider, security architecture redesign, commit or push.

The complete [historical SQL review snapshot](./migration-review.sql) stays outside the Alembic
chain as a review artifact. Its original NOT APPLIED comment is historical: approved executable
statements were applied via active 0040 solely to disposable local test databases. See the current
[authority review/evidence](./database-security-review.md). Local/Synthetic 0102 PASS does not
authorize Hosted/customer/Production operation or close the shared-Worker residual risk.

## Final Status

TC-10219 PASS extends the real command/relay/Worker harness, not the fixture-only allocation path.
All required Local/Synthetic acceptance rows have executed evidence; historical failures remain.

**Final status:** PASS
