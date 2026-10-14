# Development Record: 0102 Local Preview Publication and Capability

- Increment: `0102-local-preview-publication-and-capability`
- Date: 2026-10-13
- [Test report](./test-report.md)

## Scope

Owner-directed Local/Synthetic implementation of the detailed ADR-089 proposal. Source
ArtifactVersion bytes are retained; a separately verified Preview derivative supports exact-file,
capability-bound delivery. Hosted/customer/Provider activation and commit/push remain unauthorized.

## Source Documents

- Current owner instruction to continue after the detailed ADR-089 proposal, 2026-10-12.
- Owner approval of limited DB architecture/design/tests, followed by "ادامه بده" in response
  to the explicit question authorizing the named SQL only on throwaway Local/Synthetic PostgreSQL,
  2026-10-12. This authorizes the scoped active migration test, not Hosted or full product activation.
- [ADR-089](../../adr/ADR-089-local-preview-publication-and-capability.md).
- Owner "ادامه بده" in response to the explicit empty-only downgrade/cross-database Role
  preservation question, 2026-10-12; ADR-089 guarded downgrade section; REQ-10209/TC-10210.
- [Engineering Backlog](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit), BE-F3-02/03; read 2026-10-12.
- [Engineering Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit), section 14.4; read 2026-10-12.
- [Security and Threat Model](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit), TB-08/T-PRV-01..05; read 2026-10-12.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-10201 | BE-F3-02; ADR-089 | Worker `preview_transformer.py`; shared `preview_delivery.py` | TC-10201; `test_preview_real_bundle.py` |
| REQ-10202 | BE-F3-03; ADR-089 | `prepare_preview` exact nested reference mapping | TC-10202; `test_preview_delivery.py` (no Browser Gate yet) |
| REQ-10203 | Owner approved matrix | API Application `preview.py`; `preview_repository.py` | TC-10203; service tests and real-DB Member/tenant binding denial tests |
| REQ-10204 | T-PRV-05; ADR-089 | Issue/revoke commands, hash-only SQL resolver | TC-10204; real-DB issue/replay/conflict/concurrent issuance/expiry/revoke tests |
| REQ-10205 | Scoped asset access | Strict `parse_preview_route`, verified source/delivery Manifest | TC-10205; `test_preview_delivery.py`, `test_preview_manifest.py` (delivery runtime pending) |
| REQ-10206 | Local/Synthetic boundary | Metadata-only errors/evidence and isolated cleanup | TC-10206; service result repr/bounded error checks; runtime leakage gate pending |
| REQ-10207 | ADR-088 | Frozen Sandbox/CSP/System Font boundary | TC-10207 |
| REQ-10208 | Idempotency/outbox rules | Atomic allocation/finalization and same-identity recovery | TC-10208; real-DB rollback/claim/backend-death/replay tests (not complete delivery runtime) |
| REQ-10209 | Owner limited DB authority + guarded downgrade decision; existing migration gate | Alembic 0040; immutable SQL review snapshot; ADR-089 | TC-10209/10; 36-case authority/rollback harness, static equivalence and full PostgreSQL regressions PASS with disclosed skips |
| REQ-10210 | Owner continuation in direct response to exact fifth-helper SQL approval question, 2026-10-13; ADR-089 | Alembic 0041, fixed fail helper, Worker `finalize_failure` port | TC-10211/12: 22 actual-role helper tests, bounded Worker failure/rollback tests and three-project-type pipeline verification PASS; full regression tracked below |
| REQ-10211 | Owner continuation directly after the preready revoke/cancel question, 2026-10-13; ADR-089 | Authenticated Application revoke transaction in `preview_repository.py`; existing Job lifecycle | TC-10213: queued/running cancellation, terminal preservation, exact binding, replay, rollback and finalization race; PostgreSQL PASS |
| REQ-10212 | ADR-089 explicit Job/Outbox/Task envelope, disabled automatic retry and Local/Synthetic activation boundary; owner continuation, 2026-10-13 | Controlled-only `preview_publication_task.py` and `preview_outbox_publisher.py`; general bootstrap unchanged | TC-10214: exact envelope, app-local registration, no retry/result persistence, bounded diagnostics and transport; 40-case queue subgate PASS |

### Controlled queue continuation — 2026-10-13

The approved preview Job/Event/Task identities map only in an explicitly constructed Local/Synthetic
adapter. Existing general Worker/Relay bootstrap and publisher remain unchanged. Task registration
must be app-local, not Celery's shared task registry, so constructing a test app cannot expose the
task on a later Core/Hosted app. No environment flag, deployable service, broker choice, Provider,
SQL privilege, chaining or automatic task retry is introduced. Existing 0070 relay durability and
backoff remain unchanged; publish retry is not consumer retry. Unit/transport subgates cannot claim
full PostgreSQL-to-browser E2E acceptance. Contract tests precede implementation.

### Preready revocation authorization — 2026-10-13

The owner continuation accepts the proposed atomic preready revoke: the same active publishing
Job becomes `cancelled` together with Publication revocation and its idempotency outcome. This
uses the already-defined queued/running -> cancelled Job transitions; no new error code, retry,
Outbox deletion, Representation deletion or lifecycle enum is introduced. Terminal Jobs retain
their committed result. Revoke must acquire the scoped Job before Publication, matching Worker
lock order, and revalidate the exact server-owned binding under lock. No migration/helper/grant
or existing Worker SELECT/RLS change is authorized or needed for this Application transaction.
Contract tests preceded implementation: 6 RED failures then 65 API + 12 Worker focused passes.
Full 0102 remains PENDING. Complete regression results are recorded after final execution.

### Fifth-helper execution authorization — 2026-10-13

Owner "ادامه بده" directly follows the focused question approving exact
`failure-helper-review.sql` for Local/Synthetic migration. Authorization is scoped to that source:
one fixed helper, one helper-owner SELECT(error_code), Worker EXECUTE only, no RLS/table grant
change. The historical design review file stays immutable; an active migration must embed its
executable statements rather than loading documentation at runtime. No Hosted or commit/push
authorization is inferred. Tests are added before migration/runtime implementation.

### Worker continuation — 2026-10-13

Before implementation, REQ-10201/02/06/08 map to the new framework-free
`preview_publication_runtime.py` and contract-first `test_preview_publication_runtime.py`:
explicit identifier-only message, independent synthetic-source allowlist, canonical validation
port, all-source verification before copying, manifest-last read-back, immutable create-or-verify,
same-identity recovery and bounded failures. PostgreSQL adapter and concrete private storage
composition remain separate verification steps; unit doubles cannot establish their authority.

The fixed-helper PostgreSQL adapter now maps REQ-10208/09 to `db/preview_publication.py`,
`test_preview_job_store.py` and `test_preview_publication_runtime_postgres.py`. Local copy
maps REQ-10201/05/06 to `preview_storage.py` / `test_preview_private_storage.py`; source AST
validation maps REQ-10201/02 to `preview_canonical_validator.py`, existing 0095 content validator
and 0096 consumer validator. No source/schema/Renderer behavior is changed. The new real-role
tests extend the existing disposable authority harness, not Hosted composition.

## Assumptions and Clarifications

### Read-only delivery continuation — 2026-10-13

Before editing, REQ-10202/04/05/06/07 map to `application/preview_access.py`,
`db/preview_access.py` and `test_preview_access.py`: exact configured Host/version, hash-only
capability authorization on every GET/HEAD, private Manifest verification, file size/checksum
before response, uniform safe denial and frozen no-store/no-referrer/CSP/CORP boundary.
No HTTP listener, Hosted activation or Browser acceptance is implied by the Application tests.

At that earlier continuation, owner response approved **design only** of a fifth `fail_preview`
helper. The source remained unapplied until the subsequent exact-SQL authorization documented
above. REQ-10208/09/10 trace to the unchanged historical review file and approved 0041 execution.

Implementation is in progress. No unapproved behavior or numeric default is introduced.
The new source profile only supports actual 0100 HTML/CSS/SVG bundles. Parser implementation
uses standard-library HTML parsing and exact verification of the fixed Application CSS/SVG profile,
so unsupported CSS syntax is rejected rather than interpreted as a general stylesheet.

**Unapproved assumptions:** None

## Changes

- Contract tests added before implementation.
- Shared framework-free path/Manifest validation and deterministic preview transformer added.
  Original source hashes/bytes stay intact; closed HTML/CSS/SVG profiles are enforced.
- Owner-approved exact Manifest image preload removal is implemented and tested against real
  synthetic landing/corporate/portfolio bundles, with normal img references retained.
- Internal Application commands, ORM and repository drafts are present but not composed into
  product/public routes. No Preview Worker delivery/storage/browser runtime is enabled.
- Initial stage: SQL prepared as a **source-review document**, not an active Alembic migration. Exact
  table/claim definitions, role/column grants, RLS and four fixed helpers are included.
- Function owner does not own target tables. No direct Worker grant, dynamic SQL, role membership
  or unrelated Worker RLS redesign. Resolve locks before wall-clock expiry validation.
- Six static SQL shape/security-review checks are included in `npm test`. They are not actual
  PostgreSQL privilege tests. See [database-security-review.md](./database-security-review.md).
- Added 27 non-DB command tests: membership/key rejection before the port, active role delegation,
  synthetic-source allowlist forwarding, identity-bound fingerprints, canonical expiry instants,
  expired-original-request replay delegation, token-free repr and bounded error messages.
  Test doubles do not claim resource ownership, RLS, one-time persistence or concurrent replay proof.
  No production behavior or SQL changed in this continuation; migration source SHA-256 remains
  `916b2babe10e57b05d9b5fd19e4d127fae54a5c71182e757470d6333a4ece3b6`.
- Subsequent scoped execution approval: Alembic 0040 mechanically embeds the reviewed executable
  SQL and registers Preview models in migration metadata. The historical SQL review file remains
  immutable and is not loaded at runtime. Seven static checks include exact executable equivalence.
- Real-role SQL/capability tests added and passed: actual aria_worker login, function-only owner,
  RLS enabled, no direct new-table privileges, exact Job/Event graph, concurrency, rollback,
  backend death/reclaim, revocation, expiry, one-time replay, DB FK/identity/delete/index guards.
- Reproducible `tests/e2e/run-preview-authority-controlled.ps1` creates a new loopback-only
  PostgreSQL 16 container, runs migrations/tests and removes that exact container. All manually
  created task instances were removed; existing local databases/containers were untouched.
- Initial downgrade regression was retained as FAIL until owner approval. Following that explicit
  approval, empty-only rollback checks all three tables under transaction-bound exclusive locks,
  removes only fixed 0040 objects/grants, and preserves a Role used by other databases. Safe Role
  reuse verifies all locked attributes, never ALTERs them or grants memberships.
- Added contract-first migration tests: nonempty rollback preservation, empty round-trip,
  incompatible Role rejection/transactional schema rollback, two-database preservation/reuse
  and last-dependency cleanup. Original table/helper SQL remains semantically unchanged.
- Outbox fixture cleanup now includes the new Preview claim FK table. This is test-only setup;
  it changes no runtime scheduling, permissions, retry, business deletion or tenant behavior.
- 2026-10-13: explicit Worker preparation runtime verifies its independent synthetic-source
  allowlist, source namespace, canonical AST and all file checksums before any destination write.
  It copies immutable files with read-back, commits the private Manifest last and delegates atomic
  ready/success persistence to the reviewed helper. Recovery retains all logical identities.
- Canonical validation reuses 0095 closed-property/content validation on a validation-only copy
  plus the existing 0096 consumer validator; invalid/unnormalized source is rejected, not repaired.
  Node output is suppressed, subprocesses are reaped and temporary synthetic input is removed.
  The existing 0100 fixed Node-tool timeout is inherited; no new numeric product policy is added.
- Local proof storage is explicitly bound to one server-generated namespace. No overwrite,
  public listing, URL/storage credential or remote SDK is added. Complete files are published
  atomically under competing writers; symlink/junction paths are rejected. This is not a Hosted
  storage authorization or hostile-multiuser-filesystem isolation claim.
- PostgreSQL adapter invokes only existing claim/finalize/release helpers. Transactions end before
  external copying. Connection invalidation on ambiguous commit, cancellation or release failure
  prevents returning a possibly advisory-locked session to the pool. Existing Worker adapters,
  table grants, RLS, scheduler and retry behavior are unchanged.
- Six real-principal cases use actual synthetic source builds across landing/corporate/portfolio,
  real local destination files, actual `aria_worker` login and controlled copy failure/recovery.
  Test-only Preview metadata allocation is explicit SQL fixture setup; it does not substitute for
  authenticated Application/HTTP/queue E2E, which is separately required.

## Structure Preservation

### Approved permanent-failure implementation — 2026-10-13

- 0041 mechanically embeds the approved fifth-helper SQL. Original 0040 and both historical
  review snapshots are unchanged. No docs file is read at runtime. Source-equivalence tests
  prove the executable statements match the review file.
- Worker records failed only for the three known non-retryable preparation codes after synthetic
  source authorization. Same Job is failed with bounded reason and NULL detail; no representation,
  publication, source file, capability, Provider/Usage or latest pointer is created/changed by failure.
- Failure commit error does not return a terminal result. Explicit recovery retains the same
  identities and revalidates source. Existing storage/DB recoverable paths and cancellation remain
  outside terminal failure handling. Redelivery of a failed Job is denied before source/storage work.
- The existing held-session adapter invokes `fail_preview` with fixed parameters. It validates
  the exact Job binding and code allowlist before SQL. Commit failure invalidates the session;
  release uses the original helper. No direct Worker Job/table-write path was added.
- New PostgreSQL tests require actual aria_worker and SQLSTATE 42501 for denial, not just any
  DB error. Own claim plus live lock, wrong Job/Event/tenant, foreign session, missing live lock,
  terminal reason conflict, revoke/success exclusion, rollback, one-column owner ACL and narrow
  populated-data downgrade are tested. Legacy nonempty 0040 rollback must now retain revision
  0041 transactionally; that stronger assertion does not weaken the underlying guard.
- Harness adds explicit optional full PostgreSQL regression on its own fresh loopback instance;
  suites execute sequentially because fixtures share that disposable database. It remains a test
  tool, not Runtime activation, scheduler or public endpoint.

### Read-only access changes — 2026-10-13

- Added framework-free `PreviewAccessService` with exact pinned version/Host and mandatory
  synthetic-source allowlist. Every GET/HEAD independently resolves the capability hash, checks
  the private delivery Manifest and verifies complete file bytes before returning headers/body.
  HEAD performs the same checks and never returns a body. No cache or latest-version lookup.
- Missing/malformed/revoked/wrong-bound capability, invalid file/reference/hash and dependency
  errors return uniform safe denial. The private Manifest is never an exposed file. No requested
  token, URL, hash, exception or file content enters response diagnostics or repr.
- Existing ADR-088 header policy is enforced as result metadata: no-store/no-referrer, nosniff,
  closed CSP, system fonts, exact frame-ancestors, no ACAO; CORP cross-origin applies only after
  exact verified file authorization. This profile has no inline scripts/styles, so CSP hash lists
  are empty. No script/style grant or Sandbox permission was weakened.
- Added `PostgresPreviewCapabilityResolver`, invoking only existing `resolve_preview`. Its short
  read transaction closes before Storage work. No SQL/helper/grant/RLS/schema change is made.
- Six real Worker/PostgreSQL cases now also verify hash-only resolution and GET/HEAD file access,
  followed by synchronous deny after revocation. Capability issuance/revocation are fixture-only
  SQL setup here; authenticated commands remain covered separately by API tests, not bypassed
  in an advertised Product E2E.
- A fifth-helper **design-only** source was prepared following explicit owner approval. It
  proposes three permanent error codes and one owner-only read column for stable same-reason
  replay. It is not loaded/applied; original SQL snapshot and active migration remain unchanged.
- Queue/consumer composition stays unmodified until permanent-failure authority is reviewed.
  No HTTP listener/browser runtime or public Core endpoint was added in this continuation.

Existing API/Worker modular boundaries and Artifact source immutability are retained. No new
deployable service or product management endpoint is added.

## Senior Review

Source-only review corrected missing PL/pgSQL terminators and Job read privileges required by
restricted UPDATE expressions. NULL validation and explicit optional Data API privilege revocation
are included. Revoke/resolve ordering checks use locked Publication and post-lock wall time.
Scoped SQL execution approval was received and the real aria_worker authority gate passed. The
Supabase/PostgreSQL skills reinforced owner separation and narrow role/column grants, not broad
Worker access. Source graph scoping is not full isolation after shared Worker compromise;
`WORKER-CROSS-TENANT-001` stays OPEN. **Full security acceptance remains PENDING.**
Approved guarded rollback now passes the previously failing legacy regression. No populated table
can be dropped; unexpected dependencies abort DDL transactionally. Reviewed PostgreSQL guidance
reinforced locking before the emptiness check and catalog-based shared Role preservation.

## Verification

### Owner-authorized checkpoint publication — 2026-10-14

The owner explicitly requested "push first, then continue". This authorizes committing/pushing
the current 0098–0102 checkpoint to `codex/s1-d02-text-context-api`, including the disclosed
PENDING 0102 work; it does not authorize Hosted/customer/Provider activation or a PASS claim.
The existing completion gate is unchanged. General regression is rerun before commit; exact
results are recorded in the linked report. Subsequent continuation remains Local/Synthetic.

### Controlled queue transport — 2026-10-13

New contracts first failed collection because the adapters did not yet exist. After implementation,
`run-preview-queue-controlled.ps1` passed **40 cases**: 27 new adapter contracts, 3 actual loopback
Redis/Celery worker cases, and 10 existing publisher/configuration cases. Success, known permanent
failure and recoverable failure reach the same closed task envelope, with one invocation and no
consumer retry. This proof uses a synthetic executor double and is explicitly **not** PostgreSQL/
Outbox-to-storage/browser E2E. The owned Redis container was removed; existing Redis/PostgreSQL
services were untouched. Worker lint/typecheck PASS (97 source files). Final npm/validate results
after regression: `npm test` PASS, API **585 passed / 246 skipped**, Worker **356 passed / 55
skipped**, all Node/Renderer/Web suites PASS. The three new Redis skips in the general suite
were explicitly executed in the owned transport gate above. Other skipped integrations remain
disclosed, not silently counted as passes. Validate still fails only on PENDING 0102, with its
other 22 checks PASS. No SQL/DB or full PostgreSQL gate was rerun/claimed for this queue-only change.

Senior review used backend/queue skill guidance to retain the approved framework and separate
at-least-once delivery from task retry. Celery app-local registration prevents a later ordinary app
from inheriting Preview. No general bootstrap, existing publisher, dependency, SQL, RLS or grant
changed. Three SQL-backed finalization/replay/resource gates remain independently required.

### Final preready cancellation regression — 2026-10-13

Fresh controlled PostgreSQL gate PASS: 65 API + 12 Worker focused cases. Complete sequential
regression PASS: API **830 passed / 1 skipped**, Worker **379 passed / 2 skipped**. `npm test`
PASS: API 585/246 skipped, Worker 329/52 skipped, Node/Renderer/Web PASS. API lint/typecheck
PASS (207 source files); SQL equivalence/security checks 10/10 PASS; both historical SQL hashes
unchanged. Task-owned container/temp directories removed, existing local services preserved.
Validate still rejects only PENDING 0102; its other 22 checks PASS. No migration/helper/grant/RLS,
Hosted activation, commit or push was added in this continuation.

Senior review applied PostgreSQL skill guidance to consistent Job -> Publication locking and
short transactions. Revoke-first and finalization-first races, same-key replay, flushed rollback,
exact payload scoping and terminal preservation all execute on the real database. The scoped
Application command tests do not claim full HTTP/operational API-role or browser acceptance.

### Final fifth-helper regression — 2026-10-13

`run-preview-authority-controlled.ps1 -FullRegression` PASS on fresh PostgreSQL 16, with actual
aria_worker helper/pipeline tests. Focused 58 API + 12 Worker cases PASS. Complete sequential
PostgreSQL regression: API **823 passed / 1 skipped**, Worker **379 passed / 2 skipped**. Skips
remain disclosed. General `npm test`: API 585/239 skipped, Worker 329/52 skipped; Node/Renderer/
Web PASS. API/Worker lint/types and strict migration mypy PASS. Ten SQL source/security/equivalence
checks PASS. The generated container and owned temp directories were removed, existing containers
untouched. No Hosted migration or commit/push. Validate remains failing only on PENDING 0102.

Scoped DB authority/rollback harness: 36 passed; owner != target-table owner and
session_user=current_user=aria_worker verified. Final PostgreSQL regression: API 801 passed /
1 skipped; Worker 281 passed / 2 skipped. Earlier environmental/fixture failures and reruns are
recorded separately; no test was skipped or weakened to hide them.
Validate correctly fails on this PENDING report; Browser/storage/complete Worker gates remain open.
Latest non-DB `npm test`: API 585 passed / 217 skipped; Worker 243 passed / 40 skipped. Nine
SQL/equivalence/rollback checks and API/Worker lint/typecheck passed; the migration also passes
strict typecheck. Cleanup applies only to task-created temporary databases/directories/containers.

2026-10-13 continuation: 79 focused non-DB Preview tests PASS (47 new cases plus 32 existing),
including real-bundle copy with reused validators. Fresh PostgreSQL harness: prior 36 authority/
downgrade cases plus 6 new actual-Worker copy/recovery cases PASS. No Browser Gate is inferred.
Latest complete regression and final verification commands are recorded in the linked report.
Final `npm test`: API 585 passed / 217 skipped; Worker 290 passed / 46 skipped; Node/Renderer/Web
PASS. Worker lint and strict types PASS (93 source files). Validate fails only the PENDING 0102
record; its other 22 checks PASS. Six new database cases were executed separately, not counted
as passed merely because the general suite skips them. The owned disposable container and
test directories were removed; existing databases and previous uncommitted increments remain.

## Remaining Risks

Final read-only continuation verification: 32 focused access/resolver cases PASS; disposable
PostgreSQL 36 authority/downgrade + 6 actual Worker access/copy/revoke cases PASS. `npm test`
PASS with API 585/217 skipped and Worker 322/46 skipped; Node/Renderer/Web PASS. Worker lint/types
PASS (95 source files). Validate fails only on PENDING 0102; the other 22 checks pass. Original
review snapshot hash and active migration remain unchanged; only owned test resources were cleaned.

Current read-only acceptance is an Application/Repository subgate, not HTTP/browser security
acceptance. The approved fifth helper and owner-only SELECT(error_code) were verified only on
throwaway PostgreSQL; no existing local/Hosted database was migrated. Preready revocation Job
disposition was initially an open edge. Owner-approved preready cancellation now passes the
Application transaction/replay/rollback/finalization-race subgate without new Worker privileges.

Hosted access, customer content, private assets and shared Worker credential compromise remain
outside this Local/Synthetic gate. Browser and PostgreSQL tests are required before completion.
Rollback compatibility is CLOSED; skipped/deferred external integrations remain disclosed. The
successful SQL subgate does not authorize or prove storage delivery, HTTP access or Hosted use.
Local private-copy/Worker preparation and approved known-permanent failure subgates are verified.
Controlled queue adapter/transport subgate now passes; concrete PostgreSQL/Outbox/Worker
composition, capability-aware HTTP delivery,
revocation-vs-read and real-bundle Browser
security acceptance remain PENDING. No operational runtime or paid/customer/Hosted path is enabled.

**Final status:** PENDING
