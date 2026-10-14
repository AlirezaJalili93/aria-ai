# ADR-089 — Local Preview Publication and Version-bound Capability

**Status:** Partially accepted — Local/Synthetic database authority approved; full delivery gate pending

**Date:** 2026-10-12

**Planned increment:** `0102-local-preview-publication-and-capability`

**Implementation:** Local/Synthetic SQL gate authorized; no completed publishing/browser increment.

## Sources and precedence

- Current owner's 0102 review: dedicated Preview Storage/Namespace and Authorization Matrix are
  approved/frozen. A URL-route bearer capability is conditionally allowed only for Local/Synthetic
  verification with explicit security controls. It is not a Production authorization contract.
- Owner's subsequent instruction to continue authorizes completing this delivery-representation
  design. It does not pre-approve the proposed schema, lifecycle or implementation below.
- [Engineering Backlog](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit),
  EP-F3 / `BE-F3-02`, `BE-F3-03`, `SEC-F3-04`; read 2026-10-12.
- [Engineering Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit),
  Sprint 3 section 14.4: separate registrable domain, no Core cookie/backend secret, strict CSP,
  static/client-only runtime, scoped assets and immutable ArtifactVersion; read 2026-10-12.
- [Security and Threat Model](https://docs.google.com/document/d/1dtxr2XhtwNt4hcCaJXOlfQa5AEBKi1RRLCKI551O3Yc/edit),
  `TB-08`, `T-PRV-01..05`, `T-SH-01`; read 2026-10-12.
- [ADR-086](ADR-086-artifact-version-foundation.md),
  [ADR-087](ADR-087-synthetic-artifact-generation-runtime.md),
  [ADR-088](ADR-088-preview-isolation-architecture.md).
- Browser reference: [Referrer-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy),
  [Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control),
  [iframe](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe), checked 2026-10-12.

Canonical sources require publication, immutable routing and limited access; they do not specify
Preview capability transport, publication schema, expiry duration or command vocabulary. Proposed
choices below do not become requirements until the owner freezes them.

## Accepted decisions

### Dedicated Preview storage

Preview delivery uses a dedicated storage boundary and exact-version namespace. A source Artifact
storage reference is not a public delivery URL. Public callers receive no direct private-storage
credential or general storage access. Local proof introduces no new hosted/deployable service.

### Authorization matrix

| Command | Active Owner | Active Admin | Active Member |
|---|---|---|---|
| Publish | allow in visible tenant/project | allow in visible tenant/project | allow in visible tenant/project |
| Revoke | any visible project publication | any visible project publication | own publication only |

Authorization is enforced in Application/Repository; role or tenant claims supplied by the client
are not authority. Missing, cross-tenant and non-visible resources use the existing safe-404
boundary without an out-of-tenant existence probe. Exact Account/Project/Artifact/ArtifactVersion
association must be verified before publication.

### Isolation and activation boundary

The ADR-088 sandbox, separate registrable test sites, hash CSP, System Font Only, absent ACAO and
manifest-limited CORP policy remain frozen. No additional sandbox permission, messaging bridge,
Core session or API credential is introduced. Only explicitly selected synthetic, ready
ArtifactVersions are eligible for local verification. Customer content, hosted/CDN publishing,
Production URLs and guest sharing remain deferred.

## Proposed capability controls — pending owner freeze

1. Capability grants read-only access to one exact publication and ArtifactVersion. It never
   authorizes Core API calls, source-storage listing, mutation or access to another version.
2. Reuse the reviewed token construction as a proposed Preview-specific contract: 32 CSPRNG
   bytes, Base64URL without padding, SHA-256 of the public token's UTF-8 representation. Store only
   a unique hash. Raw token disclosure occurs once in the initial creation result; management
   queries and idempotency persistence must not retain or reconstruct it. Scope Share tokens and
   Preview tokens are separate authorities; no implicit conversion is permitted.
3. `expires_at` is supplied explicitly, must be in the future and is checked on every resource
   request using server time. No duration default is proposed. Revocation is terminal and checked
   synchronously; reissue creates a new capability. Cleanup invalidates all local proof access.
4. Every HTML, JS, CSS and image request must validate the capability, exact Host, publication,
   ArtifactVersion and verified Manifest path before any bytes are served. UUIDs, URL path,
   `Referer`, `Origin` or a prior successful document read do not substitute for authorization.
5. Unknown, malformed, expired, revoked or mismatched capabilities give the same outward safe
   not-found result. Traversal, unknown files, another Host/version and implicit latest-version
   fallback fail closed. The externally served file set excludes private manifests/checkpoints.
6. Send `Referrer-Policy: no-referrer` and `Cache-Control: no-store` on successful and denied
   Preview responses, including subresources. The parent iframe also suppresses referrer
   information. These controls do not claim to erase browser history or hide request-targets.
7. Local listeners bind only to loopback. Use a disposable browser profile and direct loopback
   transport with no external proxy/CDN, third-party script, analytics, telemetry exporter,
   persistent browser storage, service worker, user-facing copy/share flow or saved bookmark.
   Request URLs, headers, bodies and browser/CDP traces must not enter persistent reports/logs.
8. Treat raw token, token hash and capability-bearing URLs as prohibited log/trace/error/metric
   data. Do not depend on late regex redaction of raw request-targets. Use allowlisted outcomes,
   counts and internal operation IDs; IDs are not metric labels. Errors use bounded reason codes.
9. Browser history, extensions and debugging interfaces can still observe bearer URLs. This
   residual risk is accepted only for disposable synthetic local testing; passing the local gate
   does not authorize the same transport for Production or customer assets.
10. Local execution must fail closed if synthetic provenance, direct loopback transport,
    non-persistent diagnostics or isolated profile requirements cannot be established. The gate
    records results without storing tokens, URLs or artifact content.

## Proposed publication consistency — pending owner freeze

Publication selects an exact ready ArtifactVersion and verifies the private Manifest hash and every
file's size/checksum. The source bytes remain unchanged. The separately versioned Preview
representation permits only the transformations specified below, before its manifest is committed.
Delivery serves the resulting verified bytes unchanged. Do not re-render, re-invoke a Provider,
mutate the Artifact current pointer or repoint an existing publication when a newer version exists.

Create-or-verify copy permits recovery with the same publication identity: matching bytes can be
reused, mismatching bytes fail closed. No document becomes accessible until all required files
are verified and a durable publication/access outcome commits. Failed copying or DB commit
leaves the publication inaccessible; staged objects remain recoverable or discoverable for
cleanup, never falsely reported as success. External storage work does not hold a DB transaction.
The detailed lifecycle, identities and error proposals below remain subject to owner freeze.

Mutating commands require the existing tenant authorization and idempotency boundary. Concurrent
requests using the same key must commit one outcome through a DB guard. Replay cannot disclose a
raw token again; lost-response recovery requires revocation and explicit creation with a new key.
The proposed cardinalities below require approval before schema implementation.

## Blocking access-transport finding

The actual 0100 builder emits root-relative URLs:

- `scripts/artifact-generation/build-static-bundle.mjs`: `/assets/styles.css` and
  `/generation-fixtures/media.svg`.
- `packages/generation-renderer/src/renderer.tsx`: navigation uses canonical `target_path`, such
  as `/contact`, directly.

If only the document URL is `/preview/<capability>/index.html`, these URLs request paths outside
the capability prefix. Publishing those paths without capability validation would expose bytes;
denying them would break loading/navigation. A prior document authorization is insufficient.

ADR-088 prohibits rewriting Artifact bytes at delivery. Therefore transparent HTML/CSS URL
rewriting, injecting a base element, cookies/sessions, CDP header injection or weakening access
checks must not be silently added to claim this path works.

The owner authorized continuing the design of a separately hashed Preview delivery representation.
The following contract resolves relative paths explicitly for nested pages and excludes aliases
and query routing. It proposes a narrow addition to ADR-088: transforming a separate derivative
before publication; source bytes and request-time delivery remain immutable. Approval to design
this addition is not approval to implement it.

No access transport is marked Frozen by this ADR. A 0101 synthetic handcrafted HTML proof is not
evidence that the real 0100 Artifact bundle can be published using a capability prefix.

## Detailed delivery-representation proposal

Every rule in this section is a **Proposed Decision**, pending owner freeze. It specifies intended
behavior without creating a runtime service, schema file, migration or new dependency.

### Identity, cardinality and private metadata

Two durable metadata objects separate content identity from access lifecycle. Capability material
is stored on its Publication; it does not require a third table or an independently mutable aggregate.

| Object | Proposed identity and cardinality | Meaning |
|---|---|---|
| PreviewRepresentation | UUID; unique `(account_id, artifact_version_id, transformer_version, delivery_policy_version)` | One verified, immutable derivative of the exact source |
| PreviewPublication | UUID; many publications may bind the same ready representation | Tenant-owned access lifecycle and explicit publishing command |

Representation and Publication retain `account_id`, `project_id`, exact `artifact_version_id`,
creator attribution, explicit lifecycle status and timestamps. Representation retains the exact source `artifact_hash`,
private delivery manifest reference/hash and versioned transformation/policy identities. Publication
retains `representation_id`, unique `publish_job_id`, `created_by`, creation time and nullable
`revoked_at`. Publication also holds nullable `token_hash`, `expires_at` and `issued_at`: all three
are absent before issuance and all three present afterward, with a DB consistency constraint.
Non-null `token_hash` values are unique. At most one capability is issued per Publication;
issuance material cannot be cleared, rotated or replaced. Revocation uses the Publication's terminal
state and timestamp. No raw token/URL, canonical AST copy, latest-version pointer or customer title is
stored in these metadata objects. Fields are private; public response projection is independent.

Account/Project/ArtifactVersion/Representation/Publication/Job associations must be enforced through
composite foreign keys, not just RLS. Creator and resource FKs use `RESTRICT`; hard deletion of
these records is prohibited. RLS/runtime roles follow the existing tenant boundary; no public or
anonymous direct SELECT grant is introduced. Exact grant/helper DDL must be reviewed in the
implementation ADR before any migration is applied.

Immutable representation identity excludes publication access material, raw tokens, Host/port and expiry. Thus a
new Publication may reuse the same representation without modifying its files or hashes. A versioned
transformer/policy change creates a different representation; it never modifies a ready one.

### Source profile and permitted transformation

`preview_delivery_transformer_v1` supports only the verified synthetic 0100 static bundle:
`artifact_manifest/v1`, `generation_ast_schema/v1`, Renderer `0.1.0`, Design Tokens `0.1.0`, and
the exact declared HTML/CSS/SVG files. A Next.js prototype bundle or JavaScript-bearing source is
not silently accepted under this profile. ADR-088's independent JS isolation regression remains
required; supporting JS publication needs a later source-profile contract.

Source Manifest and files must pass identity, hash, size, path, canonical AST and runtime-security
validation first. The transform does not sanitize an arbitrary website into an accepted Artifact.
Malformed or unsupported source fails before any publication becomes accessible.

The transformation allowlist is limited to:

1. Rewrite `a[href]` only when its decoded value is an exact canonical `pages[].path`, to the
   corresponding generated page file. Preserve anchor text, node identity and accessibility
   attributes. Unknown pages and fragment/query navigation are rejected for this profile.
2. Rewrite `link[rel=stylesheet][href]` only for the declared bundled stylesheet and `img[src]`
   only for an exact verified Manifest image file. URLs become relative to the current page file's
   directory. Duplicate/conflicting attributes, ambiguous markup and unsupported URL-bearing
   attributes/nodes fail closed. Text that happens to contain a URL is never rewritten.
3. Remove the exact Workspace-only `@import "@aria/design-tokens/tokens.css";` from the bundled
   stylesheet only after verifying that the source builder's exact token stylesheet is already
   included. The import is a packaging directive, not permission to fetch a path. This is not a
   generic CSS import flattener. Unexpected imports, CSS resource fetches or font rules fail closed,
   including escaped/comment-obfuscated equivalents under CSS syntax parsing.
4. In the private Preview CSS derivative only, replace the verified body-font primitive declaration
   with `--primitive-font-family-body: system-ui, sans-serif`. Reject a source with unexpected font
   declarations rather than guessing. Core tokens, Renderer source and source Artifact bytes
   remain untouched. No font resource, `@font-face` or font preload is introduced.
5. Owner clarification during implementation: remove only React's `link[rel=preload][as=image]`
   hint whose root-relative `href` is a declared verified Manifest image. The ordinary `img`
   remains and loads through its mapped relative path. Font hints, external destinations,
   undeclared images and additional hint properties remain unsupported. Source bytes are untouched.

SVG bytes are preserved exactly after safety validation: this profile permits no active script,
foreign content or external resource reference. No `<base>`, inline style/script, executable code,
event handler, form action, session/cookie code or access token is injected.

HTML and CSS transformations use structured parsing with deterministic serialization; global
regex replacement is prohibited. Parsing/serialization must preserve the supported DOM semantics,
Persian text and escaping. Parser selection is an Infrastructure implementation choice only within
the approved dependency/stack policy; any new dependency requires an explicit pinned proposal.
Changing allowed transformations requires a new transformer version.

### Explicit relative-URL algorithm and serving route

Proposed local read route:

```text
GET|HEAD http://<exact-configured-preview-host>:<loopback-port>/p/<raw-capability>/<manifest-file>
```

The exact configured Host binds one source ArtifactVersion, preserving ADR-088's one-version
origin; multiple Publications of that same version may share it. No other version is served at
that Host. The Host is separate from Core's registrable test domain and conveys no tenant authority. Public
Production domain, TLS/CDN topology and guest links remain deferred.

Canonical page-to-file mapping is fixed:

```text
/                  -> index.html
/contact           -> contact/index.html
/services/design   -> services/design/index.html
```

Let `s` be the current page's file and `t` the verified target file. Compute
`posix_relative(dirname(s), t)` using only validated ASCII Manifest segments. Preserve exact target
case. Every generated reference must resolve back to `t` under the same origin and `/p/<cap>/`
prefix. Verify this invariant with WHATWG URL resolution for multiple synthetic capability values
and every page depth. A reference resolving above the prefix or to another file is rejected.

| Source page file | Target | Persisted relative reference |
|---|---|---|
| index.html | assets/styles.css | assets/styles.css |
| contact/index.html | assets/styles.css | ../assets/styles.css |
| services/design/index.html | generation-fixtures/media.svg | ../../generation-fixtures/media.svg |
| contact/index.html | canonical `/` | ../index.html |
| index.html | canonical `/contact` | contact/index.html |
| services/design/index.html | canonical `/contact` | ../../contact/index.html |

The raw capability exists in the transient request URL, not in persisted references. Browser URL
resolution removes generated `..` segments before requesting the canonical Manifest path. Those
generated relative references are not permission for raw traversal requests: the delivery handler
rejects dot-segments, percent-encoded path aliases, backslashes, duplicate separators, query strings
and any noncanonical request-target. The route parser must validate before a filesystem join.
Do not use a normalizing URL parser to turn a raw traversal request into an authorized request.

Only explicit file routes are supported. No directory-index aliases, automatic redirect,
extensionless route, trailing-slash fallback, SPA fallback, latest-version redirect, wildcard Host
or directory listing is introduced. The initial transient URL ends in `/index.html`. Navigation to
existing nested pages uses explicit file paths. Content negotiation cannot select another file.

GET/HEAD validate access identically; HEAD returns no body. Other methods cannot mutate state and
return the existing method-not-allowed semantics. Invalid capability, unavailable/revoked publication,
expired capability, wrong Host/version association and unavailable file remain outward-safe
`404 RESOURCE_NOT_FOUND`, with the same no-store/no-referrer boundary. Capability authorization
occurs on each resource, including direct asset access. The bearer route retains the previously
documented local-only history/debugging risk; it is not made secret from the browser by relative URLs.

### Private delivery Manifest and immutability

Proposed `preview_delivery_manifest/v1` contains:

```text
manifest_version
representation_id
source:
  account_id, project_id, artifact_id, artifact_version_id, version_no, artifact_hash
contracts:
  source_manifest_version
  generation_ast_schema_version
  transformer_version
  delivery_policy_version
pages[]:
  canonical_path, file_path
files[]:
  path, media_type, size_bytes, sha256, source_sha256
```

Only these fields are accepted; nested records are closed. Paths/files are sorted by exact ASCII
path, object keys are sorted recursively, arrays preserve that specified order, JSON uses exact
UTF-8 bytes without BOM/insignificant whitespace and numbers are nonnegative integers. SHA-256 of
the exact serialized bytes is stored outside the Manifest; the Manifest never includes its own
hash. `source_sha256` records the original bytes for each copied/transformed file. No canonical
AST duplication, token, Host, storage credential, URL, prompt or response belongs in this Manifest.

The delivery Manifest is private metadata, not a served file. Source and delivery hashes are distinct;
no code compares a transformed file against the source hash and calls it unchanged. Rebuilding the
same representation identity with the same source and versions must produce identical Manifest and
file bytes. Only unmodified files must retain their source hash. Serve reads verify the delivery
file size/hash before writing response headers or bytes; mismatch fails closed.

Dedicated private namespace proposal:

```text
preview/{account_id}/{project_id}/{artifact_version_id}/{representation_id}/
  files/<exact-manifest-file>
  delivery-manifest.json
```

These keys are server-generated private references; the route does not expose or concatenate them
from a caller-supplied storage path. The namespace cannot be anonymously read/listed. Browser-facing
route authorization remains required even for manifest-verified synthetic files with CORP cross-origin.

### Commands, access lifecycle and one-time disclosure

Long-running verification/transformation/copy runs in the existing Worker artifact. Internal,
explicit commands and controlled loopback harness are proposed for 0102; no product/public
management endpoint, hosted listener or automatic Generation-to-Publish chaining is introduced.

Separate operations avoid putting a raw token into an asynchronous Job/Outbox result:

| Operation | Proposed behavior |
|---|---|
| PublishPreview | Exact tenant/project/ArtifactVersion + Idempotency-Key; allocate Publication, Job, Outbox atomically; return safe identities only |
| IssuePreviewCapability | Explicit command after Publication ready; explicit future expiry; generate and return raw token once after its own atomic capability/idempotency commit |
| RevokePreviewPublication | Existing approved ownership matrix; terminal state/timestamp update invalidates its capability atomically; repeated revoke idempotent |

Proposed Publish identities:

```text
job_type         = preview_publication
event_type       = preview.publication_requested.v1
delivery_channel = job_queue
celery_task      = aria.preview.publish.v1
envelope         = message_version, outbox_event_id, job_id
```

Queue/Outbox contains no token, URL, file bytes, Manifest contents or customer data. The same Job
resolves pinned tenant/project/source/version/transformer/policy identities from PostgreSQL.
Automatic task retry and Generation-to-Publish chaining remain disabled; explicit recovery uses
the same Job, Publication and Representation identity.

Publication lifecycle proposal is `allocated -> publishing -> ready -> revoked`. A pre-ready
Publication may also be explicitly revoked; finalization then fails closed. Revoked is terminal.
Representation lifecycle is `allocated -> preparing -> ready`; ready content is immutable.
Known permanent preparation failure fails the Job without exposing the derivative. Recoverable
storage/commit failure keeps a non-ready preparation recoverable through the same identities.
It does not create a fictitious ready/failed intermediate artifact or start another render.

At most one queued/running publish Job targets a Representation, enforced by PostgreSQL. Same-key
Publish replay precedes state guards and resolves its original Job/Publication. New-key publication
may reuse a ready representation; if preparation is already active, it receives the proposed
conflict below. Creation of Job, Publication and new Representation references is atomic.

For issuance, propose the same frozen ownership boundary as Publish/Revoke: an active Owner/Admin
may issue against a visible ready Publication; a Member may issue only against a Publication they
created. This issuance permission is a **new proposed decision**, not inferred approval. One
capability per Publication has a DB compare-and-set guard over unissued fields under the Publication
row lock; token hash uniqueness is a final collision guard. Same-key/same canonical request replay returns
the same safe identity with `token=null`, `token_available=false`. A changed request conflicts;
a different key cannot issue a second capability on that Publication. Lost-response recovery is
revoke, new explicit Publication (reusing the ready Representation), then new issuance/key.
No full token-bearing response is stored in any idempotency record.

Access predicate at each authorization point:

```text
publication.status == ready
AND publication.revoked_at IS NULL
AND publication.token_hash IS NOT NULL
AND server_now < publication.expires_at
AND exact associated representation.status == ready
AND all tenant/project/source/version associations agree
AND requested file is in the verified delivery Manifest
```

Revoke and read authorization serialize through a short repository boundary: a read authorized
before revoke commits may finish; a new read authorized after revoke commits must fail. Revocation
cannot retract bytes already delivered to the browser. Storage/network work must not hold a DB
transaction indefinitely or weaken the guard to claim stronger revocation semantics.

### Copy/finalization/recovery boundary

```text
atomic allocation: same Publication + Job + Outbox + pinned Representation
  -> Worker guard and active-representation guard
  -> verify exact source Manifest/files
  -> deterministic transform; validate graph, fonts and runtime policy
  -> create-or-verify files; read-back verify
  -> create-or-verify delivery Manifest last; read-back verify
  -> atomic DB finalization:
       revalidate exact source/representation/publication bindings and non-revoked state
       persist Manifest reference/hash; Representation ready
       Publication ready; same Job succeeded
  -> explicit capability issuance
```

Failed finalization exposes no ready Publication and no capability. Recovery verifies the durable
derivative; it may deterministically recreate missing preparation output but does not invoke Provider
or Renderer. Existing mismatched objects are never overwritten. Revoke racing finalization cannot
be undone by recovery. No ready object is physically deleted by 0102; operational GC/retention is a
separate contract. Disposable local proof data/profile is cleaned after its test run.

Proposed bounded reason codes (internal commands, not yet public API HTTP contracts):

| Code | retryable | Meaning |
|---|---|---|
| ARTIFACT_VERSION_NOT_READY | false | Visible exact source is not ready |
| PREVIEW_SOURCE_UNSUPPORTED | false | Source profile or structure not supported |
| PREVIEW_SOURCE_INVALID | false | Source identity/hash/reference/security validation failed |
| PREVIEW_PUBLICATION_IN_PROGRESS | false | Another active Job owns this representation |
| PREVIEW_DELIVERY_CONFLICT | false | Immutable delivery bytes disagree with recorded bytes |
| PREVIEW_STORAGE_ERROR | true | Known transient storage failure; controlled recovery only |
| PREVIEW_FINALIZATION_RECOVERABLE | true | DB finalization did not commit; same identities resume |
| PREVIEW_PUBLICATION_REVOKED | false | Authorized internal command targets terminal Publication |
| PREVIEW_CAPABILITY_ALREADY_ISSUED | false | Different key attempts second issuance |

Existing `VALIDATION_FAILED`, `IDEMPOTENCY_CONFLICT`, safe `RESOURCE_NOT_FOUND` and membership
semantics are reused where applicable. `retryable=true` is metadata for a controlled command, not
authorization for a scheduler or automatic retry. Unknown errors cannot include raw paths/content.

### Detailed acceptance matrix — required before implementation completion

| Gate | Expected result |
|---|---|
| Same source and transformation versions, same representation ID | Identical derivative bytes and Manifest hash |
| Source hash before/after preparation/publication/read/revoke | Unchanged |
| Root, one-level and two-level pages | CSS/images/navigation resolve under the same capability |
| Same Representation under two distinct capabilities | Same file hashes; no token inside files/Manifest |
| Root-absolute link, protocol-relative URL, unknown page, CSS escaped fetch | Fail closed |
| Direct CSS/SVG read without valid capability | Safe not-found |
| Raw/encoded traversal, alternate query/route/Host, another version | Fail closed |
| Private delivery/source Manifest and checkpoints | Not served |
| Workspace CSS import / Preview font | Exact import removed; fixed system stack; zero external/font request |
| Concurrent same-key Publish and issuance | One original outcome; DB guards; token disclosed once |
| Two Publish Jobs for a preparing Representation | At most one active Job |
| Copy failure / DB finalization failure / restart | No early access; same IDs recover; no Provider/Renderer call |
| Revoke racing finalization or future resource read | Revocation persists; no new authorization afterward |
| Cross-tenant command / tampered binding | Deny without out-of-tenant probe |
| Real 0100 bundles for all three Project Types | Browser load, nested navigation, RTL and local form behavior pass |
| Existing 0101 isolation gate | Exact sandbox/CSP/CORP/no-CORS/System Font controls remain enforced |
| Logs, metrics, errors, browser diagnostics and reports | Zero token/URL/hash/customer-content leakage |

The Browser Gate must use real 0100 source bundles through this transformer and delivery handler,
not a handwritten replacement document. Fixtures must include nested pages and token-free relative
references. No data-only test or browser URL parser assertion replaces real browser loading.
No numerical retention/expiry/body/batch/time-limit default is invented here; inherited limits
must be identified and any additional required limit frozen before implementation.

## Requirement-to-design-to-gate traceability

The rows below are review traceability; proposed tests are not executed implementation tests.

| Requirement | Source / authority | Design section | Proposed gate |
|---|---|---|---|
| REQ-10201 | BE-F3-02; owner approved namespace | Dedicated storage; deterministic derivative | TC-10201 source unchanged, derivative verified; failed-copy/commit inaccessible |
| REQ-10202 | BE-F3-03; ADR-086/088 | Exact version; transport finding | TC-10202 version N remains N; multi-page/root-path browser test |
| REQ-10203 | Owner approved matrix | Authorization matrix | TC-10203 role/member-owner and cross-tenant command coverage |
| REQ-10204 | T-PRV-05/T-SH-01; proposed controls | Token, expiry, revocation | TC-10204 hash-only, one-time disclosure, expiry/revoke, malformed safe-404 |
| REQ-10205 | Scoped asset access; proposed per-file checks | Capability control 4/5 | TC-10205 direct subresource denial; wrong version/Host/traversal denied |
| REQ-10206 | Owner Local/Synthetic restriction | Controls 6..10 | TC-10206 zero token/URL/content leakage; disposable cleanup |
| REQ-10207 | SEC-F3-04; ADR-088 | Isolation | TC-10207 full opaque-origin regression; no Core credentials/API access |
| REQ-10208 | Repository mutation/idempotency rules; proposed consistency | Publication consistency | TC-10208 concurrent replay; copy recovery; no duplicate outcome/disclosure |

## Approval required before implementation

- Freeze the proposed Local/Synthetic capability controls and publication consistency rules.
- Freeze the proposed explicit-file bearer route and relative-URL delivery representation,
  including the narrowly specified preparation-time transformations.
- Freeze the two-object cardinality, separate Publish/Issue/Revoke commands, lifecycle,
  issuance permission, recovery and bounded error semantics proposed above.

The original Proposed ADR did not authorize migration or runtime activation. Subsequent owner
decisions below authorize scoped Local/Synthetic design and contract-first work, not exact SQL
acceptance. No completed record, Hosted/customer activation or commit/push is authorized.

## Implementation clarification and database authority review

The owner directed continuation after the detailed proposal. Contract-first implementation started
with the transformer, private Manifest validation and internal Application command boundary.
The owner additionally approved removal of React's verified image-preload hint. This clarification
is limited to images already declared by the exact source Manifest; font and external hints remain
unsupported. The raw source HTML remains untouched.

The canonical shared idempotency reservation lifetime is inherited from accepted
[ADR-076](ADR-076-authenticated-scope-share-management-api.md): 24 hours. Exact command replay is
provided within that existing reservation lifetime. A Publication's one-time capability issuance
guard remains permanent even after a reservation expires; expiry cannot permit a second token.
No Preview capability-expiry duration default is introduced.

Automatic approval review rejected writing migration `0040_preview_publication`: the proposed
role/grants/RLS/SECURITY DEFINER changes are a consequential persistent security boundary and this
ADR is still Proposed. The migration patch was not applied, no database was changed and the
security change has not been retried through another tool or execution path.

The following exact authorization proposal is prepared for owner review, **not applied SQL**:

| Principal/object | Proposed permission |
|---|---|
| `aria_preview_runtime_owner` | New `NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION` function-only owner; not owner of target tables |
| Owner schema privileges | `USAGE` only on `public` and existing non-exposed `aria_internal` |
| Owner read set | SELECT on the two Preview metadata tables; column-limited ArtifactVersion/Artifact/Project/Account/Job/Outbox metadata for exact association validation |
| Owner representation write set | UPDATE only `status`, `manifest_ref`, `manifest_hash` |
| Owner publication write set | UPDATE only `status`; token issuance/revoke remain authorized Application transactions |
| Owner Job write set | UPDATE only `status`, `started_at`, `finished_at`, `error_code`, `error_detail`, `attempt_count` for `preview_publication` Jobs |
| Execution-ownership state | Private `aria_internal.preview_execution_claims`: Job/Event/backend PID only; helper owner manages claim rows |
| `aria_worker` | EXECUTE only the four operation-specific helpers below; no direct privilege on Preview tables/claims |
| `PUBLIC`, `anon`, `authenticated` | No direct Preview table privilege and no helper EXECUTE privilege |
| Source Artifact/ArtifactVersion | No new UPDATE/DELETE/ownership privilege; source bytes and ready source metadata remain immutable |

Operation-specific helper signatures and required validation:

```text
aria_internal.claim_preview(job_id UUID, outbox_event_id UUID)
  -> validate exact Job/Outbox/Publication/Representation/source association
  -> verify account/project/version/hash plus frozen event/job/envelope vocabulary
  -> acquire session advisory lock; persist same-backend execution claim
  -> mark same Job running and preparation states, in a short transaction
  -> return private binding metadata only

aria_internal.finalize_preview(job_id UUID, outbox_event_id UUID,
                               delivery_manifest_ref TEXT, delivery_manifest_hash TEXT)
  -> require execution ownership by current backend session
  -> revalidate pinned source hash, exact deterministic namespace and non-revoked Publication
  -> require matching immutable Manifest identity if Representation already ready
  -> atomically set Representation ready + Publication ready + same Job succeeded

aria_internal.release_preview(job_id UUID, outbox_event_id UUID)
  -> release only the same-backend claim/advisory lock for the exact Job/Event pair

aria_internal.resolve_preview(token_hash TEXT)
  -> exact hash-indexed lookup; synchronous expiry/revoke checks
  -> verify complete account/project/version associations and ready states
  -> short shared lock on Publication for revoke/read ordering
  -> return binding/Manifest metadata to controlled delivery adapter, or no result
```

All four functions use fixed SQL, schema-qualified references and an empty fixed `search_path`.
No table names, free predicates, arbitrary SQL fragments, raw tokens or content payload are accepted.
PUBLIC execution is revoked before runtime grants. The trusted helper owner receives role-specific
RLS read policies on only its fixed metadata read set, and update policies only on its fixed
Preview/Job write set. Direct Worker access remains denied. Those owner policies trust the scoped
helper logic; they do not claim isolation after compromise of the existing shared Worker credential.
`WORKER-CROSS-TENANT-001` remains open, consistent with ADR-087.

Before migration execution, require owner acceptance of this limited authority and the proposed
two-table schema/constraints. The gate must then run under actual `aria_worker`, with positive
helpers and negative direct-write/helper-spoof/cross-tenant tests on a new throwaway PostgreSQL
instance. Owner-role success alone cannot mark 0102 complete.

This authorization request covers local synthetic migration/test execution only. It does not
authorize a Hosted migration, new product endpoint, customer content or commit/push.

### Owner decision and exact SQL review handoff — 2026-10-12

**Subsequent decision:** following the explicit question naming `migration-review.sql` and
limiting execution to throwaway Local/Synthetic PostgreSQL, the owner replied "ادامه بده".
That response authorizes executing that SQL's limited gate; it does not authorize Hosted,
customer content, commit/push or new privilege scope. The reviewed snapshot SHA-256 is
`916b2babe10e57b05d9b5fd19e4d127fae54a5c71182e757470d6333a4ece3b6`.
The following earlier source-review notes are history, superseded only for this scoped SQL gate.

The owner approved Option 1 **architecture/design/tests only for throwaway Local/Synthetic
PostgreSQL**, while explicitly retaining **PENDING SOURCE REVIEW** for exact SQL/helper security.
That decision is not approval of every schema field, policy or helper implementation.

The complete, non-active SQL is [migration-review.sql](../development/0102-local-preview-publication-and-capability/migration-review.sql).
It is not an Alembic revision, is not imported by migration configuration, and has not been
applied. The [source-review handoff](../development/0102-local-preview-publication-and-capability/database-security-review.md)
states the precise object/privilege/locking boundary and outstanding real-role evidence.

For naming clarity, the two product tables in this design are `preview_representations` and
`preview_publications`; capability hash/lifecycle is stored on Publication, not in a separate
Capability aggregate. `aria_internal.preview_execution_claims` is a **third, operational table**
with Job/Event/backend PID only, explicitly included in the exact SQL review. It is not content
storage or a new product source of truth. These exact definitions still require source approval.

Target and claim table ownership stays with the migration principal. The helper owner only owns
the four functions, has no login/role membership/table ownership, and receives only explicit
object privileges and role-specific RLS policies. `ENABLE ROW LEVEL SECURITY` is used without
claiming `FORCE RLS`: table owners remain trusted migration authority, never runtime helpers.
No broad Worker SELECT/RLS redesign is introduced. The owner-role read policies are intentionally
not a defense against a compromised shared Worker calling otherwise-valid helpers for another
tenant; `WORKER-CROSS-TENANT-001` remains open and precludes Production acceptance.

Mutation helpers first lock Job -> Publication -> Representation, then revalidate the complete
Job/Event/source/account/project/version graph before mutation. Ready source identities/hash are
protected by existing immutable ArtifactVersion contracts; no source UPDATE privilege is added.
Resolve takes a short shared Publication lock and checks current capability expiry/revocation.
No database transaction is held open for transformation, storage or browser delivery.

Source review corrected PL/pgSQL block terminators and included SELECT on Job `started_at` and
`attempt_count`, which are read by the restricted UPDATE expressions. Optional `anon` and
`authenticated` role privileges are explicitly revoked using fixed statements, with no dynamic
SQL. Static review tests are not SQL compilation, RLS enforcement or runtime-principal proof.

### Local database authority execution and remaining rollback decision

Alembic `0040_preview_publication` mechanically embeds the reviewed executable statements;
it reads no document at runtime. Static equivalence checks compare it to the immutable review
snapshot. Fresh upgrade succeeded on a new disposable PostgreSQL 16 container, independent of
existing local databases. Helper tests connect as `session_user=current_user=aria_worker`,
not DB owner or SET ROLE. Scoped authority/capability tests passed; this is not a Browser,
Hosted or full tenant-isolation gate. RLS skill review reinforced function/table owner separation
and short transactions, without changing the accepted shared-Worker residual-risk boundary.

The source specifies upgrade SQL but no downgrade contract. The current revision fails closed
on downgrade. An existing identity downgrade regression therefore fails at 0040; it is not
skipped or reported PASS. A separate explicit owner decision is requested for **empty-only
downgrade**: reject if any Representation/Publication/claim row exists; otherwise drop only
0040's functions/policies/tables/index and revoke its exact grants, preserving the cluster Role
if another database still depends on it. This proposal is not implemented without approval.

Full 0102 remains PENDING: rollback compatibility plus Worker storage/publishing and real-bundle
Browser acceptance remain open. No public route or hosted relay/preview is activated.

### Approved guarded downgrade — 2026-10-12

After the explicit question defining empty-only rollback with cross-database Role preservation,
the owner replied "ادامه بده". This authorizes that limited migration implementation/testing,
not record deletion, Hosted operation or commit/push. REQ-10209/TC-10210 cover this change.

Acquire transaction-bound exclusive locks on all three new tables before testing emptiness.
Any Representation, Publication or execution-claim row rejects downgrade before dropping any
object. Otherwise remove only 0040's fixed functions, policies, tables, Job index and exact
column/schema grants; never use CASCADE, DROP OWNED or change existing Worker grants.
Preserve the helper-owner Role when pg_shdepend records use outside the current database.
Unexpected remaining dependencies must abort transactionally rather than be destroyed.

Re-upgrade must accept a preserved Role only when its seven locked attributes remain safe;
an incompatible existing Role fails closed without altering it. This administrative reuse
guard follows ADR-070/0030 and is necessary to round-trip the approved cross-database behavior.
It introduces no new runtime Helper, privilege or broad Worker refactor. The original reviewed
table/helper statement literals remain unchanged; Role reuse and rollback are separately tested.

Required evidence: nonempty rollback rejected with data/functions/revision intact; empty rollback
and re-upgrade; the previously failing legacy rollback; two-database Role preservation and
safe reuse; incompatible Role rejection; full PostgreSQL regression. Until verified, no PASS
is claimed for rollback compatibility.

### Guarded downgrade verification — 2026-10-12

The approved downgrade is implemented. Fixed Outbox policy naming was corrected after the first
green attempt exposed a mismatch; tests were rerun rather than changing the guard or skipping
failures. Source SQL literals are unchanged except whitespace; the original review snapshot remains
immutable. Role reuse verifies all seven attributes without altering an existing Role.

- Reproducible fresh PostgreSQL harness: **36 passed**; DB authority and guarded downgrade gates
  PASS, full publishing/browser gate NOT EVALUATED.
- Complete API PostgreSQL regression: **801 passed / 1 skipped**. An earlier run had 800 passed,
  1 skipped and one Windows connection/SSL handshake failure; that failed run is retained as history.
  The single case and full suite were explicitly rerun with `ssl=disable` only on disposable,
  trust-auth loopback PostgreSQL, which has no TLS. No product TLS or retry policy was changed.
- Complete Worker PostgreSQL regression: **281 passed / 2 skipped** after fixing only the Outbox
  test fixture's new claim FK cleanup and using a workspace-local test temp directory. Initial
  fixture/temp-path failures are recorded, not suppressed; no Worker runtime privilege was added.
- Nine static SQL/equivalence/rollback/Role checks; API/Worker lint/typecheck and migration strict
  typecheck PASS. General `npm test` PASS with its separately reported integration skips.

The rollback compatibility blocker is CLOSED. Remaining 0102 publishing/storage/Worker/Browser
acceptance is still PENDING, so `validate` must remain failing on the pending record. Hosted/customer
operation, full tenant isolation, real Provider and commit/push remain unauthorized.

## Initial proposal verification — 2026-10-12

### Fifth-helper implementation subgate — 2026-10-13

The approved exact SQL is embedded in 0041 with source-equivalence checks. Both SQL review
snapshots and 0040 remain unchanged. No new role, RLS policy, table or broad Worker privilege is
introduced. Only owned-session, known non-retryable source/immutable-delivery errors can fail the
same Job. Failure commit rollback remains recoverable; no false terminal/success result is returned.

Final focused disposable gate: 58 API authority/rollback/failure cases + 12 Worker cases PASS,
using actual aria_worker. An intermediate Worker test indentation failure was corrected and the
complete gate rerun. New denial cases assert SQLSTATE 42501 explicitly. General npm regression
PASS: API 585 passed/239 skipped; Worker 329 passed/52 skipped; Node/Renderer/Web PASS. Lint and
strict types PASS. Full PostgreSQL regression is recorded below after completion.

Final `-FullRegression` run PASS on a fresh disposable instance: API 823 passed / 1 skipped,
Worker 379 passed / 2 skipped, following focused 58+12 actual-role tests. Its exact container and
temporary files were cleaned; existing local instances were untouched. Ten static/equivalence
checks and strict migration types PASS. Validate still reports one PENDING 0102 issue; no gate
was weakened. The historical source-review files remain byte-identical (including old design-only
headers), while current approval/execution state is recorded in this ADR and development records.

This closes the three-code permanent-failure authority subgate only. Preready revocation Job
disposition, queue composition, HTTP/Browser gate and all Hosted/customer/Provider activation
remain deferred. Shared Worker compromise risk is unchanged. No commit/push authorization exists.

### Fifth failure-helper design authorization — 2026-10-13

Subsequent owner "ادامه بده" directly answers the question requesting approval of the exact
linked SQL for Local/Synthetic migration. The fifth-helper proposal below is therefore approved
for this limited execution/test scope, including owner-only SELECT(error_code). The design
snapshot remains historical/immutable; an active 0041 migration embeds the executable statements.
No RLS/direct Worker table privileges or original four helper changes are authorized. Its DB/runtime
gate remains pending until actual aria_worker tests pass; preready revocation remains deferred.

Independent read-only continuation adds an Application access boundary and an adapter for the
existing hash-only `resolve_preview`, without SQL changes. GET/HEAD reauthorize each exact
file, verify private Manifest/file bytes, and return safe no-store/no-referrer/CSP metadata.
Actual aria_worker local tests prove GET/HEAD and deny after revoke across all three source
bundles. There is no HTTP listener/Browser/Hosted or queue activation; these subgates cannot
close the full 0102 gate. The helper design review below remains independent and unapplied.
Final access verification: 32 focused cases and 36+6 disposable PostgreSQL cases PASS. Full
`npm test`: API 585 passed/217 skipped; Worker 322 passed/46 skipped; Node/Renderer/Web PASS.
Lint/types PASS; validate retains the single PENDING 0102 failure. No Browser Gate, actual HTTP
listener, queue activation, fifth-helper execution, hosted/customer operation or commit/push occurred.

The owner explicitly approved **design only** of
`aria_internal.fail_preview(job_id UUID, outbox_event_id UUID, error_code TEXT)`.
Migration/execution remains WAIT for exact SQL review. See the complete
[unapplied SQL proposal](../development/0102-local-preview-publication-and-capability/failure-helper-review.sql).
The accepted 0040 migration, original reviewed SQL and four active helpers are unchanged.

Proposed decision details for that source review:

- Exactly three known permanent preparation codes: `PREVIEW_SOURCE_UNSUPPORTED`,
  `PREVIEW_SOURCE_INVALID`, `PREVIEW_DELIVERY_CONFLICT`. No transient storage/DB error,
  raw exception, arbitrary reason, technical retry or automatic Job replacement.
- Existing function-only owner and unchanged RLS. No direct Worker table privilege. One extra
  owner-only `SELECT(error_code)` column grant is proposed solely to verify same-session
  terminal persistence replay; its exact grant/revoke must be approved with the SQL.
- Lock Job -> Publication -> Representation and revalidate the entire Job/Event/tenant/project/
  exact-source graph. Require current backend's exact claim AND live advisory lock. `pg_locks`
  key mapping follows [PostgreSQL 16 documentation](https://www.postgresql.org/docs/16/view-pg-locks.html).
- Only the same running Job may become failed with bounded reason, NULL error_detail and
  server finished_at. Same owned-session/same-reason replay does not change its timestamp.
  Different reason or a succeeded/queued/unclaimed/foreign-session Job is denied.
- Publication remains inaccessible in `publishing`; Representation retains `preparing` or its
  already-ready immutable reusable content. No new lifecycle enum, capability, file cleanup,
  source mutation, grant expansion to Worker or current-pointer change is proposed.
- Keep claim until commit, then call existing `release_preview`. Failed helper commit rolls back
  all Job changes; connection loss uses existing invalidation. Redelivery of a terminal failed
  Job is denied by current claim behavior, with no re-execution. This proposal does not change
  terminal replay behavior of the other four helpers.
- Pre-ready revocation disposition and errors outside the three-code allowlist remain pending;
  do not weaken non-revoked binding checks to resolve them implicitly.

Required future tests, **NOT EXECUTED / NOT PASS**: actual aria_worker positive transition;
wrong Job/Event/tenant/version and foreign-session/stale-PID/no-live-lock denial; invalid/raw/
transient error rejection; unchanged source/publication/representation/capability; atomic rollback;
same-reason replay/timestamp preservation; terminal reason conflict; concurrent finalization vs
failure; revoke-before-failure denial; owner/EXECUTE/column ACLs; narrow downgrade compatibility.
No helper SQL was applied, and no permission to commit/push or activate Hosted operation exists.

### Worker preparation continuation — 2026-10-13

Owner continuation authorizes this limited Local/Synthetic work, not Hosted/customer execution.
The framework-free Worker pipeline and dedicated local proof storage implement existing
manifest-last create-or-verify recovery semantics. Source canonical validation reuses frozen
0095 content rules and 0096 consumer validation; stored source is never repaired. A fixed,
validation-only Node subprocess inherits the existing 0100 tool timeout and reaps cancellation.

The PostgreSQL adapter invokes only the existing approved helper signatures; it introduces no
SQL/helper/grant/RLS change. Claim/finalize transactions remain short and storage runs outside
them. Ambiguous commit or session cleanup invalidates the physical connection rather than
returning possible advisory ownership to a pool. PostgreSQL/Supabase skill guidance reinforced
least privilege and short transactions; existing Alembic governance remains authoritative.

Evidence: 79 focused Worker Preview cases passed. A fresh disposable PostgreSQL harness passed
36 existing authority/downgrade cases and 6 additional actual aria_worker login cases across
real landing/corporate/portfolio bundles, including explicit copy failure and same-ID recovery.
Fixture-only metadata allocation is not a public management command or queue/browser E2E proof.
Permanent Job failure disposition, queue composition, capability file delivery and Browser
acceptance remain pending. No new full/Hosted security acceptance, Provider or commit/push
authorization is inferred.
Final non-DB regression: API 585 passed / 217 skipped; Worker 290 passed / 46 skipped;
Node/Renderer/Web PASS. Worker lint/types PASS; validate retains its one expected PENDING 0102
failure. No existing database/container or prior increment was removed or reset.

`npm run validate` passed all 23 checks and `git diff --check` passed. `npm test` passed the
repository regression suites: API 558 passed / 182 skipped; Worker 211 passed / 40 skipped.
Skipped integration tests are not evidence of a PostgreSQL/Hosted gate. No 0102 runtime or
capability/browser acceptance test has been implemented or passed. Only this proposal and its
ADR index entry were added for 0102; earlier uncommitted increments were preserved.

The detailed design above was added after that initial verification. Its URL examples and source
findings are design evidence, not executed 0102 tests. Final documentation verification is recorded
below after the current run.

## Controlled queue adapter continuation — 2026-10-13

The owner continued after the verified preready cancellation subgate. The existing frozen
`preview.publication_requested.v1` / `preview_publication` / `aria.preview.publish.v1` identifiers
are implemented in an explicitly constructed Local/Synthetic publisher/task adapter. The general
Celery publisher, Worker bootstrap and Relay bootstrap remain unchanged and Preview-disabled.
No environment flag, global/shared task registration or Hosted configuration is introduced.

The task delegates only the closed identifier envelope to the existing Preview runtime. It uses
app-local registration, no automatic retry, no persistent result backend and only the existing
bounded outcome/reason vocabulary. Storage/DB/customer diagnostics cannot become task errors or
results. Runtime synthetic allowlists, fixed helpers, validation and idempotency are not replaced
by the queue adapter. Durable relay transport retry remains the separate accepted 0070 policy.

Contract/unit tests and a throwaway loopback Redis worker can prove this transport boundary, not
the complete PostgreSQL/Outbox-to-browser path. No chaining, public command, Provider invocation,
new service or SQL authority change is authorized by this continuation.

Execution evidence: 40 adapter/transport cases passed on an owned loopback Redis instance,
including a real Celery worker for success/permanent/recoverable outcomes. The executor is a
synthetic double, so PostgreSQL/Outbox-to-storage/browser E2E is not evaluated by this subgate.
App-local registration, one call per delivery, no automatic retry/persistent result and bounded
diagnostics pass. Worker lint/types pass; the temporary Redis container was removed. No general
Worker/Relay bootstrap, existing publisher, dependency or database authority changed.
Final npm regression PASS: API 585/246 skipped and Worker 356/55 skipped, including separately
executed Redis tests. Validate retains the one PENDING 0102 issue; other 22 checks pass. No new
complete PostgreSQL/queue/browser acceptance, Hosted activity or commit/push is inferred.

## Preready revoke disposition — owner continuation, 2026-10-13

The owner continued directly after the explicit preready revocation/cancellation question.
The authenticated Application command atomically revokes the Publication, cancels its same
queued/running Job, records terminal completion time and persists the safe idempotency outcome.
Existing terminal Jobs are not transitioned or retimed. This does not revoke/delete the immutable
Representation, delete Outbox events, steal a live Worker claim, or authorize a replacement Job.

Lock order is Job -> Publication, consistent with the fixed Worker helpers. Both lookups enforce
the current tenant/project, Member ownership and exact Publication/Representation/ArtifactVersion
Job payload binding. After locking, only preready active Jobs can be cancelled. If finalization
commits first, revoke preserves the succeeded Job and revokes the ready Publication instead.
If revoke commits first, claim/finalization cannot turn the cancelled Job into success.

No new database authority, SQL helper, migration, broad grant or RLS change is introduced.
Rollback and idempotency replay must preserve the complete prior business state. This is a
Local/Synthetic command subgate only; queue/HTTP/browser and Hosted acceptance remain pending.

Executed evidence: focused 65 API + 12 Worker PASS; complete disposable PostgreSQL regression
API 830 passed / 1 skipped, Worker 379 passed / 2 skipped. Both race orders, rollback, binding
denial and replay/terminal timestamp preservation pass. `npm test`, API lint/typecheck and
10 fixed-SQL checks PASS. Validate intentionally retains the single incomplete 0102 failure.
Existing reviewed SQL hashes/roles/grants are unchanged; only owned test resources were removed.

## Detailed design verification — 2026-10-12

- Verified six proposed relative-path mappings with two distinct synthetic capability markers
  using Node's WHATWG URL implementation: all 12 origin/prefix/file assertions passed. This was
  an in-memory diagnostic; it persisted no token/URL or runtime code.
- `npm test` passed: API 558 passed / 182 skipped; Worker 211 passed / 40 skipped, and all
  repository Node/Renderer/Web suites passed. Skipped suites remain incomplete coverage.
- `npm run validate` passed 23 checks; `git diff --check` passed.
- Only ADR-089 design prose changed in this continuation. Existing runtime, source Artifact,
  migrations and prior uncommitted increments were preserved. Task-specific pytest temp data
  was removed after the test run.
- 0102 implementation, PostgreSQL authority/concurrency/recovery and real-bundle Browser Gate
  are **NOT IMPLEMENTED / NOT EXECUTED**. This is not a completed or PASS development increment.
- Final freeze of the proposed contract is required before implementation under repository
  governance. No Hosted/customer-content/commit/push authorization has been inferred.
