# Development Record: 0102 Local Preview Publication and Capability

- Increment: `0102-local-preview-publication-and-capability`
- Date: 2026-10-14
- [Test report](./test-report.md)

## Scope

Owner-directed Local/Synthetic implementation of the detailed ADR-089 proposal. Source
ArtifactVersion bytes are retained; a separately verified Preview derivative supports exact-file,
capability-bound delivery. Hosted/customer/Provider activation remains unauthorized. The owner's
subsequent checkpoint publication authorization is recorded below.

### Checkpoint publication authorization — 2026-10-14

After Local/Synthetic completion and the recorded final gates, the owner explicitly requested
"پوش کن". This authorizes committing/pushing the current 0102 completion files to the existing
`codex/s1-d02-text-context-api` branch, not new development, Hosted/customer/Provider activation
or changes to database authority. Pre-publication npm/validate/secret/diff checks are rerun.
Earlier no-commit/no-push statements below retain their original implementation-stage scope.

### Final publication checks — 2026-10-14

The pre-publication secret scan passed across **1,233 publishable text files** after the
test-only fixture cleanup recorded under REQ-10218. Final `npm test` passed: API **592 passed /
246 skipped**, Worker **376 passed / 67 skipped**, and Node/Renderer/Web suites PASS. The
architecture validator passed **23/23** checks and `git diff --check` passed (line-ending
warnings only). Skipped tests remain disclosed and are not counted as passes.

## Current Acceptance State — 2026-10-14

**COMPLETE for the approved Local/Synthetic scope only.** Final joined matrix: **12 PASS in
293.22s**, including three real-bundle Browser cases and six command-backed two-Publication reuse
cases. All detailed ADR-089 acceptance rows are mapped to executed evidence in the linked report.
The mandatory final npm regression passes; final architecture validation **PASS (23 checks)**.
Historical PENDING/FAIL notes below describe earlier subgates, not current
Local/Synthetic status. They remain intact for traceability.

There is no Hosted/customer/real-Provider activation, management HTTP/JWT API, full human UX/WCAG
acceptance or Production tenant-security approval. Shared-Worker compromise remains an open separate
architecture concern. No migration/helper/grant/RLS or general bootstrap changed in this continuation.

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
| REQ-10202 | BE-F3-03; ADR-089 | `prepare_preview` exact nested reference mapping | TC-10202/18/19; path unit tests and final real-bundle Browser/reuse gate PASS |
| REQ-10203 | Owner approved matrix | API Application `preview.py`; `preview_repository.py` | TC-10203; service tests and real-DB Member/tenant binding denial tests |
| REQ-10204 | T-PRV-05; ADR-089 | Issue/revoke commands, hash-only SQL resolver | TC-10204; real-DB issue/replay/conflict/concurrent issuance/expiry/revoke tests |
| REQ-10205 | Scoped asset access | Strict `parse_preview_route`, verified source/delivery Manifest | TC-10205/17/19; route/access/HTTP tests and per-file two-capability reads PASS |
| REQ-10206 | Local/Synthetic boundary | Metadata-only errors/evidence and isolated cleanup | TC-10206/18/19; bounded diagnostics, private-file/outcome/log token negatives and owned cleanup PASS |
| REQ-10207 | ADR-088 | Frozen Sandbox/CSP/System Font boundary | TC-10207 |
| REQ-10208 | Idempotency/outbox rules | Atomic allocation/finalization and same-identity recovery | TC-10208/19; real-DB rollback/claim/backend-death and final joined command/concurrency/recovery PASS; no broker-process-kill claim |
| REQ-10209 | Owner limited DB authority + guarded downgrade decision; existing migration gate | Alembic 0040; immutable SQL review snapshot; ADR-089 | TC-10209/10; 36-case authority/rollback harness, static equivalence and full PostgreSQL regressions PASS with disclosed skips |
| REQ-10210 | Owner continuation in direct response to exact fifth-helper SQL approval question, 2026-10-13; ADR-089 | Alembic 0041, fixed fail helper, Worker `finalize_failure` port | TC-10211/12: 22 actual-role helper tests, bounded Worker failure/rollback tests and three-project-type pipeline verification PASS; full regression tracked below |
| REQ-10211 | Owner continuation directly after the preready revoke/cancel question, 2026-10-13; ADR-089 | Authenticated Application revoke transaction in `preview_repository.py`; existing Job lifecycle | TC-10213: queued/running cancellation, terminal preservation, exact binding, replay, rollback and finalization race; PostgreSQL PASS |
| REQ-10212 | ADR-089 explicit Job/Outbox/Task envelope, disabled automatic retry and Local/Synthetic activation boundary; owner continuation, 2026-10-13 | Controlled-only `preview_publication_task.py` and `preview_outbox_publisher.py`; general bootstrap unchanged | TC-10214: exact envelope, app-local registration, no retry/result persistence, bounded diagnostics and transport; 40-case queue subgate PASS |
| REQ-10213 | ADR-089 controlled same-ID recovery, manifest-last storage and atomic finalization; owner continuation after checkpoint Push, 2026-10-14 | Test-only joined PostgreSQL/Redis/Relay/Worker harness reusing fixed adapters | TC-10215: three project types, copy recovery, duplicate delivery, actual aria_worker principal and source preservation; 6 actual joined cases PASS |
| REQ-10214 | ADR-089 Publish/Issue/Revoke authorization, exact binding and one-time disclosure; owner continuation, 2026-10-14 | Separate-process test-only Application command bridge; existing production services unchanged | TC-10216: 6 command-backed joined cases + 7 bridge unit cases PASS; management HTTP/JWT is outside scope, not claimed |
| REQ-10215 | ADR-089 exact GET/HEAD loopback route, per-resource authorization and non-persistent diagnostics; owner continuation, 2026-10-14 | Controlled-only Infrastructure HTTP adapter, existing access service and joined harness | TC-10217: 19 HTTP + 21 existing access cases and final 12-case actual-role HTTP/Browser rerun PASS |
| REQ-10216 | ADR-089 real 0100 bundles, nested relative references and disposable capability browser proof; ADR-088 frozen isolation; owner continuation, 2026-10-14 | Test-only Browser runner and opt-in joined harness composition | TC-10218: final three real-bundle Browser cases and independent 0101 Browser PASS; full matrix audit recorded |
| REQ-10217 | ADR-089 acceptance matrix: same ready Representation under two distinct capabilities; concurrent same-key Publish; owner continuation, 2026-10-14 | Existing Publish/Issue/Revoke commands, fixed Worker helpers and private create-or-verify storage; joined test extension only | TC-10219: six command-backed cases PASS; concurrent second Publish, real Relay/Worker reuse, identical private/public files, independent revocation and zero persisted tokens |
| REQ-10218 | Owner checkpoint push request; existing repository secret-scan gate, 2026-10-14 | Test-only removal of literal dummy DB passwords in `test_provider_quality_evaluation_command.py`; scanner and runtime unchanged | TC-10220: credential-free inert composition, URL/opaque credential-marker repr rejection and publishable-file secret scan; verification below |

### Two-publication reuse continuation — 2026-10-14

Before editing, REQ-10217 maps the existing frozen cardinality to a test-only extension. Two
concurrent same-key commands must allocate one second Publication/Job using the first ready
Representation. A second explicit relay/Worker delivery runs under actual aria_worker; no fixture
SQL creates or changes either Publication. Private file/Manifest bytes must remain identical,
both independently issued capabilities must serve those same bytes, and revoking one must not
invalidate the other. Tokens remain only in captured pipes/volatile memory. No new SQL, grant,
lifecycle, Renderer/Provider call, HTTP management route or Hosted activation is authorized.
Full 0102 remains PENDING until this evidence and the final acceptance audit are complete.

### Browser proof continuation — 2026-10-14

Before editing, REQ-10216 maps to test-only Chromium/CDP verification using the existing approved
0101 launch/loopback-profile pattern. It is a repository automated test, not user-profile/UI
automation. No existing 0101 script or product source is rewritten. Browser control input travels
only through captured pipes/volatile memory; raw diagnostics, screenshots, console text, request
headers/URLs and traces are never persisted. A separate Core shim embeds the exact ready derivative
with sandbox allow-scripts and no-referrer, on independent registrable test sites. There is no
customer data, cookie/session authority, analytics, new JS source profile or Hosted listener.
The versioned fixtures remain immutable: a separately identified test-only corporate path variant
adds /services/design and updates only matching navigation targets before original 0100 generation.
This supplies the required two-level path proof without modifying Gold/fixture v1 files. Chromium
timeouts remain test tolerances inherited from 0101, not new product defaults. Existing Worker DB
resolver and HTTP adapter remain the access authority; request interception must not substitute
for CSP/server authorization when evaluating allowed-origin negative paths. Full status stays
PENDING until executed evidence and the remaining acceptance matrix are reviewed.

### Controlled HTTP continuation — 2026-10-14

Before editing, REQ-10215 maps to a temporary explicitly constructed loopback listener and
contract-first tests. It delegates every file to the existing access service; no filesystem
fallback, anonymous storage, global bootstrap or deployable service is introduced. The read route
uses a public bearer capability, not JWT. ADR-089 explicitly retains internal management commands;
the earlier remaining-gate wording must not imply authorization to add a management HTTP/JWT API.
Raw request-target is retained only in volatile memory and validated before normalization. Host
duplicates, request-target aliases and all unauthorized files fail closed. Standard-library HTTP
parsing defaults are transport implementation details of this local test adapter, not new product
limits. No new dependencies, migrations, privileges, RLS policies or numeric business defaults.
Browser acceptance remains a separate required gate; this continuation does not claim it.

### Application command integration — 2026-10-14

Before editing, REQ-10214 maps to a fixed test-only API-process bridge and an extension of the
joined harness. The bridge uses the existing tenant/membership resolver and Preview Application
commands. Trusted synthetic subject is injected at the already verified identity boundary; JWT/
HTTP authentication is not claimed. Runtime DB must be the owned loopback `aria_0102_joined` test
database. No role from command input is accepted. Raw capability travels only in a captured
creation-response pipe and volatile test memory, never argv/env/file/log/report. Allocation uses
the real Publish command; source/actor setup remains explicit fixtures. No product endpoint,
cross-module write shortcut, new grant, migration or bootstrap activation is introduced.

### Joined delivery continuation — 2026-10-14

After the owner-authorized checkpoint Push, the next test subgate joins the existing 0070 relay,
controlled Celery adapter, real Redis, actual aria_worker helper path, real synthetic 0100 bundles
and private local copy. Preview metadata allocation remains explicitly fixture-only, as in the
earlier SQL-backed Worker test; it is not authenticated command/HTTP E2E. Source Artifact Generation
is an explicit test preparation step, not production chaining. Its already-delivered fixture event
is marked published before exercising Preview relay. Recovery is an explicit same-message delivery,
never a consumer retry. No SQL/helper/grant, runtime bootstrap or new Provider behavior is added.

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

### Final Local/Synthetic closure — 2026-10-14

- Fresh full joined gate after the final observer/test changes: **12 passed in 293.22s**. Three
  types retain original fixture files; corporate uses the already versioned in-memory nested-page
  recipe. Two concurrent real Application commands allocate exactly one second Publication/Job,
  which reuses the first ready Representation. A second real Relay/Celery/aria_worker delivery
  verifies existing private files, preserves Manifest identity, and atomically succeeds. Replay
  adds no copy. Every Manifest file returns identical bytes under two distinct issued capabilities.
- Real Issue replay discloses neither token; tokens are absent from source/private files,
  delivery Manifest, idempotency outcomes and operational logs. Revoking capability one permits
  a pre-authorized held read to finish, denies new reads, and leaves capability two usable; revoking
  the latter denies it too. Source/derivative bytes remain unchanged through both revocations.
- Earlier extended matrix **11 PASS / 1 FAIL**, diagnostic subset **3 PASS / 9 deselected**, and
  Windows Temp **15 setup errors** remain in the report. No raw request destination was recorded,
  so the first failure's exact cause is not asserted. Exact armed non-network download probe
  classification improves native Sandbox testing; it does not authorize data URLs in an Artifact.
- Final complete PG regression: **837 API PASS / 1 skip; 425 Worker PASS / 17 skips**, plus
  focused **65 API + 12 Worker PASS**. The PG-only suite lacks Redis/joined configuration; its
  12 joined skips were explicitly executed above, not counted as passes from skips. Redis adapter
  coverage is independently recorded. No zero-skip, Hosted or paid-provider claim.
- Final `npm test` with owned workspace Temp: **PASS**, API **592/246 skipped**, Worker
  **375/67 skipped**, all Node/Renderer/Web suites PASS. API/Worker lint/types PASS (207/98 source
  files); Python build PASS; independent unchanged 0101 Browser proof PASS and cleans up.
  Eighteen static security/privacy/SQL contracts PASS. Reviewed SQL hashes remain unchanged.
- PostgreSQL guidance reinforced function-owner separation and fixed least privileges; modern
  Browser guidance reinforced native enforcement and non-persistent diagnostics. No generic
  reporting endpoint, CORS, cookie/session, new dependency, privilege or transport policy was added.
- The final linked report records the complete ADR acceptance audit and final validate outcome.
  Only owned services/profiles/temp directories were removed; previous user services/work are intact.
- Final `npm run validate`: **23/23 PASS**, with the original development-record enforcement
  unchanged. Final `git diff --check` PASS (line-ending warnings only), owned `.tmp` empty,
  and only the four pre-existing containers remain. HEAD is still `a3e3a84`; no commit/push.

### Real-bundle Browser subgate — 2026-10-14

`run-preview-joined-controlled.ps1 -BrowserGate`: **12 PASS in 196.37s**, including three
command-backed Browser cases for landing/corporate/portfolio; the remaining pipeline/recovery
cases also rerun. Eight pages are loaded through the real 0100 builder, unchanged canonical
validators, verified transformer/private copy, actual aria_worker resolver and capability HTTP.
The corporate in-memory recipe `preview_nested_corporate_v1` exercises /services/design while
retaining a root and one-level contact page. Source fixture v1 files, source bundle bytes and
runtime/SQL/grants/RLS stay unchanged. Nested links/styles/images remain under the exact capability.

Proof verifies one main/h1 per page, RTL, controlled System Font/CSS, decoded images, script-free
source, actual link navigation where present, native required-field validation and trusted Enter
in the real SimpleForm. Sandbox is exactly allow-scripts; no-referrer/opaque-origin, parent DOM/
cookie/storage denial, Core API/form/popup/top-navigation denial, zero downloads/font/external
network, absent CORS, no-store and unauthorized embedding denial pass. The negative download test
uses synthetic data and an owned temporary download target; it adds no permissions to the iframe.
No raw console text, HTTP/CDP trace, screenshot, capability or URL is persisted as evidence.
Disposable profiles/history and owned PostgreSQL/Redis/temp data are removed; user profiles and
existing services are untouched. This is not full WCAG/human UX, customer or Hosted acceptance.

Four prior **3 FAIL / 9 PASS** runs are retained: missing recursive child attachment; incorrect
font-root/download/embedding observations; premature image readiness; closed-label confirmation
that only images were failing. Normal scrolling plus native decode resolves lazy/async image
readiness without altering source or loading attributes. No security guard or expected outcome
was lowered. Modern Web guidance reinforced observation/data hygiene; fixed policy remains owner-
defined. Independent unchanged 0101 JS/hash-CSP/Sandbox Browser regression also PASS: same-origin
CORP remains incompatible as expected; approved cross-origin/System Font case passes and cleans up.
Seventeen static/privacy/source-equivalence contracts and Worker lint/types (98 files) pass.
Final mandatory npm/validate results are recorded after the last run in the linked report.

Final `npm test` PASS: API **592 passed / 246 skipped**, Worker **375 passed / 67 skipped**;
Node/Renderer/Web PASS. The 12 joined cases, including Browser opt-in, executed separately and
are not claimed from skipped tests. Final `validate` fails only on PENDING 0102; the other 22
checks, including documentation links and architectural boundaries, pass. Diff/runner syntax
checks pass and both SQL review hashes remain unchanged. All task-created services/profiles/temp
data are gone. No commit/push occurred; remaining matrix work is explicit below.

Full 0102 is still PENDING pending the acceptance-matrix audit and specifically a real-file reuse
proof for two Publications/capabilities bound to the same Representation. Current Browser cases
use one Publication per project and cannot silently stand in for that independent invariant.
No new commit/push or real Provider/customer/Hosted activation is authorized or performed.

### Controlled HTTP subgate — 2026-10-14

Contract-first missing-module RED and the initial 17 PASS / 1 parser-response FAIL are retained
in the linked report. After the bounded parser error and byte annotation corrections, focused
HTTP/access contracts pass **40 cases**. The new Infrastructure adapter never uses the normalized
HTTP path as authority, never serves the filesystem directly, and suppresses HTTP/server diagnostics
before any bearer URL is formatted. A closed synthetic access service is explicitly composed;
general Worker/Relay/API bootstrap, migrations, grants, RLS and dependencies remain unchanged.

Fresh `run-preview-joined-controlled.ps1` passes **12 cases** with real PostgreSQL/Redis/Celery and
physical aria_worker login. The six command-backed cases now perform actual HTTP GET/HEAD of
HTML/CSS/SVG and a deterministic revoke-versus-read test: private file IO is held after SQL access
authorization, the existing Application revoke commits, the in-flight read finishes, and the next
HTTP read is denied. This proves short authorization transactions, not stronger retroactive
revocation of already delivered bytes. No automatic retry, Provider/Renderer reinvocation during
publication or new logical Job is added. Both owned containers/temp data were removed.

Final `npm test` PASS: API **592 passed / 246 skipped**, Worker **375 passed / 67 skipped**,
Node/Renderer/Web PASS. Twelve joined skips are executed separately above; remaining skipped
integrations are not counted as passes. Worker lint/types PASS (**98 source files**); API bridge
regression **7 PASS**. SQL snapshots remain byte-identical; only the loopback HTTP adapter, scoped
tests and documentation changed in this continuation. Real-bundle Browser loading/nested navigation/
isolation remains PENDING. Management HTTP/JWT is explicitly out of scope under ADR-089, not a
missing product feature introduced by test labels. No Hosted/customer/real Provider or commit/push.

Security-guidance review reinforced non-persistent diagnostics and frozen response headers; generic
recommendations for reporting endpoints, CORS, cookies or Production transport were not adopted.
Python standard-library HTTP serving is explicitly proof-only, not Production security acceptance.
No new Supabase/SQL behavior was implemented; changelog review does not authorize a DB upgrade.

### Application command-backed joined subgate — 2026-10-14

The extended fresh throwaway PostgreSQL/Redis run passes **12 cases**: the six fixture-allocated
baseline cases plus six command-backed cases across three project types and copy success/recovery.
The new cases resolve active membership from PostgreSQL, then call the existing Publish, Issue
and Revoke Application services in a separate API process. Publish replay retains the same Job/
Publication; incompatible reuse and a new active command are rejected. Issue before ready fails;
after real relay/Worker finalization, issuance discloses the capability once, replay returns none,
GET/HEAD Application reads succeed, and revoke/replay denies subsequent reads. Raw capability is
absent from the saved idempotency outcome and captured operational stream. Trusted fixture subject
injection is not JWT verification; the read adapter is not an HTTP listener or Browser Gate.

Initial extended execution had **6 passed / 6 failed** because the API subprocess inherited the
Worker virtual-environment variable, causing a uv diagnostic. The test-only subprocess now receives
a closed environment allowlist without Provider credentials or the other project's virtual env.
Diagnostic text remains withheld; the zero-diagnostic guard was not relaxed. A new fresh complete
run then passed all 12 cases. Seven bridge shape/DB-boundary/bounded-error/response tests pass.

Final `npm test` PASS: API **592 passed / 246 skipped**, Worker **356 passed / 67 skipped**,
Node/Renderer/Web PASS. The 12 joined cases skipped in the no-env suite were separately executed;
other integrations are not claimed. Established API typecheck plus bridge passes **208 source files**;
Worker typecheck passes **97**; API/Worker and explicit bridge Ruff checks pass. An additional
global `mypy --strict` diagnostic failed with 21 errors in 16 existing files; no unrelated code or
mandatory typecheck policy was changed. This extra diagnostic is not reported as PASS. Both
owned containers/temp data were removed. SQL review snapshots and production code remain unchanged.
The required final architecture validation stays FAIL on PENDING 0102; its other checks are
recorded in the linked report. No new commit/push or Hosted/customer/Provider activation occurred.

### Joined PostgreSQL/Redis delivery subgate — 2026-10-14

`run-preview-joined-controlled.ps1`: **6 passed** using fresh PostgreSQL 16 + Redis containers.
Real 0070 relay and real Celery delivery execute the actual Preview runtime with physical
`session_user=current_user=aria_worker`; all three project types verify ready finalization,
immutable source bytes, release of claims and duplicate delivery without additional copy.
Injected first-copy failure leaves the same Job recoverable; explicit delivery of the same
event/Job succeeds, with one Publication/Job and no automatic consumer retry. Each task owns
its engine/loop/session lifecycle. No runtime, migration, privilege, RLS or dependency changed.

History is retained: the first joined run had 6 failures; a second bounded diagnostic run
identified `TypeError` before copy. The harness instantiated the existing Transformer incorrectly.
Only the test composition was corrected to the already passing `PreviewTransformer(ROOT).file`
binding; no security guard was weakened. The complete fresh third run passed. Initial no-env
collection skipped six cases and was never counted as executed evidence. Worker lint/types pass.
Both owned service containers and temporary data were removed; existing local services preserved.
General regression/final validation are recorded after the last run in the linked report.
Final `npm test` PASS: API 585 passed / 246 skipped; Worker 356 passed / 61 skipped;
Node/Renderer/Web PASS. The six new skipped joined cases were explicitly executed separately
above, not counted as passes from skips. Worker lint/types PASS (97 source files). Final
validate remains failing only on PENDING 0102; other 22 checks pass. Owned containers/temp data
are gone and historical SQL review hashes remain unchanged.

Fixture-only metadata allocation and explicit source preparation are not authenticated commands,
automatic production chaining, HTTP or browser E2E. Those remaining gates keep 0102 PENDING.
The checkpoint `a3e3a84` was pushed before this work; this continuation remains local/uncommitted.

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

The paragraphs above retain historical subgate observations. Current Local/Synthetic acceptance
is complete through final joined/Browser and two-Publication file-reuse evidence plus the full
ADR matrix audit. Hosted access, customer content, private assets and shared Worker compromise
remain outside this approval. `WORKER-CROSS-TENANT-001` remains OPEN; local route capabilities can
still be observed in disposable browser history/debug interfaces before profile cleanup.
The standard-library loopback server is proof-only, not a production server. No management HTTP/
JWT API, public copy/share flow, customer/paid/Hosted activation or operational bootstrap is enabled.
Layered SQL/backend-death/adapter rollback evidence is not broker-driven process-crash E2E.
Skipped/deferred integrations, historical environmental failures, and the existing FastAPI/
Starlette TestClient deprecation warning remain disclosed; no unrelated dependency upgrade.

**Final status:** PASS
