# ADR-090 P7 — Independent P1 Publishing Contract

**Revision:** P7 r2 contract proposal, 2026-11-01.
**Status:** PROPOSED / PENDING INDEPENDENT SOURCE REVIEW; NOT FROZEN.
The owner selected separate limited Core authority for design only; section 8 supplies its exact
proposed principals, signatures, trust boundary and ACLs. No exact r1/r2 choice is thereby approved.
**Authority:** owner froze P6 r1 and authorized exact P7 contract design only.
**Scope:** Local/Synthetic documentation. No executable SQL, Migration, Runtime, Browser Proof,
Hosted/customer content, Commit or Push. This is not complete 0103 or full ADR Freeze.

## 1. Sources, preservation and design authority

Sources: current owner decision; frozen [P4](ADR-090-controlled-preview-workspace-contract.md),
[P5 SQL r3.1](ADR-090-p5-sql-contract.md), [P6 r1](ADR-090-p6-private-packet-manifest-contract.md),
[ADR-089](ADR-089-local-preview-publication-and-capability.md); source inspection 2026-11-01 of
0040/0041, Preview Application/repository, Worker DB/task/outbox adapters and shared idempotency.
Canonical links and review date 2026-10-17 remain in the parent; no fresh Drive review claimed.

P7 adds closed P1 support to the existing Representation/Publication model (approved Option A).
It does not alter old helpers, old per-file storage/resolver, the five frozen P5 SQL blocks,
P6 names/paths/shape, ArtifactVersion/current pointers, Renderer or source bytes. New names,
helpers, policies/index and operational claim table below are PROPOSED, not installed objects.

**Core authority finding:** 0102's management-command tests use the controlled fixture
session; they do not establish a restricted authenticated Core DB principal. 0040 denies direct
Preview access to Worker/anon/authenticated and only installs helper-owner policies. A role merely
named `aria_api` in unrelated revocation statements is not an approved management principal.
Do not run Core management as DB owner or silently grant direct table rights to solve this.
The owner selected separate limited Core authority with fixed operations, without direct
Worker/anon/authenticated access. This closes the direction question only, not source review of
the exact roles/functions/grants proposed in section 8. No old fixture principal is promoted.
Identity/membership, Project visibility and idempotency sources were additionally inspected on
2026-11-01. PostgreSQL skill guidance reinforced column-limited authority, role separation and
short/consistently ordered transactions; it supplies no product defaults or runtime authorization.
Technical privilege cross-check: PostgreSQL 16
[SELECT](https://www.postgresql.org/docs/16/sql-select.html), reviewed 2026-11-01: locking SELECT
requires an UPDATE privilege. Core allocation therefore uses its transaction advisory lock and
plain Representation reads, not a hidden UPDATE grant solely for SELECT FOR UPDATE.

## 2. Fixed profile, command contracts and identifiers

P1 always binds the pair `preview_bootstrap_transformer_v1` /
`preview_bootstrap_delivery_policy_v1` and `preview_bootstrap_manifest/v1`. No Application command accepts
a profile, namespace, source hash, manifest reference, dispatch override or caller-selected role.
Source/Representation/Job/Publication/Outbox IDs are server-resolved/generated, never Provider IDs.

Proposed Application-only command signatures (NOT public HTTP/API or installed DB functions):

```text
PublishBootstrapPreview(context, project_id UUID, artifact_version_id UUID, key TEXT)
  -> publication_id UUID, job_id UUID, replayed BOOLEAN
IssueBootstrapPreviewCapability(context, project_id UUID, publication_id UUID,
                                key TEXT, expires_at aware-UTC-datetime)
  -> publication_id UUID, token TEXT-or-NULL, token_available BOOLEAN, replayed BOOLEAN
RevokeBootstrapPreviewPublication(context, project_id UUID, publication_id UUID, key TEXT)
  -> no business response body
```

`context` is the existing authenticated Identity/TenantContext, not a public actor/account
assertion. Revalidate active membership and tenant/project visibility server-side. Active
Owner/Admin/Member may Publish; Owner/Admin may Issue/Revoke any visible P1 Publication, Member
only their own. Missing/foreign/non-visible/wrong-profile resources use safe RESOURCE_NOT_FOUND,
with no extra out-of-tenant existence lookup. Inactive membership retains existing semantics.
No HTTP method/status/route is Frozen here; future transport remains a separate ADR-090 gate.

Proposed P1-only delivery identities, separate from 0102:

```text
job_type          = preview_bootstrap_publication
event_type        = preview.bootstrap_publication_requested.v1
delivery_channel  = job_queue
celery_task       = aria.preview.bootstrap.publish.v1
queue envelope    = message_version, outbox_event_id, job_id
message_version   = "1"
Job payload       = publication_id, representation_id, artifact_version_id
Outbox payload    = jobId, taskType, payloadVersion
taskType          = preview_bootstrap_publication
payloadVersion    = "1"
```

All payload objects are exact/closed; UUID strings bind the same graph. No tenant/content/token/
packet/path/hash is added to the queue envelope. Existing tenant metadata on the Outbox row is
unchanged. P1 registration/routing is explicit in controlled composition only; no legacy task
replacement, global/Hosted registration, environment auto-enable, chaining or generic dispatch.
SDK/Provider calls remain absent; Celery automatic retry OFF and persistent task results OFF.

## 3. Allocation, cardinality and idempotency

Proposed Publish transaction: authorize Project -> serialize allocation for the exact tenant/
ArtifactVersion -> reserve/replay idempotency -> resolve the ready, synthetic-allowlisted source
-> get/create the exact fixed-profile Representation -> active-Job guard -> allocate Publication,
Job and Outbox -> persist safe outcome -> commit. Return identities only after confirmed commit.
Replay precedes source/current-state and active-Job guards, but never authorization/Project scope.

Propose a transaction advisory allocation key derived only from
`aria:preview-bootstrap-allocation:` + canonical account UUID + `:` + ArtifactVersion UUID;
no Project UPDATE privilege is added just to take a row lock. Hash collisions may serialize more
work, not authorize it. Existing profile UNIQUE remains the final concurrent Representation guard.
An additional P1 partial UNIQUE index on `(account_id, project_id, payload_ref->>'representation_id')`
for P1 Jobs in queued/running is the final active-Job guard, not just Application precheck.
The old v1 index remains unchanged. Allocation takes no existing Job or Representation row lock;
use plain reads under its transaction advisory lock plus DB uniqueness/FK guards. Worker may
advance preparation concurrently, but immutable source/profile identity cannot change. Core
must not assume its earlier status read reserves readiness; Worker revalidates before finalizing.

An existing ready Representation may be reused only with exact source/profile/identity. A new
Publication still has its own queued Job/Outbox and must pass verification/finalization; Publish
never turns itself into capability issuance. Non-ready Representation with no active Job may be
prepared by a new explicit Publication/Job. Never repoint an old Publication or overwrite bytes.

Proposed idempotency uses the existing account/actor/route/key boundary and 24-hour policy:
route keys `preview-bootstrap:{project_id}:publish`, `:issue`, `:revoke`. Fingerprints use existing
canonical JSON/SHA-256 with authenticated account/actor, Project, fixed command name, exact target
and fixed P1 transformer/policy/Manifest identities; Issue also includes canonical UTC expiry.
No raw capability enters a fingerprint or saved response. Same unexpired scope/key/request returns
the original safe identities/outcome; changed semantics conflict. Command namespaces are distinct.
Failed transactions leave no completed outcome or partial allocation.

The 24-hour store is NOT a permanent consumed-capability registry. After its expiry no indefinite
response replay is promised; a new explicit Publish may allocate a new Publication, but never
clear/reuse the old capability. Lost-response recovery uses explicit revoke/new Publish/new Issue
with new keys. There is no background regeneration/republication/reissue. Issue's immutable
one-capability-per-Publication guard remains effective even after idempotency expiry.

## 4. Independent execution ownership and four Worker operations

Propose `aria_internal.preview_bootstrap_execution_claims` with exactly:
`job_id UUID PRIMARY KEY REFERENCES jobs(id) RESTRICT`,
`outbox_event_id UUID NOT NULL REFERENCES outbox_events(id) RESTRICT`,
`owner_backend_pid INTEGER NOT NULL`.
It is operational ownership, not a second content/capability aggregate or consumption record.
Use a distinct fixed session-advisory namespace `aria:preview-bootstrap:` + canonical Job UUID.
This separation is necessary because legacy `release_preview` checks only its own claim table/
session/Event, not profile. Shared claims would let the old release operation target P1 ownership.
Old release must find no P1 claim; it cannot release the distinct P1 advisory key.

Proposed fixed signatures; bodies/SQL are deliberately absent:

```text
aria_internal.claim_preview_bootstrap(job_id UUID, outbox_event_id UUID) -> JSONB
aria_internal.finalize_preview_bootstrap(job_id UUID, outbox_event_id UUID,
                                        manifest_ref TEXT, manifest_hash TEXT) -> VOID
aria_internal.fail_preview_bootstrap(job_id UUID, outbox_event_id UUID,
                                    error_code TEXT) -> VOID
aria_internal.release_preview_bootstrap(job_id UUID, outbox_event_id UUID) -> VOID
```

No raw token, content, free profile/table/predicate/SQL or tenant-context mutation is accepted.
Each mutation locks Job -> its Publication -> its Representation -> P1 claim row, then revalidates
all Job/Event/account/project/source/profile associations. Missing/mismatched input is denied;
no helper tries another identity, profile or event. Source metadata is ready/immutable; do not
grant source UPDATE merely to lock it. Storage/transformation never occurs inside these locks.

**Claim:** accept only queued/running P1 Jobs with the exact closed payloads/event and non-revoked
allocated/publishing Publication; source remains ready/hash-equal. A succeeded/ready coherent
binding returns already_completed without lock acquisition, mutation, storage work or issuance.
Failed/cancelled/revoked targets never execute again. Otherwise acquire the session advisory lock
non-reentrantly, install/replace only the exact P1 claim after ownership is acquired, mark the same
Job running, Publication publishing and allocated Representation preparing in one short commit.
Ready reusable Representation stays ready. Same-backend reacquisition is denied without leaking
a lock count. Live other-session ownership yields PREVIEW_PUBLICATION_IN_PROGRESS. A stale PID
alone does not authorize reclaim; the new session must actually acquire the advisory lock.

Claim returns exactly the existing private binding vocabulary, with 13 keys:
`job_id, publication_id, account_id, project_id, artifact_id, artifact_version_id, version_no,
representation_id, source_hash, source_ref, manifest_ref, manifest_hash, already_completed`.
UUID/hash/version encodings match P6; manifest_ref/hash are both NULL only for a non-ready
Representation. They must be the exact P6 namespace/hash for ready reuse. No capability fields.
Propose max_attempts=1 and logical attempt_count 0->1; same-ID ownership recovery does not increment
past 1, invent a Job retry or retime its original started_at. No attempt/budget policy is enabled.

**Finalize:** require current backend's exact claim AND live advisory ownership. Revalidate the
whole graph under locks, Job running, Publication publishing/non-revoked/unissued and exact P1
pair. Accept only P6's derived packet-manifest.json key and valid external Manifest digest. All
P4/P6 source/content/byte/provenance/size/read-back verification occurs in trusted Worker code
before this call; SQL cannot claim to verify private file bytes. If Representation preparing,
set ready and record ref/hash; if already ready, require exact equality and change nothing.
Atomically set the same Publication ready and Job succeeded, clear bounded error fields and
record server finished_at. Same-owned-session persistence replay after success may return only
when all final identities/ref/hash match; preserve its original timestamp. Any mismatch rolls
back everything. No finalization changes capability fields, consumption, source/current pointers.

**Fail:** require the same graph/session/live-lock proof. Exactly four permanent reasons:
PREVIEW_SOURCE_UNSUPPORTED, PREVIEW_SOURCE_INVALID, PREVIEW_DELIVERY_CONFLICT,
PREVIEW_PACKET_TOO_LARGE. Mark only the same running Job failed with server finished_at and NULL
error_detail; Publication remains inaccessible publishing, Representation preparing or immutable
ready. Same-owned-session/same-reason replay preserves timestamp; changed reason conflicts.
Transient storage/DB errors and raw exceptions are not accepted. Revoked/cancelled/succeeded
bindings cannot be turned into failed. No change to 0041's three-code allowlist.

**Release:** only the same Job/Event/backend's P1 claim and live P1 advisory ownership may be
removed/released. Validate the stored P1 graph, but permit cleanup after success/failure or
revocation/cancellation; cleanup is not a new domain transition. A foreign/missing claim is a
no-op with no disclosure and cannot unlock another session. Never acquire a lock to prove release
ownership. Ambiguous cleanup/commit discards the physical session; never pool a connection with
unknown advisory state. No legacy claim/lock or consumption row is touched.

## 5. ACL, profile constraints and installation review

Proposed Worker ACL: EXECUTE only these four new exact signatures; no direct P1-claim/Preview/
consumption writes, ownership, INSTALL/CREATE, role membership or BYPASSRLS. Existing unrelated
Worker privileges stay unchanged. PUBLIC/anon/authenticated and Core get no execution privilege
on the four Worker helpers or direct P1 claim access through this design.

Propose existing `aria_preview_runtime_owner` as restricted function-only owner, never owner of
the new claim table. Reuse reviewed NOLOGIN/NOINHERIT/NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/
NOCREATEROLE/NOREPLICATION attributes, fixed empty search_path, row_security=on, qualified fixed
objects. No CREATE on either schema, dynamic SQL, arbitrary relation names or ownership transfer
to Worker. New claim table ENABLE/FORCE RLS; helper owner alone gets SELECT/INSERT/UPDATE/DELETE
there, with P1-bound policies. No TRUNCATE, anonymous access or TTL job is proposed. A replaced
stale execution claim is distinct from the permanent append-only P5 consumption ledger.

Existing helper-owner column grants already cover P1 mutation/read fields; do not replace them
with table-wide/new parent writes. Propose additive P1-only owner SELECT/UPDATE policies on Jobs
restricted to the new job_type, plus owner Outbox SELECT restricted to its exact new event/channel.
Do not widen the old policies or alter shared Worker raw SELECT/RLS. Exact Core command-principal,
definer ownership/grants and authentication trust contract are separately proposed in section 8,
not inherited from Worker rights or approved merely by the owner's direction choice.
The existing WORKER-CROSS-TENANT-001 shared-credential compromise risk stays open: a compromised
Worker may target otherwise-valid P1 Jobs across tenants. Fixed graph checks are not complete
Production tenant isolation. No role redesign or claim that RLS independently authenticates
the Worker caller is inferred from this Local/Synthetic proposal.

0040's two old profile CHECKs currently reject P1. A future separately reviewed additive migration
must replace them with one closed pair constraint: exact old transformer+policy OR exact P1
transformer+policy, never the Cartesian product, arbitrary strings or mixed versions. Preserve
old rows, composite FKs, immutable triggers and Representation uniqueness. Do not edit 0040/0041
or amend their helper bodies/allowlists; update future ORM constraints consistently only after
source approval. P5 source remains byte-identical. This draft supplies no DDL or migration file.

Future installation must use the independently controlled temporary Installer, restricted final
function owner, PUBLIC revocation, exact grants and effective ACL/owner/RLS/strict ADMIN OPTION
assertions before commit; operational-role tests afterward are independent. Any proposed change
to Frozen P5 assertions needs separate review, not silent adaptation. Downgrade/cleanup SQL is
not designed here; no removal/relabeling of P1 data or consumed state is authorized. Actual SQL
source review, rollback contract and separate execution permission remain mandatory gates.

## 6. Transactions, issuance, revoke and recovery

States remain existing enums: Representation allocated->preparing->ready; Publication
allocated->publishing->ready or revoked; Job queued->running->succeeded/failed, with authorized
preready cancellation. Ready Representation is immutable; revoked Publication and terminal Job
are not reopened. A failed Job does not create a new Publication/Representation failure enum.

Runtime flow: short Claim commit -> verified exact 0100 source -> deterministic P4 transform ->
full P6 validation/cap -> create-or-verify/read-back packet then Manifest OUTSIDE a DB transaction
-> short Finalize commit -> Release/physical-session cleanup. Hold session ownership, not a DB
transaction, across storage. Conflict never overwrites; early staged objects are not publicly
accessible and grant no capability. Publish success still requires separate explicit Issue.

Issue must resolve the exact P1 Publication in the authenticated tenant/ownership boundary,
serialize its mutation with revoke, resolve idempotency before current-time expiry/state guards,
then require ready/non-revoked/unissued and explicit expiry strictly after server time sampled
after lock wait. Generate the existing 32-byte CSPRNG/Base64URL-no-padding token; atomically store
only SHA-256 token hash, expires_at, issued_at and safe idempotency reference. First response
discloses raw token only after confirmed commit; replay returns NULL/false. Never store/reconstruct
the token, use a URL/cookie/storage transfer, add an expiry default or issue a second capability.
This is one-time disclosure, not P5 consumption. Section 8 keeps raw token generation/disclosure
in Core memory and passes only its digest to SQL; these are proposed, not installed privileges.

Revoke locks the exact bound Job -> Publication, validates the P1 graph/ownership and safe replay,
then sets terminal revoked_at/status. If Publication preready and Job queued/running, cancel that
Job atomically without retiming an already-terminal Job. Do not steal/release its live Worker
claim, delete its Outbox or mutate Representation/files/source. If Finalize won, preserve success
and revoke the ready Publication; if Revoke won, Finalize/Fail must not override cancellation.
Issue never waits on Job after holding Publication. The final Core contract must use Job ->
Publication ordering for Issue/Revoke; neither operation later acquires Representation UPDATE
locks. P5 consumes under Publication lock only and never subsequently locks Job, so no reversed
cycle is introduced. Check all associations again after locks; capability expiry uses wall time.

P5 Preflight/Consume remain the only proposed delivery/consumption authority, unchanged. Revoke
or expiry blocks a new Bootstrap under their ordering. Consume first may commit and deliver
already verified bytes even if Revoke commits afterward; no live retraction of bytes is promised.
Issuing/revoking/publishing/recovering never deletes consumption or resets issued_at/token_hash.
P7's Worker helpers have no P5 ledger privilege additions and never invoke Consume.

Recovery matrix (all future evidence NOT RUN):

| Boundary | Required behavior |
|---|---|
| Allocation rollback/ambiguous response | No partial graph; replay committed safe IDs within idempotency window; no auto-new Job/token |
| Crash after Claim, before/during storage | Physical session ends; explicit same-Job/Event recovery may reacquire; verify/recreate missing deterministic output, never overwrite conflicts |
| Storage/validation failure before Finalize | No ready Publication/capability/consumption; known permanent failure via Fail; transient remains same-ID recoverable, no task retry |
| Finalize rollback or ambiguous commit ACK | Discard session; inspect via same-ID Claim; only committed coherent success returns already_completed; otherwise validate same staged bytes and finalize |
| Duplicate succeeded delivery | No state/timestamp mutation, re-copy, capability issue or Consume |
| Revoke while Worker alive / failure race | Cancellation/revoke persists; stale Worker cannot succeed/fail that Job; own-session cleanup only |
| Issue commits but response lost | Replay cannot recover token; explicit revoke/new Publication/new Issue with new keys only |
| P5 consumption exists, including after 24 hours | Remains consumed forever under current R2; no P7 path revives/reissues it; manual new Publication has a distinct identity/capability |
| P6 integrity mismatch on ready reuse | Fail closed; no source repair, ready overwrite, latest fallback or automatic re-publication |

## 7. Review traceability and remaining gates

| Requirement | Source / draft coverage | Future evidence — ALL NOT RUN |
|---|---|---|
| REQ-10333 | Owner exact P6 Freeze; status only in P6 section 8/parent | Frozen P6 sections 2..7 and P5 SQL fingerprints unchanged |
| REQ-10334 | Owner P7 independent operations/signatures; sections 2..4 | Exact identifier/closed payload/profile denial; same-Job ownership/duplicate/terminal behavior |
| REQ-10335 | Owner minimum ACL/lock ordering; sections 1,4,5,8 | Real Worker/Core positive and direct-write denial; old release cannot target P1; exact authority source review PENDING |
| REQ-10336 | Owner 0040 compatibility/P5 unchanged; sections 3,5 | Closed profile pairs, mixed-pair rejection, unique active Job race, legacy resolver/helper regression |
| REQ-10337 | Owner idempotency/revoke/recovery/no ledger bypass; sections 3,6 | Rollback/ambiguous ACK/revoke/issue/24h consumption races with real operational roles |
| REQ-10338 | Owner selected independent limited Core authority for design only; section 8.1/8.4 | Separate caller/definer owner; no direct Worker/anon/authenticated/Caller table rights or role-escalation path |
| REQ-10339 | Owner fixed Core operations; sections 8.2/8.3 | Exact actor/membership/tenant graph, DB role revalidation, fixed profile/fingerprint; no caller role or free SQL |
| REQ-10340 | Owner Core authority without consumed-capability bypass; sections 8.3..8.6 | Token never reaches SQL; confirmed-commit-only disclosure; replay/expiry/revoke/ledger retention; all NOT RUN |

The new claim namespace/table and section 8's exact Core roles/ACLs are consequential proposals,
not approved merely by design authorization. No unapproved choice is implemented. Exact P7 source
must be independently reviewed before contract Freeze; executable SQL needs another exact-source
review, and execution needs separate authorization again. No Browser/DB scenario or 0103
acceptance has run. Full ADR Freeze WAIT; all execution NO-GO.

## 8. Separate limited Core authority — exact r2 proposal

### 8.1 Principals and authentication trust

Propose `aria_preview_core_runtime` as a dedicated LOGIN caller with NOINHERIT/NOSUPERUSER/
NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/NOREPLICATION, no role membership/admin option and no object
ownership. Credential provisioning is out-of-band for a separately authorized disposable run;
no password, login or connection is created here. The existing Core adapter alone holds it.
No credential enters Browser/Preview/Worker/Outbox. Existing Core/Worker credentials are neither
renamed nor silently endowed with this authority. This is no new service or guest session.

Propose `aria_preview_core_owner` as a separate NOLOGIN role with the same restricted attributes
and NOINHERIT. It owns only the three new SECURITY DEFINER functions below, not tables, existing
functions or schemas; no role membership/admin option, schema CREATE or RLS bypass. Reuse of
the broad existing Worker-helper owner is deliberately not proposed for these Core operations.
Both principals get USAGE on public/aria_internal only as needed; no arbitrary schema capability.

Core verifies the existing JWT/Identity and resolves TenantContext before invocation. Helpers
receive subject/account/membership IDs from that trusted context, never from client actor/role
claims. They independently match `(membership.id, user_id, account_id)` and active status in
account_memberships, derive owner/admin/member from DB, and verify a visible same-account Project
(including existing `deleted_at IS NULL` visibility). No new account-status or entitlement rule
is invented. No role string, tenant GUC, Core assertion token or public JWT parameter enters SQL.

SQL is not a JWT verifier. Possession of the Core credential plus the trusted identity adapter
is an explicit boundary: a compromised Core caller could impersonate another valid Membership.
Membership/graph checks do not claim to prevent that compromise or independently establish
end-user identity. Public/Worker callers have neither this credential nor these EXECUTEs.
RLS policies constrain the definer's fixed P1 operations; they do not authenticate a JWT from
row data. No complete Production security acceptance follows from this Local/Synthetic design.

### 8.2 Three fixed Core function contracts

Proposed signatures only, NOT executable declarations:

```text
aria_internal.publish_preview_bootstrap(
  actor_id UUID, account_id UUID, membership_id UUID, project_id UUID,
  artifact_version_id UUID, idempotency_key TEXT, expected_source_hash TEXT
) -> JSONB

aria_internal.issue_preview_bootstrap_capability(
  actor_id UUID, account_id UUID, membership_id UUID, project_id UUID,
  publication_id UUID, idempotency_key TEXT, expires_at TIMESTAMPTZ,
  candidate_token_hash TEXT
) -> JSONB

aria_internal.revoke_preview_bootstrap_publication(
  actor_id UUID, account_id UUID, membership_id UUID, project_id UUID,
  publication_id UUID, idempotency_key TEXT
) -> JSONB
```

UUID/key arguments are required; reject NULL/invalid key with existing validation semantics,
without trimming/changing a key or introducing a numerical length default. The Application
key validator remains authoritative for accepted key syntax; SQL must not accept NULL/empty.
Profile/route/fingerprint/UUID allocation/server time are fixed/generated inside the functions;
no free request_hash, caller timestamp, role, predicate, table, namespace or SQL is accepted.
Core is granted only these three new EXECUTEs, not the four Worker helpers or P5 delivery helpers.
All three functions are VOLATILE SECURITY DEFINER with fixed empty search_path and row_security=on;
use schema-qualified fixed objects and no dynamic SQL. PUBLIC/default execution is revoked before
granting the exact Core caller. Trusted hashing dependencies are fixed/schema-qualified in the
later reviewed SQL source, never discovered by a caller-controlled schema/search path.
Each function must verify the exact restricted Core session principal; real-login tests, not
Superuser/SET ROLE success, prove the runtime boundary. Inside definer code current_user is the
restricted owner; it is not misrepresented as the end-user or session caller.

Publish result has exactly `publication_id, job_id, replayed`; Issue result exactly
`publication_id, issued, replayed`; Revoke result exactly `publication_id, replayed`. IDs are
canonical UUID strings and flags literal booleans. No token/hash/private path/content is returned
by SQL. Core maps these into section 2's Application results; Revoke's safe internal identity is
not a new public body. Denials use the existing bounded reason vocabulary without raw SQL detail.

`expected_source_hash` is a private adapter assertion, not an Application/API parameter or
synthetic authorization supplied by the Client. Core obtains it only from its controlled
version/hash synthetic allowlist. It may be NULL when only replay can be resolved; if present
it must be `sha256:` + 64 lowercase hex digits. Publish resolves authorized replay before source/
allowlist guards; a new allocation requires a non-NULL allowlisted value matching the ready
stored source hash. The Worker independently enforces its synthetic allowlist before reading/
transforming source. SQL alone cannot infer that data is synthetic from a valid hash; this
trusted Core assertion cannot replace the independent Worker invariant or authorize customer
content. Replay still validates the original target/binding, never a new latest source.

`candidate_token_hash` is required, exactly 64 lowercase hex digits. Core generates 32 CSPRNG
bytes and Base64URL-no-padding token in volatile memory, computes SHA-256 over that token's
UTF-8 bytes, and passes ONLY this digest. Token generation remains Application-owned, not a SQL
function returning raw secrets. Candidate hash is not part of idempotency request semantics.
Finite expiry must be representable by the existing timezone-aware Python datetime contract;
Core normalizes UTC, and SQL validates it and uses wall time after lock waits. No expiry default.

### 8.3 Transaction, fingerprint and disclosure semantics

The trusted Core adapter invokes one command per caller-controlled short transaction; all three
operations return provisional
metadata until confirmed commit. Failure rolls back all mutations and idempotency outcome.
No storage/Renderer/Provider call, capability consumption, transaction-internal network or new
Outbox event on replay occurs. Core must not return success/raw token on uncertain commit.

Every operation rechecks Membership/Project visibility initially and after its target lock wait,
before mutation/replay disclosure. No Membership/Project UPDATE privilege or new row-lock helper
is introduced. A concurrent membership/Project change after the last authorization read is not
claimed to synchronously retract an already-authorized in-flight operation; such a stronger
lifecycle contract is not silently invented. Existing outward membership semantics remain.

Publish uses section 3's exact allocation advisory key, then its exact idempotency row, then
plain Representation read/insert; existing Jobs/Representations are not row-locked in reverse order. Same-key
replay must bind the stored Publication/Job to the requested ArtifactVersion/account/Project/P1
pair, returning original IDs even after successful/failed/cancelled/revoked outcomes, without
reopening them. New allocation generates server UUIDs for Representation if absent, Job,
Publication, Outbox, correlation and idempotency record; inserts exactly the closed objects in
sections 2/3. Initial status/counts/max_attempts are those proposed there; available/created times
come from server clock. No Core UPDATE of Representation or source/current-pointer mutation.

Issue/Revoke first identify an authorized P1 target, then lock Job -> Publication, then reserve/
read their exact operation-scoped idempotency row. Do not later lock Representation or Job in
reverse order. Revalidate the full tenant/Project/Artifact/source/P1/Job-payload binding; Issue
requires Job succeeded/Representation ready before first issuance. Both recheck authorization
after waiting and before replay. Cross-target replay is conflict, not permission to probe a
second tenant. Different operations retain distinct route namespaces, as in section 3.

Each function computes its own request_hash as SHA-256 of the exact canonical-JSON bytes from
the existing application convention. Keys are `account, actor, operation, project, values`;
operation is the fixed string publish/issue/revoke, not an argument. Values are an ordered array:
Publish `[artifact_version_id,T,D,M]`; Issue `[publication_id,UTC_expiry,T,D,M]`;
Revoke `[publication_id,T,D,M]`. Here T/D/M are the three fixed literals in section 2, not new
parameters. UUIDs are lowercase canonical strings; UTC_expiry is exactly
`YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (six fractional digits). All fingerprint values are constrained
ASCII; the SQL source must produce the same fixed, sorted-key, compact bytes as the Application,
not rely on jsonb::text spacing/order. Existing pgcrypto from 0000 supplies hashing; no extension
is installed here. No raw token, candidate hash, allowlist assertion or time-of-execution enters
the fingerprint. This contract is not permission to introduce a generic hashing/JSON SQL API.

Idempotency uses the existing UNIQUE scope and 24-hour policy. Only the exact expired scope may
be removed/re-reserved; no cleanup sweep. Persist only response_ref `{publication_id}` and existing
internal status metadata 202/201/204 for Publish/Issue/Revoke respectively; these are not new HTTP
endpoint decisions. Verify saved target and, for Issue replay, original immutable expiry as well
as request_hash; caller-supplied digest cannot suppress changed-request conflict. Incomplete or
inconsistent stored outcomes fail closed. TTL never extends on replay and never touches P5.

For first Issue, under the lock require unissued fields, ready/non-revoked target and expiry
strictly after fresh server time. Atomically write exactly the candidate digest, expiry and
server issued_at plus safe outcome; return issued=true/replayed=false. On replay return
issued=false/replayed=true, without changing issued fields. The fresh candidate/raw token must
be discarded. Core discloses its in-memory token ONLY when the returned Publication matches,
flags are exactly first-success and the outer commit is confirmed. Any error, contradictory
result, serialization failure, replay or ambiguous ACK discards it without disclosure. A new key
on an already-issued Publication returns PREVIEW_CAPABILITY_ALREADY_ISSUED, even after 24 hours
or P5 consumption. No DB read/response can reconstruct the original raw token.

Revoke follows section 6, atomically cancelling only a preready queued/running P1 Job and marking
its Publication revoked with server time. Repeated authorized revocation is a no-op on business
timestamps, with safe replay/outcome persistence. It does not clear issued fields, retry a Job,
mutate Representation, steal session claims, delete Outbox/objects or read/delete P5 consumption.
Consume/Revoke ordering and One-shot lost-response semantics remain exactly P5/P6/D6.

### 8.4 Exact proposed owner ACL and RLS boundary

Caller has no direct business-table privileges. The following explicit definer-owner column
grants are proposed, not applied; unspecified DML, GRANT OPTION and ownership are denied:

| Relation | `aria_preview_core_owner` minimum proposed access |
|---|---|
| accounts | SELECT(id) only |
| profiles | SELECT(user_id) only; no display/profile/customer fields |
| account_memberships | SELECT(id,account_id,user_id,role,status); no writes |
| projects | SELECT(id,account_id,deleted_at); no UPDATE for locks |
| artifacts | SELECT(id,account_id,project_id) |
| artifact_versions | SELECT(id,account_id,project_id,artifact_id,status,artifact_hash,version_no); no storage/content/current-pointer writes |
| preview_representations | SELECT(id,account_id,project_id,artifact_id,artifact_version_id,source_hash,transformer_version,delivery_policy_version,status,manifest_ref,manifest_hash,created_by); INSERT(id,account_id,project_id,artifact_id,artifact_version_id,source_hash,transformer_version,delivery_policy_version,status,created_by); no UPDATE/DELETE |
| preview_publications | SELECT(id,account_id,project_id,artifact_version_id,representation_id,publish_job_id,status,created_by,revoked_at,token_hash,expires_at,issued_at); INSERT(id,account_id,project_id,artifact_version_id,representation_id,publish_job_id,status,created_by); UPDATE(status,revoked_at,token_hash,expires_at,issued_at); no DELETE |
| jobs | SELECT(id,account_id,project_id,job_type,status,payload_ref,finished_at); INSERT(id,account_id,project_id,job_type,status,payload_ref,attempt_count,max_attempts,idempotency_key,correlation_id,available_at); UPDATE(status,finished_at) for authorized cancellation only |
| outbox_events | INSERT(id,account_id,aggregate_type,aggregate_id,event_type,delivery_channel,payload,status,attempt_count,available_at); no SELECT/UPDATE/DELETE |
| idempotency_records | SELECT/INSERT(id,account_id,actor_id,route_key,idempotency_key,request_hash,response_status,response_ref,expires_at); UPDATE(response_status,response_ref); DELETE only exact expired P1 scope under RLS/function guards |
| old/new execution claims, P5 consumption ledger, content/Usage/price tables | NONE; no Core helper EXECUTE on Worker/consumption functions |

Created timestamps use existing defaults; no sequence grants are needed for generated UUIDs.
UPDATE column ACLs needed for Issue/Revoke locks are restricted to the listed target columns;
do not add Project/Membership/Representation UPDATE or table-wide grants. Trusted function branches, existing
immutability triggers, RLS and transaction predicates constrain what the restricted owner can
do with those rights. A definer role can see its authorized rows across tenants internally;
this is not a claim of per-request identity enforcement by ACL alone.

Add role-specific policies, never replace existing policies. Base identity/Project/source metadata
SELECT policies permit only this NOLOGIN owner to read the listed columns for fixed lookup, with
no new content access or writes; helpers apply exact actor/account/Project predicates. Do not
create circular RLS dependencies by requiring a not-yet-created Representation to read its source.
Preview metadata reads/INSERTs must follow the stored source graph and fixed P1 pair; Jobs are P1-only,
Outbox INSERT is only the exact P1 event/channel/closed payload for that Job; initial rows cannot
be inserted ready/issued. Publication UPDATE and Job cancellation remain P1-only under helper
guards. Idempotency policies accept only the three fixed P1 route forms with canonical Project
UUID, same-account Project and actor Membership association; DELETE additionally requires expired
server time. Code constrains the exact actor/account/Project/key tuple. No prefix wildcard grants
access to other modules' records. Existing ENABLE RLS remains; no broad FORCE/role-policy rewrite
of old tables is proposed. Owner is never their owner and remains NOBYPASSRLS.

Do not grant this owner EXECUTE on arbitrary user-defined SECURITY DEFINER functions. Pre-commit
inspection must include effective PUBLIC/default/role/SET ROLE/ADMIN OPTION paths and reject
unreviewed privileged execution, schema CREATE or business-table rights. Unexpected inherited
defaults fail the installation review; do not globally revoke unrelated PUBLIC privileges or
weaken Frozen P5 assertions to force a PASS. Worker/anon/authenticated must have no effective
access to the three Core operations, caller role or Core-owner authority. No role memberships
or SET ROLE chain connect Core caller, Core owner, Worker owner and Installer. Effective ACLs,
function ownership/row_security/search_path and RLS are asserted before any future commit.

### 8.5 Failure, retention and installation boundary

The restricted owner cannot UPDATE issued_at/token_hash to NULL or a different issued value:
existing immutable issued-field triggers and helper guards forbid it. Its function code never
touches P5 ledger or grants. Core cannot consume a capability to test it; only P5 delivery can.
An expired/deleted idempotency row cannot restore an issued or consumed capability. New explicit
Publication/Issue use new identities/keys; no automatic bootstrap/recovery/publication occurs.

Bounded failure codes and no-leakage rules are inherited from sections 4/6 and P6. Log neither
raw token nor candidate digest, private hashes/refs, request body, membership attribution or
raw DB exception. Application response contains raw token only on the confirmed initial Issue;
idempotency stores no full token-bearing response. Credential and token values are never passed
as process arguments or written to reports. There is no new audit payload or public error code.

This r2 proposes role attributes/signatures/column grants/policy intent, not executable SQL or
its actual PostgreSQL compilation. Installation, guarded rollback and precise policy/function/
assertion source require separate review. Installer remains independent and temporary; it is
not the final definer owner. Future tests must log in as the actual limited Core/Worker roles,
prove both positive calls and negative direct table/role/legacy/profile paths, and disclose all
skips. Source/contract review is not installation or a full Production security assessment.

### 8.6 Core authority evidence matrix — ALL NOT RUN

| Case | Required future observation |
|---|---|
| Exact Core login vs Worker/anon/authenticated/unrelated principal | Three Core calls allowed only for approved caller; direct table access/role escalation denied |
| Valid JWT context / forged actor-membership-role-account-target combinations | Trusted Core precondition plus independent DB active-Membership/P1 graph checks; no caller role override |
| Owner/Admin/Member Issue/Revoke and foreign/soft-deleted Project | Existing authorization matrix, safe not-found, no cross-tenant existence probe |
| Source ready/allowlist binding and replay after source guard changes | No new unallowlisted allocation; original authorized replay before current guards; independent Worker synthetic check |
| Concurrent same-key Publish/Issue, changed target/expiry, expired idempotency | One atomic original outcome, no duplicate effects/disclosure, no indefinite replay promise or ledger cleanup |
| Same fingerprint inputs in Core and SQL, timezone/microseconds variations | Exact canonical bytes/hash; no candidate digest or execution time in fingerprint |
| Issue rollback/commit ambiguity/response loss/replay | No raw token in SQL/persistence/logs; disclosure only on confirmed first commit; replay discards candidate |
| Revoke vs Issue/Finalize/P5 Consume; consumed capability after 24 hours | Approved lock order/atomicity, terminal issued/revoked/consumed state never reset |
| Effective ACL/RLS/default privileges and independent definer ownership | Column-limited rights and fixed operations only; unreviewed privilege paths stop install before commit |

P7 r2 is ready for exact-source contract review, NOT FROZEN. The owner approved only the Core
authority direction; the exact role names, signatures, ACL/policy/claim choices and lifecycle
details in this document all remain proposals. No SQL, Migration, runtime, dedicated test or
Browser Proof has been created/executed. Full ADR Freeze WAIT; Hosted/customer/Commit/Push NO-GO.
