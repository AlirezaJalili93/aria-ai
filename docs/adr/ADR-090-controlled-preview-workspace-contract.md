# ADR-090 — Controlled Preview Workspace and Authenticated Access Contract

**Status:** WAIT — PENDING CONTRACT REVIEW; implementation NO-GO

**Date:** 2026-10-17

**Planned increment:** `0103-controlled-preview-workspace`

**Review revision:** v0.15 — P4 contract FROZEN; P5 Installer/pre-commit ACL design APPROVED, exact SQL r2 PENDING SOURCE REVIEW; full ADR Freeze WAIT; implementation/SQL execution/Migration NO-GO

The owner approved T1..T7, the six D6 One-shot semantics and the minimum consumption-retention
invariant and identity-only response direction recorded in v0.7 below, plus S1/S2/R2 with the
refinements and subsequent explicit P2/P3 approvals recorded in v0.9, and the P5 logical model and
Capability-bound authentication decision recorded in v0.12, plus the P4 derivative identities and
initial-page decision recorded in v0.13. The owner subsequently read the complete v0.13 P4.R1..R4
text in the conversation and explicitly froze the complete P4 contract (v0.14, 2026-10-24).
The subsequent v0.15 decision approves only the independent temporary Superuser Installer and
pre-commit effective-authority design; the revised SQL text itself remains pending source review.
This includes its derivative identities, initial page, transformation/script/CSP rules and P4
acceptance conditions, not executable source bytes or proof results. Remaining P1 transport/
persistence integration, other D clauses, detailed state/polling proposals and wireframe are not
thereby Frozen. Contract refinement/review only is authorized. No runtime
code, endpoint, migration, Hosted activation, commit or push is authorized by this draft revision.

**ADR090-T01 direction resolved:** the owner selected option 2: no capability token in any URL,
including Path, Query and Fragment. ADR-089's Local/Synthetic bearer-URL exception is technical debt
of 0102 and MUST NOT be inherited by 0103. T1..T7 below are approved constraints, not approval of
the proposed replacement transport. D6's approved semantics do not authorize the remaining transport,
other D clauses or wireframe.

## Purpose and current evidence

Define a concrete next slice for `FE-F3-05` (browser preview container) and `FE-F3-06`
(mobile/desktop viewport switch). The owner asked to continue development from the canonical
documents, then to continue the proposed contract definition. This authorizes preparing this
proposal. Except for the explicitly approved T1..T7, D6 semantics, v0.7 retention/identity-only
decisions, v0.9 S1/S2/R2/P2/P3, v0.12 P5 logical-model/authentication decisions and the v0.14
P4 contract Freeze based on v0.13's complete text, plus v0.15 Installer/pre-commit ACL design,
unapproved details below remain proposals.

0102 passed its approved Local/Synthetic publication, access and browser matrix. It deliberately
excluded management HTTP/JWT and product activation. Source inspection on 2026-10-17 found
`PreviewPublicationService.publish/issue/revoke` in the Generation Application layer, but no
Generation/Preview FastAPI router or Web Preview Workspace. Connecting the UI therefore requires
an explicit HTTP contract, safe queries and browser capability handling.

This is a local proposal, not a modification or a claim of approval in Canonical Drive.

## Sources and traceability authority

Canonical source links were read through the connected Google Drive plugin; sync/review date:
**2026-10-17**. The repository implementation remains subject to the explicit owner restrictions
recorded in ADR-073 and ADR-088/089.

| Source | Relevant requirements |
|---|---|
| [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) | EP-F3; FE-F3-05/06; OBS-F3-07 is a following work item |
| [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) | Sprint 3, section 14.4; isolated exact-version Preview and executable vertical slices |
| [PRD](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) | FR-10-01/02/04, US-14; browser Preview, basic responsive review and visible version identity |
| [UX Information Architecture](https://docs.google.com/document/d/1buWODJz-NdmRdcm1bo8iL-rwEa_4Z7lKkrNHqpk54_I/edit) | SCR-20; canvas/controls, Artifact/Scope version and status; approved wireframe before Frontend implementation |
| [Frontend UX State Specification](https://docs.google.com/document/d/1uEDGtiFriI10ACNQwgKtjJJhdQEUK7KDY70dLicyUzE/edit) | PRV-01..05, GEN-01; permission safety, actionable recovery, RTL, keyboard and no sensitive diagnostics |
| [API Contract Specification](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) | Sections 2..7, 17, 22..27; JWT, Tenant boundary, envelopes, immutable versions, idempotency, OpenAPI/security testing |
| [ADR-073](ADR-073-mvp-real-provider-integration-deferral.md), [ADR-088](ADR-088-preview-isolation-architecture.md), [ADR-089](ADR-089-local-preview-publication-and-capability.md) | Existing Local/Synthetic, sandbox, source-profile and capability restrictions |
| [Design System Master](../../design-system/MASTER.md) | RTL, tokens, focus, target sizes and reference breakpoints |

The canonical sources specify the feature and security goals. They do not specify these new
route names, projection fields, viewport defaults or the proposed polling/event semantics.
Those are explicitly reviewable decisions below, not silently inferred requirements.

## D1 — Scope and activation proposal

Implement the new API/router, safe query projection and Web component through a controlled
Local/Synthetic composition, using the existing API, Web and Worker artifacts. No new deployable
service, Provider call, generation endpoint, Generation-to-Publish chaining or guest sharing is
part of 0103. The input source remains the exact verified 0100 static bundle accepted by 0102.
The single-response candidate below would require a separately versioned delivery derivative;
it does not silently extend 0102's accepted no-JavaScript delivery profile.

Normal API bootstrap does not register the controlled router. Normal Web composition exposes a
controlled unavailable state for the proposed route and does not add a live project-navigation
entry. The local proof explicitly supplies the approved synthetic source identities/hashes,
loopback services and exact Core/Preview test origins. An ordinary boolean UI flag cannot authorize
access. Requests outside the configured synthetic allowlist fail closed before Job/Outbox creation
or capability disclosure. Customer, Production and Hosted use stay unauthorized.
The source-identity/hash allowlist is server-only; it is not serialized into browser bundles or RSC
props and is not accepted from Client input.
The same allowlist is enforced for both new metadata queries; a Publication must resolve back to
the configured source identity/hash before it can be projected. Normal unregistered API routes
remain 404; FEATURE_NOT_ENABLED applies only inside an explicitly registered controlled composition
whose availability guard denies execution.

The proof must use the existing JWT verifier and DB-backed active membership resolution with a
controlled synthetic issuer; caller-supplied subject/role and an authentication bypass are not
acceptable HTTP evidence. 0102 validates a capability independently for every file. A replacement
0103 transport must prove its own authorization boundary; that existing route is not reusable here.

Acceptance closes a **Local/Synthetic Workspace foundation** only. It does not claim completion of
Product Preview, FE-F3 production acceptance, Login-to-Preview or Hosted security acceptance.

## D2 — Exact version and query projection proposal

All routes below have the `/api/v1` prefix. A concrete Artifact ID and `version_no >= 1` identify
the selected immutable version. No `latest` alias, implicit version selection, pointer mutation,
background publication or auto-regeneration is introduced.

| Method and route | Request | Successful result |
|---|---|---|
| `GET /projects/{project_id}/artifacts/{artifact_id}/versions/{version_no}` | No body | 200 exact version projection |
| `POST /projects/{project_id}/artifacts/{artifact_id}/versions/{version_no}/preview-publications` | Exactly empty body; Idempotency-Key | 202 Publication/Job references |
| `GET /projects/{project_id}/preview-publications/{publication_id}` | No body | 200 exact Publication projection |
| `POST /projects/{project_id}/preview-publications/{publication_id}/capability` | Closed JSON `{expires_at: timezone-aware datetime}`; Idempotency-Key | 201 first issuance; 200 replay |
| `POST /projects/{project_id}/preview-publications/{publication_id}/revoke` | Exactly empty body; Idempotency-Key | 204, including replay |

`{}` is not an exactly empty body. Unknown JSON properties are rejected with 422 VALIDATION_FAILED.
GET requests with a nonempty body are rejected with the same validation error. FastAPI/OpenAPI and
the contracts mirror must describe the same shapes before Web integration.

Exact version `data` is closed to:

```text
artifact_id
artifact_version_no
source_scope_version_no
version_status = queued | generating | validating | ready | failed
```

The version row is resolved with Account + Project + Artifact + version number. Its bound
ScopeVersion supplies `source_scope_version_no`, never the current ScopeVersion of the Project.
The existing technical version status is displayed with accurate Persian labels. `ready` is not
`approved`, and `Draft/Under Review/Approved` is not invented as a new Artifact review state.
An Artifact review/approval lifecycle remains a separate contract.

Publication `data` is closed to:

```text
publication_id
artifact_id
artifact_version_no
source_scope_version_no
publication_status = allocated | publishing | ready | revoked
job_id
capability_issued: boolean
expires_at: UTC datetime | null
can_issue: boolean
can_revoke: boolean
```

These are safe operational projections, not ORM serialization. They omit source/delivery/checkpoint
references, hashes, Manifest/AST/content, token/token_hash, creator identity, tenant internals and
storage/provider metadata. `can_issue` and `can_revoke` are Backend decisions for their named
actions only; endpoints independently enforce permission and state at mutation time. Expiration is
derived from the existing timestamp; it does not become a new persisted Publication lifecycle.

Both GETs use the normal `{data, meta:{request_id}}` envelope. Publish returns:

```text
data: {publication_id, job_id, status_url: /api/v1/jobs/{job_id}}
meta: {request_id, replayed}
```

There is no collection/version picker in this slice. The controlled proof supplies safe links to
concrete version identities. Product version discovery/navigation follows a separate query contract.

### Proposed browser-to-Web transport

Retain the existing server-owned Core authentication pattern. Add narrow Next.js Route Handlers
under `/api/preview-workspace/projects/{projectId}/...` for only the five operations above (matching
their suffixes after `projects/{project_id}`), plus the selected Publication's Job Status read.
The latter has the fixed Web path
`/api/preview-workspace/projects/{projectId}/preview-publications/{publicationId}/job`; it resolves
the authorized Publication first and forwards only its persisted job_id to the existing Job API.
It accepts no arbitrary Job ID or upstream path.

The Web handlers resolve the existing verified session/account server-side, then forward JWT and
X-Account-ID to FastAPI using the configured fixed API origin. FastAPI independently verifies both
JWT and membership. Client-supplied role/account/Authorization values cannot replace this context.
No generic proxy, arbitrary destination or new browser-side JWT storage is introduced.

Because the Web handlers use Core cookies, every unsafe method requires an Origin exactly equal
to the configured Core origin; missing, null or foreign Origin is rejected with bounded 403
FORBIDDEN before forwarding. Reject Sec-Fetch-Site=cross-site; do not enable cross-origin credential
access. Host/X-Forwarded-Host are not configuration authority. The controlled feature/synthetic
guards also apply here. All responses, including errors, are no-store; redirects do not forward
credentials. A response containing the raw capability is a plain transient JSON response to fetch,
not Server Action/RSC state. No intermediary response cache or body diagnostic capture is enabled.

The Web and API contracts validate the same closed shapes. Mutation retries remain explicit and
reuse the same logical key; the Web gateway performs no hidden upstream retry. This fixed gateway
is a proposed addition to existing Web server-to-API calls, not an approved general proxy mechanism.

## D3 — Authorization, idempotency and HTTP error proposal

All management requests require Bearer JWT, X-Account-ID and the existing active membership
boundary. The header is checked against verified membership; it is not Tenant authority by itself.

| Operation | Active Owner/Admin | Active Member |
|---|---|---|
| Exact version metadata | Visible tenant/project | Visible tenant/project |
| Publish | Visible exact eligible source | Visible exact eligible source |
| Read Publication / Issue / Revoke | Any visible project Publication | Own Publication only |

Publication-read visibility is a new proposal; Issue/Revoke ownership follows the accepted 0102
implementation. Invited/suspended/inactive and authentication failures retain existing Auth/Tenant
semantics. Missing, cross-tenant and non-visible resources return the same safe 404; no existence
probe outside Tenant scope is added. An archived Project remains read-only: Publish/Issue are denied
with safe 404; Revoke remains available to an otherwise authorized actor to invalidate access.
This archived-Project disposition is a proposed product/security decision for review.

Transport syntax errors can be rejected without a resource lookup. For well-formed requests the
resource order is authenticate/resolve Tenant -> resolve Project -> enforce controlled composition ->
resolve exact authorized target -> command idempotency -> state guards -> existing Application
command. Closed request-shape validation precedes command use. All write state/permission checks
are revalidated in the transaction.
Same-key replay precedes mutable readiness/issuance/active-Job guards. Malformed structural inputs
are validation errors; resource UUID associations never substitute for authorization.

Publish/Issue/Revoke reuse their existing Application and repository idempotency operations. They
do not create a second parallel store or a different route-key namespace. Preserve the accepted
actor/account/project/operation scope, canonical request hash, shared 24-hour record retention and
DB race guards. `expires_at` canonicalizes to UTC before fingerprinting. A changed request with the
same key gives 409 IDEMPOTENCY_CONFLICT. A key replay never creates a second logical outcome.

| Error | HTTP | retryable |
|---|---|---|
| RESOURCE_NOT_FOUND | 404 | false |
| FEATURE_NOT_ENABLED | 403 | false |
| VALIDATION_FAILED | 422 | false |
| IDEMPOTENCY_CONFLICT | 409 | false |
| ARTIFACT_VERSION_NOT_READY | 409 | false |
| PREVIEW_PUBLICATION_IN_PROGRESS | 409 | false |
| PREVIEW_PUBLICATION_REVOKED | 409 | false |
| PREVIEW_CAPABILITY_ALREADY_ISSUED | 409 | false |
| PREVIEW_SOURCE_UNSUPPORTED / PREVIEW_SOURCE_INVALID | 422 | false |
| PREVIEW_DELIVERY_CONFLICT | 409 | false |
| PREVIEW_STORAGE_ERROR / PREVIEW_FINALIZATION_RECOVERABLE | 503 | true |

Only errors actually raised in the management path map to that HTTP response. Worker failures remain
the bounded Job result from the existing Job Status API. `retryable=true` does not authorize an HTTP
retry scheduler, a new recovery Job or another Provider invocation. Unexpected failures produce the
existing bounded internal error without raw exception text or dependency details.

No schema/Role/grant/RLS/helper change is authorized. A durable bootstrap-consumption boundary may
require new schema and narrow helpers; exact SQL and authority must be separately reviewed before
execution. Do not promise a schema-free implementation or add broad grants to accommodate this draft.

## D4 — Expiration and one-time browser capability proposal

The user must enter an explicit expiry date/time before Issue. The UI has no prefilled date,
remembered expiry, implicit duration or renew-on-load behavior. It clearly displays the browser's
local timezone and submits an unambiguous UTC timestamp; the server enforces a future instant.
No new maximum duration is introduced by this draft. Replays retain the original result semantics
even if the original future timestamp has subsequently elapsed.

Issue returns only:

```text
data: {publication_id, token: string | null, token_available: boolean, expires_at}
meta: {request_id, replayed}
```

First response: 201, token_available=true. Same-key replay: 200, same Publication/expiry,
token=null, token_available=false. The original token-bearing response cannot be retained in
idempotency storage, server-rendered HTML, React Server Component payload, a Server Action state
cache, an error boundary, diagnostics, logs or reports. The issue response is consumed directly
in browser volatile memory. Core authentication credentials never go to the Preview origin.

### Approved transport constraints — owner's T1..T7

| ID | Approved constraint |
|---|---|
| T1 | Capability token is prohibited in Path, Query and Fragment, including iframe navigations, redirects, resource URLs and secret hostnames |
| T2 | No token persistence in localStorage, sessionStorage, Cookie or IndexedDB; renaming a bearer secret to session ID does not create an exception |
| T3 | Transfer only through a specified, limited, testable transport; the exact transport remains unapproved |
| T4 | Each tab owns independent volatile memory; no automatic cross-tab token transfer |
| T5 | Refresh, Close and Workspace exit cause no automatic recovery or reissuance |
| T6 | BFCache return requires access revalidation; security cannot depend on pagehide/unload execution |
| T7 | Legacy `/p/<token>/...` is 0102 technical debt and is prohibited in 0103 |

Source: explicit owner transport decision of 2026-10-17. This supersedes the unselected alternatives
in v0.2, not ADR-089's existing runtime. No legacy route is changed in this documentation revision.

### Transport feasibility finding — not an implementation decision

Platform references checked on 2026-10-17: the WHATWG [form submission algorithm](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#form-submission-algorithm)
specifies POST body submission and checks the submitting document's sandbox flags; MDN's
[form reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/form)
describes targeting a browsing context. These support evaluating a Core-owned form, not a claim
that P1 has passed browser tests. Lifecycle references below document restoration/callback limits.

POST bootstrap alone does not solve authenticated multi-file delivery. Once HTML has loaded, normal
stylesheet/image/navigation requests need their own authorization signal. A server-side session row
does not identify those requests automatically. Ordinary element requests cannot be configured to
attach an arbitrary Authorization header held by the parent tab. A cookie carrying a session bearer,
a secret subdomain, IP binding, Referer or a public resource UUID is not an approved substitute.
Origin checks are defense in depth, not proof of tenant authorization.

Consequently **POST + ordinary 0102 multi-file resources + no URL bearer/cookie/header mechanism is
an incomplete design**, not a transport ready to implement. No CORS exception, ServiceWorker,
postMessage bridge, srcdoc/blob substitution, request interception or allow-same-origin is selected.

The owner conditionally accepted **P1 single-response bootstrap** as Local/Synthetic design only.
It avoids a follow-up-resource authorization channel by not making follow-up resource requests.
One-shot delivery semantics are approved in D6; exact profile, CSP, SQL and transport details still
require review and practical evidence. No implementation authority follows from conditional approval.

### P1 — Proposed body-only, single-response bootstrap contract

**Status: DESIGN CONDITIONALLY ACCEPTED / NOT FROZEN / NO IMPLEMENTATION AUTHORITY.** Proposed local
Preview-origin route:

```text
POST /bootstrap
Content-Type: application/x-www-form-urlencoded
body: token=<capability>

success: 200 text/html; charset=utf-8
GET / HEAD: no Preview bytes
redirects: none
```

The path and host contain no secret or caller-selected upstream destination. Proposed request shape:
exactly one scalar `token`, with the existing canonical 32-byte Base64URL token format; duplicate
fields, extra fields, query parameters and alternative content types fail closed. Structural errors
are proposed 422; invalid/malformed/expired/revoked/consumed capability and inaccessible associations
share safe 404. Incorrect configured Host or missing/null/foreign Origin is rejected before lookup
with a bounded 403. All responses, including errors, are no-store and contain no token reflection.
These are proposed HTTP semantics, not newly available API routes.

1. **Explicit browser action.** The authorized Core Workspace obtains the existing one-time Issue
   response in volatile memory. It prepares a dedicated named iframe with exactly
   `sandbox="allow-scripts"`. A transient form in the **Core document**, not in the sandboxed
   document, submits POST to the fixed Preview route and targets only that existing iframe.
   The form carries no Core JWT/account cookie value. Token is assigned only to the transient input
   value, never server-rendered markup, a URL, frame name or a saved form default; references and
   form controls are removed after submission. Application references are not memory zeroization.
   No default GET submission, `_blank`, redirect, fetch-to-srcdoc fallback or automatic retry exists.
   The frame target must not resolve to another tab/window after close/unmount; this is a browser gate.
2. **Exact binding.** Preview validates configured Host, exact Core Origin and closed body shape,
   hashes the token, then verifies the existing Publication -> Representation -> ArtifactVersion ->
   Artifact -> Project -> Account associations, readiness, explicit expiry and non-revocation.
   The client supplies no tenant/version/storage identity as authority. A different valid capability
   resolves only its own binding, never another Workspace-selected version. The controlled Core
   composition and server source allowlist must prevent mixing that selection before submission.
3. **Prepared private response.** A Worker-prepared, verified packet must exist before bootstrap.
   Build/transform/hash work remains in the existing Worker artifact; no new service or request-time
   rendering pipeline. Read and verify private packet bytes before the short authorization transaction;
   no transaction stays open across object storage reads or HTTP streaming. The packet identity/hash
   is pinned and rechecked with the Publication while holding the final transaction lock.
4. **Proposed one-use server record.** An internal bootstrap-consumption record binds the exact
   Publication, Representation, ArtifactVersion, tenant/project, derivative version/hash and existing
   expires_at. Its ID is operational only, never another bearer credential. It does not authenticate
   subsequent GET requests and is not represented as a normal cookie-backed browser session.
   Lock/revalidate Publication and persist consumption atomically, with a DB uniqueness guard allowing
   at most one consumption per Publication. No new default duration, renewal, viewer heartbeat or
   transport token is introduced. Exact table/helper SQL and record retention remain review items.
5. **Commit before response bytes.** Only after consumption commits may Preview send packet HTML.
   A revoke committed before that lock check denies bootstrap; a response authorized/committed first
   may finish after revoke. Commit failure sends no Preview bytes. Lost/truncated response after
   commit burns the one-use access; replay is safe 404 and cannot return another document or create
   another record. Recovery requires explicit revoke + new Publication/key + explicit expiry/Issue.
   This deliberately proposes idempotent *effect*, not repeatable document disclosure. Network write
   completion and iframe.load are not evidence that the user received or correctly rendered it.
6. **No follow-up resource transport.** The single response contains the exact supported version's
   pages, styles and allowlisted synthetic media. Resource GETs and 0102 token routes are unavailable
   in the 0103 composition. There is no credential-bearing browser session to recover on refresh.
   Packet HTML/script contains no token/hash/session secret. No Set-Cookie, ACAO, HTTP authentication,
   browser storage, messaging, prefetch/preload, ServiceWorker or Core credential forwarding is
   introduced. Cookie headers must not
   be used as authorization; no Core cookie scope can include the separate Preview site.

The parent Core page would need a narrowly scoped `form-action` allowing the exact Preview endpoint
origin as well as its existing approved targets. This is a **new Core CSP proposal**, not permission
to widen global policy. Preview retains `form-action 'none'`. Native POST support into the restricted
iframe, actual Origin behavior and frame-target races require real browser verification. If they
fail, do not allow `Origin: null`, add allow-forms/allow-same-origin, or bypass the browser with tools.

**Compatibility issue P1-O1 — limited R1 evidence available; owner Freeze WAIT:** the existing 0102 Core proof document sends
`Referrer-Policy: no-referrer`. The WHATWG [Origin-header algorithm](https://fetch.spec.whatwg.org/#append-a-request-origin-header)
sets Origin to null for a non-CORS POST using that policy. Therefore do not claim that copying the
current Core harness headers yields a usable exact-Origin bootstrap. P1 needs explicit review of
the submitting Core document's request/referrer policy and actual form-navigation behavior. R1 is
authorized for proof only, not as a Frozen product policy. Preview response no-referrer remains required. A null-Origin
exception, browser header injection or silent Core header weakening cannot resolve this issue.

**Resolution candidate P1-O1-R1 — APPROVED FOR DISPOSABLE PROOF; FINAL FREEZE WAIT:** use `Referrer-Policy: strict-origin` only on the
controlled Core Workspace/proof document that submits the form. Do not change global Core policy,
Preview response no-referrer, iframe referrerPolicy, sandbox, ACAO or allow missing/null Origin.
Allow no secure-to-insecure scheme downgrade and use only configured exact test origins.
The [Referrer Policy specification](https://w3c.github.io/webappsec-referrer-policy/#referrer-policy-strict-origin)
limits the Referer value to an origin under this policy; the Fetch Origin algorithm nulls it on a
downgrade, rather than on every non-CORS POST. This is a standards-based candidate, not browser proof.
The Core origin becomes visible in Referer as well as the required Origin header; no Core path,
safe resource IDs or secret may be sent in Referer. That limited disclosure and page-specific header
change have approval for the disposable experiment only. Origin remains defense in depth alongside the capability, never
tenant identity or sufficient authorization by itself.

The standalone proof must observe the unmodified browser-generated Origin/Referer and
targeted-frame navigation under the unchanged iframe referrerPolicy and sandbox. Reject null even
if the candidate fails. Do not intercept/inject request headers, relax sandbox or change production
routes to manufacture PASS. The subsequent explicit owner authorization allowed that disposable
experiment only; no Runtime/API/Migration implementation is authorized. See the linked v0.5 report.

Owner-authorized limited proof scope, separate from 0103 implementation:

- Disposable loopback-only servers and independent configured test sites, with a synthetic canary
  capability held only in process/browser volatile memory. No DB, customer data, real capability,
  Provider, Production/Hosted service, installed ServiceWorker or hosts-file change.
- Baseline Core no-referrer POST: observe actual Origin and require safe denial if null. Candidate
  Core strict-origin POST: require browser-generated exact Core Origin, Referer no more than Core
  origin, correct body-only canary and expected iframe document under unchanged sandbox/iframe policy.
- Missing/null/foreign Origin, GET and invalid body deny. No redirect, request-header interception,
  cookie authorization, automatic retry or token in a URL, form target name, saved diagnostics/logs.
- Report only bounded PASS/FAIL and configured-origin comparisons. Do not save POST bodies, raw
  canaries, HAR or screenshots containing secrets. Remove the exact owned temporary proof files and
  stop owned servers afterwards; repository runtime/source and approved 0102 files remain untouched.
- This proof can close only native POST/Origin feasibility for the browsers actually run. It cannot
  establish consumption atomicity, tenant isolation, BFCache safety or all twelve P1 acceptance cases.
  The owner's full browser matrix remains NOT RUN wherever actual execution evidence is absent.

This limited experiment was executed under the owner's separate approval; desktop Chrome/Edge
evidence is available in the v0.5 report. R1 remains awaiting final owner review. Product integration,
untested browser families and the full P1 acceptance matrix are not approved/passed by association.

### P1 delivery-profile changes requiring explicit approval

P1 is not a wrapper around 0102's unchanged multi-file bytes. It needs a new immutable versioned
derivative, while original ArtifactVersion/source/0102 derivative bytes remain unchanged:

- Inline verified CSS with hashes from final response bytes; no CSS imports, resource URLs or fonts.
- For the currently supported single fixed synthetic `generation-fixtures/media.svg`, embed only
  verified allowlisted SVG structure with equivalent accessible names. No general SVG ingestion,
  arbitrary image/data URL/blob or remote fetch is authorized by this proposal.
- All supported pages are delivered together. A fixed Application-owned, hash-authorized script
  activates one page at a time from verified inert templates, using controlled DOM operations, not
  innerHTML/eval or Provider code. At most one active main/h1; navigation stays in-document, with
  public non-secret page identifiers. Direct path navigation must not trigger an uncredentialed GET.
  No-JavaScript behavior is initial-page-only with no network submission, not a claim of full navigation.
- Proposed packet CSP uses default-src 'none', exact script/style hashes, img-src 'none', font-src
  'none', connect-src 'none', form-action 'none', object-src 'none', frame-src 'none', worker-src 'none',
  base-uri 'none' and frame-ancestors exact Core origin. System fonts, no ACAO, no-referrer, no-store,
  nosniff and the existing sandbox remain. Hash-authorized fixed script is a change from 0102's
  no-JavaScript delivery profile and needs explicit review, even though 0101 proved script isolation.

This changes navigation/asset representation and delivers **all supported version pages upfront**;
the owner conditionally accepts this only for a verified versioned Local/Synthetic derivative.
It is unsuitable to assume per-page confidentiality or later resource revocation. No packet-size or
timeout limit is invented; compressed and expanded size ceilings must be approved before coding.
The existing finite synthetic source allowlist must bound input, but does not replace an explicit
review of packet response size, preparation limits and dependency/asset validation.

### P1 lifecycle and BFCache limits

Consumed capability never grants another network disclosure, including browser POST resubmission,
reload or concurrent submission. Expired/revoked capability is denied synchronously at bootstrap.
When the Client learns of expiry/revocation it removes the iframe as a UI action, not a guarantee
that all viewers immediately lose delivered content. BFCache return blocks continued interaction
until revalidation through authenticated Core succeeds. Failed/unavailable revalidation makes the
Workspace unusable; it never issues a new token or performs automatic bootstrap. Close/unmount
discards references and invalidates callbacks; pagehide is best-effort cleanup only.

**BFCache is not solved merely by a one-use POST or Cache-Control: no-store.** It can restore already
delivered browser state without a new Preview request. T6 requires restoration revalidation and a
fail-closed Workspace, independent of pagehide/unload. The contract cannot promise no transient stale
pixels before a pageshow handler runs. The owner approved the interaction/revalidation requirement
for Local/Synthetic and retained transient restored display as a risk requiring independent testing,
not a zero-stale-paint guarantee. Real content and Production remain prohibited. A browser matrix
must establish actual behavior; successful interaction blocking does not prove zero restored frames.
Chrome's [no-store/BFCache documentation](https://developer.chrome.com/docs/web-platform/bfcache-ccns)
explicitly permits such restoration under some conditions; no-store is not a portable BFCache ban.

Browser POST bodies may be retained internally for resubmission and are visible in privileged
developer tools, extensions or request-body instrumentation. One-use consumption limits reuse but
does not prove browser memory/history-body erasure. T1 eliminates URL exposure, not those residual
risks. Raw POST-body capture, HAR/trace/screenshots containing secrets and diagnostic persistence are
prohibited in the Application and acceptance artifacts; tests retain bounded assertions only.
The WHATWG [navigation/session-history model](https://html.spec.whatwg.org/multipage/browsing-the-web.html#post-resource)
includes a POST resource/request body, so omitting the secret from a URL is not a claim that the
browser never retains submission material.

### Transport threat model — proposed controls, not proven results

| Threat / boundary | Required control / unresolved limitation |
|---|---|
| URL/history/request-target leakage | Fixed token-free bootstrap URL; no secret hostname, query, fragment, redirect or legacy-route fallback |
| POST body, Core XSS or privileged browser observer | No body capture/telemetry, transient control, no third-party script on Workspace; compromised Core/browser remains outside bearer secrecy guarantee |
| Missing resource authority after bootstrap | Single verified response, no resource session or anonymous file route; ordinary multi-file session alternative remains incomplete |
| CSRF / confused deputy | Exact configured Host and Core Origin, body capability, narrow Core form-action and Preview frame-ancestors; Origin is not tenant authority |
| Publication/version/tenant substitution | Server association checks and fixed prepared-packet identity under lock; source allowlist and actual-role negative tests |
| Concurrent bootstrap / revoke / lost response | One consumption DB guard; same Publication lock as revoke; commit before bytes; consumed replay denies; explicit recovery only |
| Expiry / refresh / BFCache | Approved One-shot semantics: deny new bootstrap; no live revocation guarantee; authenticated Core revalidation before resumed interaction, failure unusable; transient stale paint remains a Synthetic-only risk, not solved or authorized for real content |
| Form target hijack / close race | Dedicated existing frame, no window opening/alternate target; abort stale callbacks; browser proof required, not a name-as-authorization claim |
| Generated script / CSS / asset escape | New verified derivative profile only; fixed hash script/CSS; fixed safe SVG; no arbitrary code/URL/font/network |
| Isolation weakening for compatibility | Exact allow-scripts-only sandbox, independent sites, absent ACAO, no bridge/storage/secret cookie; failure blocks acceptance |
| Shared Worker authority | Existing WORKER-CROSS-TENANT-001 remains; narrow helpers do not imply Production tenant isolation |

### Transport Browser Acceptance Matrix — full 0103 cases NOT RUN; limited R1 evidence linked below

| ID | Planned case | Required assertion |
|---|---|---|
| TC-103T01 | POST from Core to existing sandboxed iframe | Fixed URL/body-only token; correct document and exact Origin under the explicitly reviewed Core referrer policy; existing no-referrer/null-Origin conflict exposed, no additional sandbox permission |
| TC-103T02 | landing/corporate/portfolio complete packet | Expected sections, accessible media, RTL and one active main/h1; exact version and all navigation work |
| TC-103T03 | Resource/network inspection | No CSS/image/font/API/other-version fetch, redirect, prefetch/preload or ServiceWorker; only approved fixed inline script/styles; no fallback to `/p/` |
| TC-103T04 | URLs, redirects, history locations, DOM/RSC and storage | No token in URLs/frame names/rendered response/RSC/storage/logs; only transient Core input value and request body allowed; do not archive raw browser traces |
| TC-103T05 | Unknown/malformed/expired/revoked/consumed capability | Same safe denial, no HTML packet, no redirect/reflection; GET/HEAD never disclose content |
| TC-103T06 | Foreign/missing/null Origin, wrong Host, extra/duplicate body fields | Reject without disclosure; no CORS/cookie/URL alternative |
| TC-103T07 | Two submissions, separate tabs and revocation race | At most one consumed response per Publication; independent Publications remain independent; revoke ordering established with DB evidence |
| TC-103T08 | Failed commit and response interruption | No bytes before commit; failed commit no consumption; post-commit loss no document replay or reissue |
| TC-103T09 | Refresh, POST resubmit, close/unmount, late callbacks | No second disclosure, recovered token, background issuance or popup/foreign target |
| TC-103T10 | Actual BFCache restore plus successful/denied/offline revalidation | No resumed interaction before authenticated Core revalidation; failure/unavailability unusable; no new token/bootstrap; actual persisted restore and any stale paint separately observed, never a zero-paint claim |
| TC-103T11 | DOM/Cookie/Storage/Core API/popup/download/top-navigation probes | Deny under unchanged sandbox; unsolicited messages ignored; SimpleForm never submits |
| TC-103T12 | JS disabled, CSP rejection and corrupted packet | Safe initial-only/degraded/unavailable behavior, no implicit network or policy relaxation; load alone never PASS |

Run with separately registered test sites, not merely two localhost ports. Required matrix from
the owner's review: desktop Chrome, Edge, Firefox and Safari; Chrome Android and Safari iOS.
Exact browser/OS versions, native device/simulator selection and availability still require an
explicit execution plan. Missing engines/devices are NOT RUN, never inferred from another engine.
Chromium viewport emulation does not establish Chrome Android/Safari iOS execution, and a generic
WebKit test does not by itself establish a Safari result.
No case is satisfied by an HTTP unit test, injected
browser request headers, disabled web security, DB-owner execution or a synthetic pageshow alone.

### Transport review questions before Freeze

1. P1/all-pages versioned derivative has conditional Local/Synthetic design approval only. Review
   exact fixed script/safe SVG/CSP/profile before Freeze; no ordinary reusable server session is claimed.
2. One-shot/lost-response semantics and explicit authorized recovery are approved. Exact bootstrap
   HTTP errors, consumption storage/SQL and response profile are not approved by that decision.
3. T6 interaction blocking/revalidation is approved in D6; independently test BFCache/stale paint
   without claiming prevention of all restored display. Real content remains prohibited.
4. Specify compressed/expanded packet and request-body bounds, size rejection behavior, internal
   consumption-record retention and safe cleanup. Cleanup must not enable consumed-capability reuse.
   Review exact schema/helper authority before any migration; do not invent retention defaults.
5. Review R1's separately authorized desktop proof results. Core policy is authorized only inside
   that experiment; accepting null Origin remains forbidden. Establish evidence for the unexecuted
   browser families and full acceptance matrix under an explicit plan before final transport Freeze.

If P1 is rejected, design another explicit body/header transport; do not fall back to URL tokens,
secret cookies, a shared IP session or weakened sandbox. These open choices block implementation.

All management responses use Cache-Control: no-store; capability-bearing response/body capture is
disabled. 0102 retains its existing per-file authority; P1 proposes a different single-response
authorization boundary with no-store/no-referrer. Neither boundary is interchangeable with the other.
The iframe uses `referrerPolicy="no-referrer"`.

A refresh or route unmount loses the raw capability. Safe Publication identity can remain in the
Core URL, but neither API nor browser reconstructs the token. If capability_issued=true and no
token is in memory, show the deliberate recovery: explicit Revoke -> explicit new Publication
with a new key -> explicit new expiry/Issue. The ready Representation can be reused under 0102.
No silent revoke, rotation, reissue, expiry extension or publication occurs.

### Proposed Workspace and multi-tab lifecycle — owner review pending

Browser lifecycle rules below describe Application behavior, not guaranteed erasure of browser
memory, history, tooling or already delivered bytes. T1..T7 are approved; the detailed lifecycle
implementation and P1 choices remain conditional on transport review. Approved D6 governs
revocation/expiry and BFCache interaction semantics; this does not approve the remaining UI choices.

Browser references checked for this revision: MDN [pagehide](https://developer.mozilla.org/en-US/docs/Web/API/Window/pagehide_event)
documents that lifecycle callbacks are not guaranteed on termination; [pageshow](https://developer.mozilla.org/en-US/docs/Web/API/Window/pageshow_event)
includes restoration from BFCache. MDN [iframe event behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe#error_and_load_event_behavior)
also documents that load is not successful-render evidence. These sources explain platform limits;
the lifecycle choices below remain product proposals, not browser guarantees.

| Event / situation | Proposed behavior and observable invariant |
|---|---|
| Explicit open succeeds | Keep the disclosed token only in the initiating mounted Workspace's volatile state; create the iframe only after the selected transport and exact binding are approved/validated |
| Close Workspace / route unmount | Remove the iframe, drop Application references, cancel pending reads and invalidate callbacks for the old Workspace; no automatic server-side revoke or expiry extension |
| Browser pagehide | Best-effort disposal of the iframe and capability references; no unload mutation and no server security dependence on this callback |
| Back/forward or BFCache restoration | Approved D6: block continued interaction until authenticated Core revalidation; failure/unavailability makes Workspace unusable. No new token or automatic bootstrap; stale-paint risk remains, not a zero-frame guarantee |
| Refresh / browser session restore / reopen safe Core URL | Resolve only safe route/Publication identities; no capability recovery from storage, history, query, fragment or another tab; no automatic issuance/publication |
| In-flight mutation completes after unmount | Do not repopulate state, assign an iframe or emit preview_opened for the departed Workspace; cancellation does not prove a server rollback |
| Issue response lost but server committed | Explicit same-key retry returns the existing Publication with token=null; use explicit revoke/new-Publication/new-key recovery, never manufacture a replacement token |
| document.hidden | Pause selected active-Job polling; this is not a close/revoke command. Keep no background mutation or renewal policy |
| Visible again | Perform an authorized read of the selected Publication before enabling/revealing access. If expired/revoked/not-visible, discard access state/remove iframe. Read failure gives the existing safe recovery state |
| Known expiry | Remove iframe/drop references when observed, including visibility/pageshow. Client clocks/timers are best effort; server time governs any new bootstrap, with no claim to erase delivered packet bytes |
| Explicit revoke | After confirmed commit, remove the initiating Workspace's iframe/token. Never claim that a lost response proves no revoke; an explicit idempotent retry can reconcile it |

Closing a tab is not a security boundary: unload/pagehide may not run on a process crash or
device termination. The server capability remains governed by its explicit expiry and terminal
revocation. No guarantee of immediate server revocation or memory zeroization is made on close.

Each tab has independent volatile state. No BroadcastChannel, storage event, local/session storage,
IndexedDB, SharedWorker, ServiceWorker, clipboard flow or postMessage channel transfers a capability
between tabs. The Application never reads another frame's URL to recover an absent token.

| Concurrent tab scenario | Proposed result |
|---|---|
| Two tabs issue against one Publication with the same key and canonical expiry | DB guard commits one issuance. Exactly one first response discloses the token; the other is replay with token=null. The losing tab cannot retrieve the winner's token |
| Same key with different canonical expiry | 409 IDEMPOTENCY_CONFLICT; no second capability |
| Different keys issue against one unissued Publication | Exactly one issuance commits; the other receives PREVIEW_CAPABILITY_ALREADY_ISSUED. No token rotation or second disclosure |
| Two tabs explicitly create distinct Publications/new keys for the same ready Representation | They may hold separate capabilities/expiries; Representation/files remain unchanged. Neither action implicitly revokes the other Publication |
| Revoke one of those distinct Publications | New bootstrap through that Publication is denied; the other remains governed by its own state. Already delivered content is not retracted |
| Another tab references the same Publication but has no token | Show lost-capability recovery; do not auto revoke/reissue. Explicit revoke prevents new bootstrap through this Publication, not immediate viewing of previously delivered bytes in other tabs |

There is no new single-tab lease, viewer-presence registry, heartbeat, cross-tab leader or immediate
cross-tab UI synchronization. A visible tab may retain already delivered content after another tab
revokes the same Publication; any new network disclosure must fail. On refresh/visibility/
restoration/read reconciliation it removes the iframe when invalid access is known. Do not claim
that revocation can erase content already delivered to any viewer.

## D5 — Workspace route, wireframe and viewport proposal

Proposed authenticated Web route:

```text
/projects/{projectId}/artifacts/{artifactId}/versions/{versionNo}/preview
optional safe query: publication_id=<UUID>
```

The optional query contains no token or arbitrary URL. On publication selection, the API projection
must agree with all route identities before any iframe exists. A mismatch fails safely; it does
not repin to another version. Back-to-Project uses the existing workspace route.

Reviewable SCR-20 subset wireframe, implemented with existing design tokens and controls:

```text
Back to Project                          Preview / Artifact Version N
Source Scope Version M                  Technical version status
-------------------------------------------------------------------
Publication status / Job result          [Desktop] [Mobile]
Explicit prepare action OR explicit expiry + open action
-------------------------------------------------------------------
Isolated Preview canvas, or safe empty/loading/error/unavailable state
-------------------------------------------------------------------
Explicit refresh / revoke / lost-capability recovery as applicable
```

The layout is RTL-first, responsive, light/dark compatible and keyboard operable. Controls retain
44px targets, visible focus, accessible names and native button/radio semantics. The iframe has a
specific accessible title including Artifact version. No animated resize is required.

Proposed Desktop default: fill the available canvas. Proposed Mobile target: **375 CSS px**, using
the Design System's reference size, clamped to available width on narrow outer screens. Show the
actual viewport width so a constrained canvas is not represented as exact device emulation. No
zoom, device user-agent emulation, orientation preset or new arbitrary width input is added.
Switching mode changes only geometry of the same iframe; it does not recreate it, reset navigation,
request a new capability, create a Job or increment preview-open counts.

The iframe keeps exactly `sandbox="allow-scripts"`; no allow-same-origin, forms, popup, download
or top-navigation sandbox token is added. No application postMessage bridge, handler or message
emission is introduced. Sandbox does not make browser postMessage impossible: unsolicited messages
must have no effect and their data must not be logged. Preview content remains on a separate registrable
test site. It receives no React callbacks, Core DOM access, Cookie/Storage access or backend secret.
System Font Only, hash-based authorization, absent ACAO and exact-version validation remain required.
P1's packet representation, fixed script/safe SVG and stricter resource CSP need separate explicit
approval; this section cannot silently approve them as an unchanged 0102 delivery profile.
The Core proof page permits embedding only its exact configured Preview origin through its
page-scoped frame-src policy; Preview frame-ancestors still permits only the exact Core origin.
No wildcard or global Core CSP relaxation is proposed.

Prompt/direct editing, feedback, guest sharing, approval and revision controls are not rendered as
working or disabled placeholder features in this slice. Those SCR-20 actions belong to their own
Backlog contracts. Public human-readable Artifact review statuses remain deferred as described in D2.

## D6 — One-shot Delivery and Revocation Semantics — APPROVED

**Scope:** Local/Synthetic Only. Authority: owner's explicit six-clause D6 decision in this
conversation, recorded 2026-10-17. Approval covers these semantics only, not the whole local ADR.

1. **Pre-delivery:** before delivery the server MUST validate Capability, Publication, exact
   ArtifactVersion, Expiry, Revocation and consumption state. Capability consumption MUST be atomic
   and successful at most once.
2. **Post-delivery:** received content may remain in browser memory/state. Expiry and Revocation
   prevent new bootstraps; they do not guarantee removal of previously delivered bytes.
3. **Active Workspace:** iframe removal after the Client learns of expiry/revocation is UI behavior,
   not a guarantee of immediate access termination for all viewers.
4. **BFCache:** on return from BFCache, the Workspace MUST revalidate through authenticated Core
   before continued interaction. Failure or inability to validate MUST make the Workspace unusable.
   This check MUST NOT issue a new token or perform automatic bootstrap.
5. **No Live Access Guarantee:** 0103 guarantees neither immediate revocation of already delivered
   content, deletion of saved copies nor live access control.
6. **Production Boundary:** real content, Hosted Preview and Production security claims remain
   prohibited until an independent contract and tests are approved.

Interaction blocking alone does not prove prevention of even a single stale restored frame. That
limitation stays in the threat model and independently observed Browser Gate; no such guarantee is
approved for this synthetic proof. Server response-write completion cannot prove user receipt.

### D6.1 — State, polling and honest render-status proposal — NOT APPROVED

The following detailed state table, polling interval and recovery-control choices remain proposals.
They must conform to the approved six D6 clauses but are not approved by association.

| State/evidence | Workspace behavior |
|---|---|
| GEN-01 / composition unavailable | Controlled unavailable state; no writes or iframe |
| No selected Publication | Exact version metadata plus explicit prepare action |
| Publication allocated/publishing + Job queued/running | Qualitative processing state; no fabricated percentage or token |
| Ready, unissued Publication | Explicit future-expiry input and Issue action |
| Ready + valid token in memory | Strict URL prohibition already applies; no submission/iframe access until the replacement transport itself is approved |
| PRV-01 | Nonblocking navigation-loading indication; recovery controls remain usable |
| PRV-02 | Display isolated canvas after navigation load; do not claim verified render/health |
| PRV-03 / known expiration/revocation/not-visible resource | Safe generic unavailable view; discard in-memory token and remove iframe |
| PRV-04 / known preparation or validation failure | Bounded Job failure and authorized recovery/back action |
| PRV-05 / known rejected origin, binding or capability | No iframe; safe unavailable view and Back action |
| Network/metadata request failure | Keep safe selected IDs/expiry form input; remove access-bearing iframe if access state cannot be established; explicit retry/back |
| Issued Publication, token absent | Lost-capability recovery from D4 |

A cross-origin iframe `load` event can occur for an error document. `error` is not a reliable
availability signal. The implementation must not read its contentDocument, add postMessage,
weaken sandbox/CORS, infer HTTP 200 from load, or invent a render timeout to claim PRV-02 success.
Known server failures come from authorized metadata/Job status; rendering correctness is separately
proved in the controlled Browser Gate. A visible reload/back action remains available even if
navigation never reports load. Broader availability measurement belongs to OBS-F3-07.

Proposed polling reuses the already accepted Context Inbox pattern: 5 seconds only while the
selected Job is queued/running; pause on document.hidden, resume when visible if still needed,
finish/cancel the preceding request before another, and stop on terminal state/unmount. Use the
existing Job Status API as truth. Do not auto retry a mutation, resubmit a failed Publication,
redeliver a Job, enqueue work or invoke any Provider. Read failure requires explicit refresh.

No `POST /jobs/{job_id}/retry` or new Preview recovery endpoint is authorized here. Recoverable
publication preparation still resumes through the approved controlled same-ID operator/harness
path. The Workspace offers safe refresh/back actions, not a misleading active retry button for a
command it cannot perform. Exposing recovery as a user command needs a separate contract.

0102's per-file authority is not inherited. Approved D6 selects One-shot enforcement at bootstrap,
without live control of delivered content. P1's exact lock/commit/HTTP implementation still needs
review and proof. Detailed UI cleanup is not server access authority or a claim to erase bytes.

## D7 — Analytics and diagnostics proposal

The PRD's `preview_opened` is a client interaction when a user explicitly opens an authorized exact
version, not a server completion/availability metric. Propose one existing-pipeline event per
explicit open intent, with a stable event_id reused on ingestion retry. A viewport change or read
refresh does not create another event. The event does not assert successful rendering.

Its new closed per-event property allowlist is `artifact_id`, `artifact_version_no`, `publication_id`
plus the already accepted common envelope. No path, raw URL, token/hash, customer title, Scope/AST
text, arbitrary exception or browser diagnostic context is permitted. IDs are correlation fields,
never metric labels. The Local/Synthetic proof uses an in-memory sink without an external exporter,
third-party script or analytics SDK. No new analytics provider is selected. Extending the event
schema requires the contract test first; adding generic logger properties is not an alternative.

## Implementation sequence after approval

1. Create the linked 0103 development/test records with approved decisions, sources and traceability.
2. Add behavior-based HTTP contract tests before router/query implementation. Preserve the existing
   command transactions, idempotency namespace and token construction; no second Source of Truth.
3. Prove JWT/membership, actual database role, safe projections, replay and tenant/ownership guards
   against disposable Local/Synthetic PostgreSQL; no DB-owner-only acceptance.
4. Implement the approved SCR-20 subset and exact capability handling using existing Web/auth/token
   layers. Generate/sync HTTP types from the approved OpenAPI boundary.
5. Connect controlled authenticated HTTP -> existing commands -> relay/Worker -> private delivery ->
   iframe for three project types. Keep commands explicit and source identities pinned.
6. Run the matrix below, npm test/validate and appropriate lint/typecheck/build/security checks. Final
   records list all skips/limitations and cannot claim PASS for unexecuted runtime cases.

## Planned requirement and acceptance matrix

These are planned cases, not executed evidence. The approved matrix will be copied into 0103's
development record before implementation.

| Requirement | Authority / proposal | Planned implementation | Planned verification |
|---|---|---|---|
| REQ-10301 | FE-F3-05; SCR-20; D1/D2 | Controlled FastAPI router + allowlisted query projections | TC-10301: exact version/Scope association; closed DTOs; feature off/zero effects |
| REQ-10302 | API/Auth baseline; D3 | Existing JWT/Tenant dependency and command adapter | TC-10302: real JWT verifier, inactive membership, ownership, missing/cross-tenant uniformity, no secondary existence lookup |
| REQ-10303 | ADR-089; D2/D3 | Existing Publish/Issue/Revoke command transactions | TC-10303: same-key replay/conflict/concurrency, same Job, no duplicated Outbox; one-time response and no token in idempotency store |
| REQ-10304 | ADR-089; D4; owner's approved D6 | Explicit expiry form/volatile capability after transport approval; One-shot boundary, no live control | TC-10304 / TC-103T05..10: before-delivery expiry/revoke/consumption, manual lost-response recovery; no automatic reissue or delivered-byte erasure claim |
| REQ-10305 | FE-F3-05; FR-10-01/04; D2/D5 | Exact-version Workspace component and proposed wireframe | TC-10305: real three-type Browser flow, correct version labels, safe error/empty/unavailable and immutable source |
| REQ-10306 | FE-F3-06; FR-10-02; D5 | Same iframe, Desktop/Mobile geometry controls | TC-10306: keyboard/RTL/LTR, actual width, no shell overflow, same navigation/token/Job and no new open event |
| REQ-10307 | ADR-088/089; D5/D6 | Existing Preview delivery boundary, restricted iframe | TC-10307: independent sites, parent DOM/Cookie/Storage denied, network/forms/popups/download/top-navigation denied, no cross-version assets or messaging bridge; unsolicited messages ignored |
| REQ-10308 | UX PRV-01..05; D6 | Bounded state controller and existing Job Status reads | TC-10308: hidden/visible/non-overlap/stop behavior, load of a 404 never proves render success, known failures recoverable without automatic commands |
| REQ-10309 | PRD preview_opened; analytics baseline; D7 | Closed event contract and safe in-memory test sink | TC-10309: stable event identity, no resize duplication and negative leakage across logs/errors/events/HTML/RSC/storage/Outbox/Queue |
| REQ-10310 | Owner T4..T6 and approved D6; detailed UI still proposed | Per-Workspace state and authenticated Core revalidation before continued interaction, only after transport approval | TC-10310 / TC-103T09..10: real BFCache restore, denied/unavailable revalidation unusable, zero automatic token/bootstrap; no stale-paint prevention claim |
| REQ-10311 | Owner pending review's concurrency criteria; ADR-089 DB guards | Existing Publication/issuance transactions, without cross-tab token transport | TC-10311: same/different keys across two Browser contexts, one first disclosure, no replacement token, independent Publication revocation |
| REQ-10312 | Owner approved T1..T7/D6; P1 design conditionally accepted, exact transport unapproved | Transport design only; no implementation, API or Migration | TC-10312 / TC-103T01..12: body-only transport, no URL/Storage bearer, exact binding/consumption/expiry/revocation, isolation and restoration; every new transport test NOT RUN |
| REQ-10313 | Owner's explicit ADR-090 v0.6 retention review, recorded in v0.7 | Contract design only: durable consumed state through at least expiry, independent idempotency TTL, replay-safe cleanup; no schema or cleanup implementation | TC-103R01..06 below: all NOT RUN; no Runtime/DB acceptance claimed |
| REQ-10314 | Owner's explicit identity-only response selection in v0.7; numeric/request refinements approved in REQ-10316 | Contract design only: uncompressed final UTF-8 HTML response body; no proxy/runtime changes | TC-103S02..04: planned boundary cases, NOT RUN |
| REQ-10315 | Historical v0.8 design proposal; approval/refinements superseded by REQ-10316 / v0.9 | Review document only: original size proposal and rationale; no executable implementation | TC-103S01..08: planned boundary checks, NOT RUN |
| REQ-10316 | Owner's explicit v0.8 S1/S2/R2 approval and subsequent P2/P3 answers, recorded in v0.9 | ADR only: approved caps/error mapping/no-purge scope, exact parser and precedence; immutable prepared bytes before atomic consumption; no Runtime/SQL | TC-103S01..08, TC-103P01..06 and TC-103R01..06: NOT RUN; no acceptance claimed |
| REQ-10317 | Historical P4 proposal; owner approval now recorded in REQ-10321 | Contract only: versioned packet transformation, fixed navigation script, exact-source SVG and hash-only CSP; no source/profile/Worker/schema implementation | TC-103D01..08 below: all NOT RUN; no Browser acceptance claimed |
| REQ-10318 | Owner's design continuation and explicit Option A selection; actual Alembic 0040/0041 and ADR-089 authority boundary | Additive closed-profile design approved; exact consumption schema/helper DDL still requires review; no Migration/Runtime change | TC-103M01..06 below: proposed future compatibility checks, NOT RUN |
| REQ-10319 | Owner's explicit P5 logical-model/SQL-design approval and Capability-bound authentication clarification | [P5 SQL review source](ADR-090-p5-sql-contract.md): proposed DDL, FK/PK/RLS, fixed Preflight/Consume, lock/commit/ACL boundaries; not an applied schema or migration | TC-103SQL01..12 in review source: all NOT RUN; SQL not compiled/executed |
| REQ-10320 | Owner's P4 v0.10 source review at d794ffa: identities/initial page approved; four mandatory refinements, 2026-10-18 | P4.R1..R4 and v0.13: exact DOM ownership/reference/failure rules, closed SVG boundary, reviewed CSP hash provenance and separate zero-request/zero-navigation invariants; documentation only | TC-103D02..07 strengthened; TC-103D09..12 planned below, all NOT RUN; no Browser/Runtime/SQL authorization |
| REQ-10321 | Owner's explicit final P4 architecture decision after reading the complete v0.13 text, 2026-10-24 | P4 current status and v0.14 decision record: complete P4 contract FROZEN, executable bytes/proofs and other ADR gates still independent | Source-to-decision status audit only; P4 tests NOT RUN; no Freeze of P5 SQL/full ADR or implementation permission inferred |
| REQ-10322 | Same instruction: continue independent P5 SQL review only | P5 review document section 10: static constraint/authority/concurrency/commit review and open installation preconditions; SQL blocks unchanged | TC-103SQL01..12 remain NOT RUN; text-only SQL preservation check; no parser/compiler/database execution |
| REQ-10323 | Owner's P5 Installation Authority decision, 2026-10-24: SQL-contract text design only | P5-SQL r2 sections 2/3/6/6.1/11: temporary independent Superuser Installer, restricted final definer ownership and pre-commit raw/effective ACL/role/schema/RLS assertions; no Helper owner CREATE or Worker installation rights | TC-103SQL13..16 proposed NOT RUN; source/privilege-path review and existing regression checks only; exact SQL acceptance and execution still separate NO-GO gates |

Additional final gates: real-role revoke/issue races, immutable source byte preservation,
one-time capability disposal on unmount, cancellation of pending metadata requests, 375/768/1024
outer viewports, accessible iframe title/focus/44px targets, light/dark contrast and reduced motion.
The HTTP gate also covers Web Origin/CSRF enforcement, no client-supplied authority or arbitrary
upstream target, redirect credential safety and no token in HTML/RSC/Server Action/cache state.
No full human usability, screen-reader certification or Production security claim follows from the
synthetic automated matrix. Existing shared-Worker risk WORKER-CROSS-TENANT-001 remains open.

The Browser Gate must independently assert expected synthetic page/section content, exact-version
assets, actual viewport widths, network denials and sandbox behavior. Neither iframe.load nor the
absence of JavaScript exceptions substitutes for those assertions. Multi-tab and BFCache cases are
planned Browser/DB acceptance cases, not conclusions derived from unit tests or draft prose.

## Review and approval boundary

Review remaining D1..D7 proposals, especially the new authenticated HTTP surface, Member query visibility, archived-Project
disposition, explicit no-default expiry, 375px/available-width viewports, honest iframe load semantics
and preview_opened interaction definition. Approving this ADR would authorize the specified controlled
implementation only. Customer/Hosted access, real Provider, general runtime activation, new SQL
authority, automatic chaining, commit and push require their existing separate authorization.

Current result: **WAIT / PENDING CONTRACT REVIEW; implementation NO-GO**. T1..T7 and the six D6
One-shot semantics are approved. P1 design/all-pages derivative and manual lost-response recovery
are conditionally accepted for Local/Synthetic only. The exact transport, Origin policy, derivative/
CSP/SQL, detailed UI/state/polling choices and other D clauses/wireframe remain unapproved.
No proposed decision has been applied as product behavior. This draft introduces no runtime code,
migration, dependency, event-schema change or external document write.

## Proposal verification — 2026-10-17

Only this proposed ADR and the ADR index changed. The index now also accurately labels the already
accepted Local/Synthetic ADR-089; its contract and implementation are unchanged.

- Initial `npm test` passed Node/Renderer/Web suites, then stopped before API execution because
  the default external uv cache was inaccessible. This run is not a full PASS.
- Repeated full `npm test` with process-scoped UV_CACHE_DIR in the workspace and an owned temporary
  directory: **PASS**. API: **592 passed / 246 skipped**. Worker: **376 passed / 67 skipped**.
  All Node/Renderer/Web suites passed. Database/Redis service variables were absent for this
  ordinary regression; skipped integrations are not executed acceptance evidence.
- API reported one existing Starlette/httpx deprecation warning and one pytest cache-write warning;
  Worker reported one pytest cache-write warning. No warning was hidden and no test was weakened.
- `npm run validate`: **23/23 PASS**. `git diff --check`: **PASS**, with an index-file line-ending
  warning only. New ADR trailing-whitespace inspection found none; all local Markdown links resolve.
- `npm run scan:secrets`: **PASS**, 1,234 publishable text files inspected.
- The exact owned temporary directory was removed after execution. Existing service containers,
  user databases, dependency versions, runtime code and approved SQL were untouched.

These are proposal/repository regression checks, not execution of TC-10301..09. No new authenticated
HTTP, Browser, PostgreSQL or Hosted acceptance gate for 0103 has been executed. The implementation
remains awaiting an explicit decision on D1..D7; no commit/push was performed.

### v0.2 review continuation

The owner's WAIT/NO-GO verdict is recorded explicitly. Only proposal text changed to expose the
transport conflict and define reviewable close/refresh/BFCache/concurrent-tab semantics and planned
acceptance rows. No new transport, API, schema, browser behavior or lifecycle rule was implemented.
The full-suite results above belong to the earlier proposal check; they are not a new v0.2 execution
or evidence that TC-10310..12 passed. Documentation validation for this revision is recorded below.

v0.2 documentation checks: `npm run validate` **23/23 PASS**; `git diff --check` **PASS** (index-file
line-ending warning only). No runtime code changed, so the full suite was not repeated for these
prose refinements. No new Browser/DB test result is claimed. Only ADR-090 and the previously edited
ADR index are dirty; commit/push and external document writes have not been performed.

### v0.3 strict transport direction — 2026-10-17

Only the explicit T1..T7 constraints are recorded as approved. P1, its new response/profile/consumption
semantics, proposed HTTP route and Browser Acceptance Matrix are contract-design artifacts only.
No API was registered/called, Migration written/executed, dependency added, source/derivative changed
or browser experiment run for P1. The previous D1..D7 and wireframe are not promoted to Frozen.
No linked development record is marked complete; 0103 remains WAIT / implementation NO-GO.

The new matrix contains twelve NOT RUN cases, with BFCache pre-display semantics explicitly open.
Current revision verification is recorded after the checks below; historical results above are
not evidence of the proposed transport's correctness.

v0.3 verification:

- Full `npm test`: **PASS** for the existing repository suite. Node/Renderer/Web suites passed;
  API **592 passed / 246 skipped / 2 warnings**; Worker **376 passed / 67 skipped / 1 warning**.
  Process-scoped workspace UV cache and a newly owned temporary directory were used. Database/Redis
  URL variables were removed from this child process; no migration or external runtime gate ran.
- Warnings remain the existing API Starlette/httpx deprecation and API/Worker pytest cache-write
  permission warnings. No dependency, test or warning policy was changed to obtain a PASS.
- `npm run validate`: **23/23 PASS**; `npm run scan:secrets`: **PASS**, 1,234 publishable text files.
  Tracked and new-ADR diff/whitespace checks passed; Git reports line-ending warnings only.
- The exact task-owned temporary directory was removed after the suite. No user service/database
  or runtime source was changed. Only ADR-090 and its index remain dirty; no commit/push/Drive write.
- **TC-103T01..12: NOT RUN. 0103 Browser/DB acceptance: NOT PASS.** These regression checks do not
  resolve P1-O1, BFCache behavior, pending limits or any owner approval question.

### v0.4 owner decision — One-shot semantics, 2026-10-17

The owner's six-clause D6 text is now recorded as approved, with corresponding Lifecycle, threat
model and planned-test alignment. It does not approve the whole local file or authorize execution.
P1's conditional design approval and manual unrecoverable-response trade-off are recorded; no
server acknowledgement is represented as proof of actual receipt. Misleading cross-tab wording
that implied revocation immediately invalidated all existing viewers was removed.

| Gate | Current state |
|---|---|
| One-shot instead of Live Access Control; six D6 semantics | APPROVED, Local/Synthetic only |
| Origin verification / P1-O1 | BLOCKED; R1 page-specific strict-origin is a proposal only |
| Native POST into unchanged sandbox | NOT VERIFIED |
| Compressed/expanded size caps and consumption retention/cleanup | PENDING; no invented defaults |
| Desktop Chrome/Edge/Firefox/Safari, Chrome Android, Safari iOS | Required; exact versions/device plan pending; NOT RUN |
| TC-103T01..12 | NOT RUN |
| Full ADR-090 Freeze | WAIT |
| 0103 implementation / new API / Migration | NO-GO |
| Hosted Preview / Customer Content / Production claim | NO-GO |
| Commit / Push | NOT AUTHORIZED |

R1 is a standards-based resolution candidate, not a verified fix. No Core/Preview header, sandbox,
runtime file, migration, proof harness, endpoint or external document changed. Browser execution
requires separate limited authorization; no existing gate is relaxed or reported as passing.

v0.4 documentation verification: `npm run validate` **23/23 PASS**; `npm run test:records`
**6/6 PASS**; tracked and new-file diff/whitespace checks **PASS** (Git line-ending warnings only).
Full `npm test` was not repeated for this prose-only revision; v0.3's API/Worker results and skips
remain historical regression evidence, not a new runtime result or P1 acceptance. All twelve
transport Browser cases remain NOT RUN. No 0103 increment is marked complete.

### v0.5 owner-authorized R1 disposable proof — 2026-10-17

The owner explicitly authorized R1 only for a temporary Local/Synthetic browser proof with valid
HTTPS, unchanged iframe referrerpolicy and allow-scripts-only sandbox, no null-Origin exception,
real token, cookie/session, product database, Runtime/Migration or Hosted change. The preceding
v0.4 notes are historical; the limited experiment authorization supersedes their execution WAIT,
not the 0103 implementation NO-GO or requirement for final owner review.

The [R1 proof report](ADR-090-r1-disposable-proof-report.md) records actual headers, browser versions,
HTTP outcomes, TLS trust/setup, failures, limitations and cleanup. Final native POST feasibility
results: Chrome/155.0.8059.40 and Edg/155.0.4283.45 **PASS** on separate HTTPS test sites with normal
TLS verification. Core strict-origin preserved exact Core Origin and origin-only Referer; the
unchanged no-referrer iframe accepted the native parent-form navigation and rendered the expected
synthetic heading. Baseline null Origin, foreign Origin and absent Origin were denied; invalid
dummy canary was denied even with correct Origin. No real Capability/Publication implementation
was exercised. No Windows trust-store change or certificate-error bypass was used.

| Gate | Updated evidence / decision |
|---|---|
| R1 design | APPROVED FOR PROOF only; final Freeze requires owner review |
| Origin and native form/sandbox feasibility | Limited proof PASS on actual listed desktop Chrome/Edge headless versions |
| Firefox, Safari, Chrome Android, Safari iOS | NOT RUN |
| TC-103T01 / TC-103T06 | Limited supporting R1 evidence only; full 0103 acceptance NOT EXECUTED |
| Other full P1/0103 Browser cases, BFCache, DB/concurrency | NOT RUN |
| Size / retention / exact derivative-CSP-SQL / other D clauses | Review still pending |
| ADR-090 Freeze | WAIT |
| 0103 implementation, Hosted Preview, Customer Content | NO-GO |
| Commit / Push | NOT AUTHORIZED |

R1 does not make Origin tenant authority or replace independent Capability/Publication validation.
No source-profile, parent global CSP, production route, schema or approved 0102 Runtime was changed.

v0.5 verification: disposable proof profiles/keys/sources and regression temporary files were removed
within the validated exact task directory; final proof port closed. Full existing `npm test` PASS
(API 592 passed/246 skipped/2 warnings; Worker 376 passed/67 skipped/1 warning; Node/Renderer/Web
passed). `npm run validate` 23/23 PASS; final secret scan PASS on 1,235 publishable text files;
diff/whitespace checks PASS with line-ending warnings only. Pre-cleanup scanning correctly found the
temporary TLS private key; cleanup, not a scan exception, resolved it. Details and preparation
failures are in the linked report. No 0103 implementation or full-browser-matrix PASS is claimed.

### v0.6 design continuation after authorized checkpoint push — 2026-10-17

The owner's explicit "push, then continue" authorized publication of the existing documentation
checkpoint. Commit `f269132f5aa302db651e2c0b378dda8d26e14dd9` was pushed to the existing
`codex/s1-d02-text-context-api` branch; remote SHA matched. This does not approve R1 Freeze, another
browser experiment, Runtime/API/Migration work or the remaining D clauses. This continuation is
local design only; no additional commit/push or implementation is inferred.

#### Remaining size contract: findings, not new limits

Source inspection of [the canonical AST schema](../../packages/contracts/generation-ast-v1.schema.json)
confirms 12 maximum Pages, 30 Sections per Page and 100 Asset references. Those are existing
structural limits from [ADR-082](ADR-082-generation-component-registry-and-ast.md), **not** a
compressed/expanded HTML-response byte budget. HTML escaping, repeated media, template markup and
fixed script/CSS can change the derivative size. Do not equate AST JSON size or the tiny R1 response
with a maximum P1 packet, and do not infer a numeric limit from the browser proof.

[ADR-089](ADR-089-local-preview-publication-and-capability.md) explicitly declines to invent
numerical body/retention defaults. No approved P1 packet byte ceiling or compression policy was
found in the reviewed source boundary. The experimental R1 request guard is not inherited.

The following additional design choices require explicit approval before coding:

| Decision | Required contract |
|---|---|
| Bootstrap request bound | Maximum serialized body bytes and whether request Content-Encoding is rejected; exact handling of equivalent percent-encoded form values/padding |
| Packet expanded bound | Maximum final UTF-8 HTML bytes after all pages/styles/media/fixed script are embedded; count actual bytes, not characters |
| Packet wire bound | Maximum compressed/wire bytes and allowed response encoding, or explicitly identity-only delivery; a proxy must not silently change this choice |
| Failure boundary | Prepare/read/verify/reject oversized packets before capability consumption and before any Preview bytes; no truncate-and-serve or partial valid artifact |
| Error semantics | Freeze bounded request-size vs packet-preparation failure codes; do not silently reuse unrelated codes or expose content/hash/storage details |

No packet builder, benchmark, compression library or new response mode was created or executed in
this continuation. Numeric caps remain PENDING, rather than choosing a default unsupported by an
approved source. An identity-only proposal would remove response decompression from this profile,
but even that encoding decision is not approved by association with P1.

#### Consumption retention: replay-resurrection risk

The existing management-command idempotency retention is 24 hours (D3), while capability expiry is
explicit and has no approved maximum duration (D4). These are different boundaries. Applying that
24-hour TTL to a new consumption row would be unsafe if the capability remains valid longer:

```text
capability consumed -> consumption row deleted by short TTL
-> same still-valid capability presented again
-> missing row mistaken for unconsumed -> second disclosure
```

The minimum rule proposed in v0.6 was subsequently approved by the owner. The v0.7 section below
is authoritative for that invariant; numeric purge policy, schema and cleanup execution remain
unapproved. The existing permanent one-issuance guard from ADR-089 is independent of management
idempotency TTL and remains unchanged.

### v0.7 owner-approved consumption-retention invariant — 2026-10-17

**Source:** owner's explicit review titled "ADR-090 v0.6 — Capability Consumption Retention" in
this conversation. This records that decision locally; it does not claim a new Canonical Drive
review or change. Only Size/Retention contract completion and acceptance-scenario design are
authorized. No Runtime, API, Migration, additional browser experiment, commit or push is authorized.

#### Approved safety rules

1. Each Capability permits at most one successful Bootstrap consumption. Consumption is a server
   transaction boundary, not proof that a client received the complete response; D6 lost-response
   semantics remain unchanged.
2. The consumption record **or an equivalent durable consumed state** MUST remain at least through
   the Capability's `expires_at`. A separate row is not mandated by this decision.
3. The management-command Idempotency TTL of 24 hours MUST NOT automatically delete or reset that
   consumed state. Expiring an idempotency record must not make a consumed Capability reusable.
4. Cleanup is permitted only when it cannot restore validity, authorize another consumption,
   reactivate the Publication, extend expiry or enable issuance of the same Capability again.
5. Concurrent consumption MUST be atomic: checking for an existing marker before inserting one is
   insufficient. At most one contender may commit consumption and proceed to packet disclosure.

Even after `expires_at`, cleanup is not automatically safe. The authoritative validation path
MUST reject expired Capabilities independently of the removed consumption record. Deleting the
record must not reopen issuance or consumption. Existing revocation and one-issuance guards stay
independent. No early-deletion exception for revoked Capabilities is introduced.

#### Separate time semantics; physical schema not authorized

| Contract time | Meaning | Approval boundary |
|---|---|---|
| `expires_at` | Explicit validity boundary; at or after this server time no new Bootstrap is authorized | Existing Capability contract; minimum safe consumed-state retention boundary, not an exact deletion time |
| `consumed_at` | Time of the first atomically committed consumption; not response receipt or UI render time | Semantic contract term; does not authorize a new DB column or a response field |
| `purge_after` | Earliest time at which cleanup may be considered, still subject to replay-safety checks | Proposed policy term with `purge_after >= expires_at`; no numeric value, default, deadline or scheduler approved |

The relation `purge_after >= expires_at` expresses the approved minimum, not permission to purge
at equality. Reaching `purge_after` alone never authorizes deletion. The final policy still needs
explicit review of audit needs, data-retention requirements, storage cost and cleanup authority.
Do not invent a fixed extension, maximum lifetime, automatic deletion job or manual cleanup command.
No schema, SQL, broad delete grant or storage/object GC is authorized by these semantic names.
Payload bytes, raw token and token-bearing response never belong in consumption records or logs.

#### Retention acceptance matrix — planned only, all NOT RUN

These supplement, rather than replace or pass, TC-103T01..12. They require a future explicitly
approved implementation and controlled DB test environment. Time must be controlled in the tests;
no 24-hour wall-clock wait or invented production retention duration is required.

| Case | Scenario | Required observation | Execution |
|---|---|---|---|
| TC-103R01 | Consume a Capability whose explicit expiry is more than 24 hours away; advance beyond management Idempotency TTL but remain before expiry; replay | Idempotency expiry cannot remove equivalent durable consumed state; replay discloses no packet and creates no second consumption | NOT RUN |
| TC-103R02 | Two concurrent valid Bootstrap requests for the same Capability | At most one consumption commits and may disclose the packet; loser cannot bypass the durable guard; no check-then-insert race | NOT RUN |
| TC-103R03 | Present the Capability at and after `expires_at`, both with retained state and after otherwise eligible cleanup | Independent server-time expiry validation denies every request; absence of a marker cannot be interpreted as a usable Capability | NOT RUN |
| TC-103R04 | Evaluate cleanup before expiry or under a proposed `purge_after` earlier than expiry | No consumed-state removal; the minimum retention invariant remains intact; no unapproved default or idempotency TTL controls this decision | NOT RUN |
| TC-103R05 | Exercise cleanup after expiry only when replay-safety preconditions are met, then replay and attempt reuse of the same issuance | No token resurrection, second disclosure, expiry extension, Publication reactivation or new issuance of the same Capability; independent guards remain effective | NOT RUN |
| TC-103R06 | Fail the consumption transaction, and separately interrupt the response after committed consumption | Rollback leaves no committed consumption/disclosure; post-commit loss leaves durable consumption through the safety boundary and does not enable retry disclosure | NOT RUN |

#### Remaining decisions and release boundary

**Subsequent explicit owner decision:** in response to the focused Size-contract question, the
owner selected "without compression; identity-only" for Local/Synthetic P1 response delivery.
This closes response compression direction only, not the numeric size contract or implementation
gate. The earlier v0.6 encoding question is historical and superseded for the response direction.

Under this direction the complete final UTF-8 HTML response body is delivered without response
compression; its encoded payload-byte count equals its expanded HTML UTF-8 byte count. A future
implementation must not silently enable gzip/Brotli or intermediary body transformation. HTTP/TLS
headers and transfer framing are not HTML payload bytes. Request Content-Encoding and canonical
form handling remain separate review items; identity-only response approval does not settle them.
No server/proxy configuration, packet builder or encoding implementation is changed here.

Size acceptance must also be specified before implementation. The following design cases use
**unapproved** byte limits, not numeric defaults. Their exact
success/error expectations remain subject to the Size contract review; all are NOT RUN.

| Case | Proposed boundary coverage | Unresolved input |
|---|---|---|
| TC-103S01 | Serialized request at the approved byte cap and one byte above; count the received encoded body, not decoded token characters | Request cap, encoding/percent-encoding policy and bounded error response |
| TC-103S02 | Final embedded UTF-8 HTML at its cap and one byte above, including Persian/multibyte text, escaped content, media and fixed template bytes | Expanded-response cap and exact derivative profile |
| TC-103S03 | Identity-only response-body bytes equal final HTML UTF-8 bytes; check the approved cap and one byte above; no silent compressed response or intermediary transformation | Numeric unified response-body cap and exact enforcement/error behavior; transfer framing is not part of the HTML payload-byte cap |
| TC-103S04 | Oversized/invalid packet preparation fails before consumption commit and before Preview bytes; no truncated packet or token/content-bearing diagnostic | Exact bounded preparation/size errors and reviewed delivery implementation |

No benchmark, builder, compression path or executable Size test was added. These are acceptance
design questions, not evidence that the caps or proposed behavior have passed review or execution.

| Decision / gate | Status |
|---|---|
| Minimum retention through `expires_at`, atomic at-most-once consumption, TTL separation | APPROVED |
| Replay-safe cleanup even after expiry | REQUIRED; executable proof NOT RUN |
| Numeric `purge_after` policy, deletion deadline, cleanup mechanism/authority | PENDING; no default assumed |
| Local/Synthetic P1 response encoding | Identity-only APPROVED by explicit owner answer; no response compression |
| Serialized request cap/policy, unified final UTF-8 response-body cap and error contract | PENDING; no numeric limits inferred from encoding approval |
| R1 final owner review, remaining browser families and full TC-103T01..12 | WAIT / NOT RUN except limited historical R1 evidence |
| TC-103R01..06 | NOT RUN |
| TC-103S01..04 | Proposed acceptance design; limits/encoding/error semantics PENDING; NOT RUN |
| Full ADR-090 Freeze | WAIT |
| 0103 implementation, Hosted Preview / Customer Content | NO-GO |
| Commit / Push | NOT AUTHORIZED |

No implementation or completed 0103 increment is claimed. The approved invariant closes only the
minimum-retention ambiguity; it does not close the size, final purge-policy or remaining transport
review gates.

v0.7 verification: `npm test` passed its Node/Renderer/Web stages (including 6/6 development-record
tests and 47/47 Web tests), then exited unsuccessfully before API tests because the default global
`uv` cache was not writable. No ACL change or elevated test execution was used. Re-running the
remaining `npm run test:api` and `npm run test:worker` with `UV_CACHE_DIR` set to the existing
workspace-local cache passed: API **592 passed / 246 skipped / 2 warnings**; Worker **376 passed /
67 skipped / 1 warning**. Warnings concern Starlette/httpx deprecation and non-writable pytest
node-id caches; they were not suppressed. This is a failed initial aggregate command plus passing
remaining-stage reruns, not an uninterrupted `npm test` PASS. Skipped service tests and all new
0103 transport/retention/size cases remain unexecuted. No gate is weakened or increment completed.

### v0.8 Size proposal and scoped retention disposition — 2026-10-17

**Status: PROPOSED / OWNER REVIEW REQUIRED.** The owner's "continue" authorizes further contract
design, not adoption of the numbers, HTTP refinements or retention-scope proposal below. The
approved identity-only response and minimum consumed-state retention remain unchanged. Sources:
owner's v0.6 retention review and identity-only answer; ADR-089 token construction/no-invented-limit
boundary; ADR-082 and the canonical AST schema for structural limits. No new Drive review claimed.

#### S1 — Explicit proposed budgets, not measured capacity

| Budget | Proposed inclusive maximum | Counted material | Approval |
|---|---|---|---|
| Serialized Bootstrap request body | 1 KiB = 1,024 bytes | Actual received form-body bytes before form decoding; no decompression allowance | PENDING |
| Final Preview response body | 8 MiB = 8,388,608 bytes | Complete final UTF-8 HTML including all pages, embedded media/styles and fixed script | PENDING |
| Expanded versus delivered response body | Same byte count and same 8 MiB proposed cap | Identity-only payload; HTTP/TLS headers and transfer framing excluded | Encoding approved; numeric cap PENDING |

Rationale is deliberately separated from evidence. ADR-089 specifies 32 random bytes, encoded as
43 unpadded Base64URL characters. Ordinary `token=` plus that value is 49 ASCII/UTF-8 bytes. A
read-only arithmetic check confirmed this length; it did not create or use a real token, generate
a packet, run a browser or establish maximum memory/performance. The proposed 1 KiB guard leaves
headroom for form serialization without permitting additional fields. It is a reviewable guard,
not a limit inherited from the R1 experiment or an allowance for padding/extra business input.

The 8 MiB proposal is an initial Local/Synthetic **delivery budget**, not a claim that every AST
valid under the 12-Page/30-Section limits fits. Existing Renderer fixture media is 606 bytes, but
that single asset is not representative capacity evidence. No P1 packet builder or benchmark
exists. A schema-valid source may exceed the approved delivery budget; the proposed behavior is
explicit preparation failure, never dropping pages/media, truncating content, changing the AST or
raising the cap automatically. Future three-type packet evidence is required before acceptance.
Eight MiB bounds one output body, not total process memory, concurrent viewers or intermediate
buffers. No concurrency, memory or runtime-timeout budget is silently approved here.

#### S2 — Request and failure-contract proposal

All entries in this subsection require owner approval; they do not amend the current Runtime.

- Preserve the P1 exact Host/Origin guard before capability lookup. Reject compressed request
  bodies; propose accepting only an absent `Content-Encoding` header, with no decompression step.
  Response identity-only approval alone does not authorize this new request restriction.
- Preserve exactly one scalar `token` field and the proposed form media type. Parse form encoding
  once; well-formed percent-encoded aliases may decode to the same canonical token. Do not double
  decode, trim, accept padding, coerce arrays or silently ignore duplicate/extra fields. This
  decoding choice is proposed, not inferred from the 1 KiB headroom.
- Apply the body-byte cap while reading, including when Content-Length is absent; do not rely only
  on the declared length. Proposed size denial: `413 REQUEST_TOO_LARGE`. Unsupported request
  Content-Encoding: proposed `415 UNSUPPORTED_MEDIA_TYPE`. Existing proposed structural errors
  remain `422 VALIDATION_FAILED`; malformed/unknown/expired/revoked/consumed capability remains
  safe `404 RESOURCE_NOT_FOUND` after the request guards. These are review candidates, not new
  registered error constants or an approved ordering for malformed HTTP framing.
- Enforce the response cap during Worker preparation and again on the verified private packet
  before consumption. A body read must not trust Manifest size alone or allocate an arbitrarily
  oversized object before checking its actual byte count. No DB transaction spans packet IO.
- Proposed internal permanent preparation reason: `PREVIEW_PACKET_TOO_LARGE`. It contains no
  content, token, hashes, paths or storage references. Bootstrap must not expose that internal
  distinction: an unusable packet yields the same safe `404 RESOURCE_NOT_FOUND`, without packet
  bytes or consumption. A valid capability is not consumed merely because its packet fails size
  verification. No new failure helper, Job transition or SQL is authorized by naming this reason.
- Count UTF-8 bytes after all serialization/escaping/embedding, not characters, AST JSON bytes or
  the sum of original asset lengths. Prepare and validate the whole packet before the final
  consumption transaction. No partial Preview response precedes commit; post-commit response
  interruption still burns the one use under D6. Errors remain no-store and never reflect input.

#### S3 — Additional acceptance design, not executable tests

TC-103S01..04 remain planned and unexecuted. If the owner accepts these caps, their exact boundary
inputs become 1,024/1,025 request bytes and 8,388,608/8,388,609 final-response bytes. Exactly at the
cap is size-eligible only: it does not bypass shape, provenance, authorization or CSP validation.

| Additional case | Proposed observation | Execution |
|---|---|---|
| TC-103S05 | Absent or misleading Content-Length cannot bypass bounded actual-body reading; reject any request Content-Encoding without decompressing | NOT RUN; proposal |
| TC-103S06 | Persian/other multibyte text, escaping and embedded media counted in final UTF-8 bytes; schema-valid oversized source fails with zero consumption and no truncation | NOT RUN; proposal |
| TC-103S07 | Form decoding once accepts equivalent canonical token values; malformed encoding, duplicates, extra fields and double-encoded values cannot bypass the request/capability guards | NOT RUN; proposal |
| TC-103S08 | Response identity-only remains enforced even if the client advertises compression; no intermediary transformation or size-failure detail/content leaks | NOT RUN; proposal |

#### R2 — Proposed no-purge scope for 0103, not a new duration

For owner review: keep consumed state durable in 0103 with **no per-Capability purge/TTL operation
in this increment**. Numeric `purge_after`, deletion deadlines, cleanup command/scheduler and
cleanup authority would remain a separate unapproved policy, not a runtime default. This proposal
does not call indefinite retention a Production policy, and does not authorize destroying a test
database, deleting any row or adding a nullable/defaulted `purge_after` field.

Under this proposed scope, future cleanup must still satisfy the already approved replay-safety
invariant; TC-103R03/R05 cover that condition but do not authorize a production cleanup path.
The owner must explicitly accept deferring cleanup before it can cease to be a 0103 contract
blocker. Until then the final purge-policy disposition remains PENDING.

**Review needed:** S1 numeric caps; S2 parsing/encoding/error contract; R2 no-purge scope versus a
separately defined cleanup policy. Approval of those items alone would not freeze the remaining
P1 profile/CSP/SQL, R1 policy, D clauses or wireframe. Full ADR-090 remains WAIT; 0103 Runtime/API/
Migration, Hosted/customer use and commit/push remain NO-GO / NOT AUTHORIZED.

v0.8 verification: the full `npm test` command completed with exit 0 using the existing
workspace-local `UV_CACHE_DIR`; no privilege/ACL change or test suppression. Node/Renderer/Web
stages passed; API **592 passed / 246 skipped / 2 warnings**; Worker **376 passed / 67 skipped /
1 warning**. The prior v0.7 failed initial invocation remains historical evidence, not erased by
this rerun. The same Starlette/httpx and pytest-cache warnings remain disclosed. `npm run validate`
passed **23/23**; Secret Scan passed on **1,235** publishable text files; diff whitespace checks
passed with Git line-ending warnings only. No new Size/Retention/transport case or browser matrix
was executed; service skips are not a full PostgreSQL gate. Only this ADR changed; no completed
increment, new DB field, Runtime/Migration, external document write, commit or push is claimed.

### v0.9 owner S1/S2/R2 approval and precise contract closure — 2026-10-17

**Source:** owner's explicit "ADR-090 v0.8 — S1 / S2 / R2" review in this conversation. The owner
approved these three decisions for Local/Synthetic, with the refinements below. This supersedes
the v0.8 PENDING labels for numeric caps, the stated error mapping and the no-purge scope only;
prior sections remain review history. It does not approve a complete P1 transport, Runtime/API,
Migration, commit/push, Hosted use or customer content. No independent Drive/source approval claimed.

#### Approved S1 — exact bytes and frozen delivery budget

| Contract constant / policy | Approved value | Measurement |
|---|---|---|
| `MAX_BOOTSTRAP_REQUEST_BYTES` | 1,024 bytes inclusive | Actual body bytes before form parsing/decoding; not characters or trusted Content-Length alone |
| `MAX_BOOTSTRAP_RESPONSE_BYTES` | 8,388,608 bytes inclusive | Complete final UTF-8 HTML body, including every page and embedded resource |
| Response encoding | identity-only | Count and deliver the same body bytes, without compression or body transformation |

No truncation, automatic Page/Asset removal, source mutation or silent cap increase is permitted.
The complete derivative must be prepared, validated and size-approved **before** consumption.
After measurement, no serializer, middleware, template or proxy may mutate the response body.
Headers and transport framing do not count as HTML body bytes. A response exactly at the limit is
only size-eligible, not automatically valid or authorized. These are initial contractual budgets,
not benchmark-proven capacity. Browser memory, Mobile performance and processing cost require
separate Browser Proof observations; the 8 MiB body cap is not a browser/process-memory cap.

#### Approved S2 — public mapping and consumption boundary

| Condition | HTTP | Outward code | Consumption |
|---|---|---|---|
| Actual request body exceeds 1,024 bytes | 413 | `REQUEST_TOO_LARGE` | None |
| Any request Content-Encoding header | 415 | `UNSUPPORTED_MEDIA_TYPE` | None |
| Invalid request structure | 422 | `VALIDATION_FAILED` | None |
| Packet undeliverable because it exceeds the body cap | 404 | `RESOURCE_NOT_FOUND` | None |
| Packet size failure, internal reason only | Not public | `PREVIEW_PACKET_TOO_LARGE` | None |

The packet failure response must not expose byte counts, ArtifactVersion identity, Publication
state, capability metadata, hashes or content. The same internal reason is metadata-only in any
future safe diagnostic path. Its name grants no new helper, Job transition, label or log payload.

All packet preparation failures are pre-consumption failures. In the proposed final sequence,
the existing Worker prepares the derivative; Bootstrap reads/verifies its bounded bytes and exact
identity before entering the short transaction. Under lock it revalidates authorization, expiry,
revocation, prior consumption and the pinned packet identity; consumption commits atomically at
most once. No transaction spans storage reads. After commit it may only send those already
verified bytes, without another preparation/transformation step. Failure sending those bytes is
distinct: committed consumption remains, lost/truncated response is not recoverable automatically,
and there is no second disclosure, new token or automatic Bootstrap. D6 remains unchanged.

#### Approved R2 — no consumption cleanup in 0103

Consumed state stays durable. No automatic TTL, purge, cleanup endpoint/command or implicit cleanup
through management Idempotency expiry is introduced. Deleting or expiring a 24-hour Idempotency
record must neither delete nor reset consumed state, including through any future FK/cascade.
No cleanup operation is authorized without an independent contract and explicit authority.

The approved 0103 disposition is **no consumption purge**, not a new numeric retention duration or
Production indefinite-retention policy. Future cleanup still requires `purge_after >= expires_at`
and independent rejection of expired Capabilities without resurrecting issuance/consumption.
No numeric `purge_after`, DB column, deletion deadline or cleanup mechanism is selected. That
future policy is deferred, rather than asking for another numeric retention decision for 0103.

#### P2 — Exact parsing; APPROVED FOR LOCAL/SYNTHETIC CONTRACT

The owner asked to close precise Content-Type/decoding semantics, then explicitly answered
"Approve P2" to the focused parsing question. These choices are approved by that answer, not
inferred from S2 approval alone. Technical references reviewed
2026-10-17: [WHATWG form parsing](https://url.spec.whatwg.org/#urlencoded-parsing) and
[MIME parsing](https://mimesniff.spec.whatwg.org/#parsing-a-mime-type). The Modern Web Guidance forms
review supports explicit POST and server validation, but is not product authority. Its generic
analytics, extra CSRF fields, AJAX and fallback suggestions are not adopted into this closed form.
The installed skill reported a newer version; no skill, dependency or repository package was updated.

1. Accept one syntactically valid Content-Type field with MIME essence
   `application/x-www-form-urlencoded` (ASCII case-insensitive). Accept either no parameter or
   exactly one `charset=UTF-8` parameter, with a valid quoted equivalent allowed. Reject missing,
   duplicate or malformed fields, duplicate/unknown parameters and other charsets/media types as
   `422 VALIDATION_FAILED`; never fall back to JSON, multipart or text/plain. This closed parameter
   policy is an approved application restriction, not a claim that MIME itself forbids other parameters.
2. Use form semantics on the already size-checked bytes: `&` separates pairs, the first `=`
   separates name/value, `+` represents space, and percent-decoding occurs once. Keep the pair list
   until duplicate checks; never collapse it into a first/last-value map. Empty segments follow the
   standard parser's skip behavior, not an undocumented new delimiter rule. Semicolon is not an
   alternative separator. No extra unquoting, trim, Unicode normalization or token repair follows.
3. Approved strict overlay: reject malformed raw `%xx` sequences or invalid UTF-8 in the once-decoded
   name/value bytes as `422 VALIDATION_FAILED`, rather than permissive literal/replacement-character
   recovery. Validate raw escape syntax before decoding, not by interpreting residual `%` in the
   decoded token as another escape. This is stricter than the URL Standard's error recovery, not a
   misstatement of that standard. A percent-decoded plus is not subject to another plus-to-space pass.
4. After decoding, require exactly one pair whose name is exactly `token`. Detect duplicates after
   name decoding, including `token` plus `%74oken`. No arrays, coercion, ignored fields or hidden
   `_charset_` input. A well-formed encoded alias resolving to the same canonical token has the
   same hash identity. Value validation is separate: empty, whitespace, `+`-derived space, padding,
   noncanonical Base64URL and a residual `%` are malformed capabilities and yield safe 404, not a
   second decoding pass. Values remain case-sensitive and use ADR-089's canonical 32-byte format.

No form parser, header handler or validation code is changed by P2 approval. Malformed HTTP framing
and server/proxy header-size limits are not assigned new endpoint error semantics by this contract.

#### P3 — Deterministic error precedence; APPROVED FOR LOCAL/SYNTHETIC CONTRACT

The owner explicitly answered "Approve P3" to the focused precedence question. For an otherwise
well-formed HTTP POST on the proposed fixed route, use the following ordered
short-circuit policy. The first failed stage determines the public result. No later stage executes.
That answer selects these ties; S1/S2/R2 approval alone did not select them.

| Order | Check | Contract failure outcome | Forbidden before it succeeds |
|---|---|---|---|
| 0 | Existing exact configured Host and Core Origin guard | Existing proposed bounded 403; no null/missing/foreign exception | Capability/packet lookup or consumption |
| 1 | Actual body-byte budget, bounded reading even without trustworthy Content-Length | 413 `REQUEST_TOO_LARGE` | Decoding/decompression, form parsing, capability/packet lookup |
| 2 | Content-Encoding is absent, even if present with empty/identity value | 415 `UNSUPPORTED_MEDIA_TYPE` | Decompression, form/capability/packet processing |
| 3 | P2 Content-Type, strict form decoding and exactly one token field | 422 `VALIDATION_FAILED` | Capability/packet lookup or consumption |
| 4 | Canonical token format, hash resolution, exact bound graph and preliminary validity | Uniform 404 `RESOURCE_NOT_FOUND` | Packet disclosure or consumption |
| 5 | Read bounded complete prepared packet; verify exact identity/hash/size/bytes | Uniform 404 `RESOURCE_NOT_FOUND`; oversized reason internal only | Consumption or Preview bytes |
| 6 | Under final lock, revalidate bound identities, expiry/revocation and unused state; atomically consume | Invalid/revoked/expired/consumed state remains safe 404; failed commit cannot consume or disclose | Preview bytes before successful commit |
| 7 | Send only the already validated identity-only body | Post-commit delivery interruption retains consumption; no replay | Preparation, mutation, reissue or automatic retry |

For example, oversized plus encoded is 413; encoded plus malformed form is 415;
malformed form plus a valid or invalid token is 422. Every such pre-lookup result must be identical
for valid, invalid, consumed and expired tokens embedded in otherwise identical request shapes.
No packet existence, cap or Publication-state detail reaches the public response. This does not
promise constant-time processing or eliminate all network/timing side channels. Exact remaining
DB/storage operational-error mapping still belongs to the unapproved complete P1 transport review.

#### Added acceptance design — all NOT RUN

| Case | Required future observation |
|---|---|
| TC-103P01 | P2 no-parameter/UTF-8 variants accepted; wrong/missing/duplicate MIME fields and parameters denied without capability lookup |
| TC-103P02 | Encoded duplicate token names rejected; once-decoded aliases retain one hash identity; double-encoded value is never decoded again |
| TC-103P03 | Plus/percent-space/padding/empty value share malformed-capability 404; malformed raw escapes/invalid UTF-8 follow the approved strict 422 policy; never trim, re-decode or repair |
| TC-103P04 | Multi-failure combinations follow P3 precedence identically across valid/invalid/expired/consumed token populations; zero lookup at stages 0..3 |
| TC-103P05 | Packet bytes measured/hash-verified before consumption are exactly the delivered body; no late serializer/proxy transformation; preparation failure never burns Capability |
| TC-103P06 | Failed consumption commit discloses no Preview bytes; network interruption after committed consumption cannot recover/reissue; atomic concurrent guard remains effective |

TC-103S01..08 and TC-103R01..06 remain unexecuted. Browser memory/Mobile/processing observations
remain required without inventing thresholds. The original twelve transport Browser tests are
not replaced or passed by these design rows or the historical limited R1 proof.

| Current decision / gate | Status |
|---|---|
| S1 caps, identity-only exact-body measurement/no mutation | APPROVED with owner refinements |
| S2 mapping, no information disclosure, prepare-before-consume distinction | APPROVED with owner refinements |
| R2 no consumption TTL/purge; Idempotency independent | APPROVED |
| P2 exact MIME/strict parser choices and P3 tie precedence | APPROVED by explicit subsequent owner answers; contract only |
| Complete P1 profile/CSP/SQL, remaining D clauses and wireframe | WAIT |
| R1 proof | Limited historical Chrome/Edge feasibility evidence; no new run or blanket browser acceptance |
| Twelve full Browser cases, new P/S/R cases, remaining browser families | NOT RUN |
| Full ADR-090 Freeze | WAIT |
| 0103 implementation / Runtime / Migration / Hosted / customer content | NO-GO |
| Commit / Push | NOT AUTHORIZED |

Subsequent owner approval source: the two focused questions were answered "Approve P2" and
"Approve P3" in this conversation on 2026-10-17. No numeric cap or retention decision is reopened.
These answers close parsing/precedence review only, not the complete P1 profile/CSP/SQL, the
remaining D clauses/wireframe or any Browser/DB acceptance. The next design work remains those
unfrozen contracts; no new experiment or implementation authorization is inferred.

v0.9 verification: full `npm test` completed with exit 0 using the existing workspace-local uv
cache, without privilege changes or suppression. API **592 passed / 246 skipped / 2 warnings**;
Worker **376 passed / 67 skipped / 1 warning**; preceding Node/Renderer/Web stages passed, including
47 Web tests. Existing Starlette/httpx deprecation and pytest cache-permission warnings remain.
`npm run validate` **23/23 PASS**, Secret Scan **1,235 files PASS**, and diff whitespace checks PASS
(Git line-ending warning only). No executable 0103 P/S/R case, full PostgreSQL gate or additional
browser proof ran. Only this ADR changed; no Runtime/API/Migration, package/skill update, external
document write, commit or push. These checks do not change full Freeze WAIT or implementation NO-GO.

### v0.10 P4 single-response profile and CSP proposal — 2026-10-17

**Current status (v0.14 owner decision, 2026-10-24): APPROVED / FROZEN AT CONTRACT LEVEL.**
The owner reviewed the complete v0.13 P4.R1..R4 text sent in the conversation, not the old GitHub
checkpoint. The Freeze includes P4's identities, pages[0], HTML/CSS/SVG transformations, fixed-script
behavior, CSP and acceptance conditions. Concrete executable bytes/hashes, Transformer code and
Browser evidence are still unreviewed/unexecuted. P5/full ADR/implementation remain separate.
The following v0.10 history records the original proposal and its verification. The owner explicitly requested
"push, then continue". The approved v0.9 documentation checkpoint was committed and pushed as
`413a0cc246689fd634117fcfe5979c5f9d46a8dd`; remote branch SHA matched and the worktree was clean.
That commit changed only this ADR. Later local contract text has now received the limited P4 Freeze
above; no further commit/push, Runtime, API, Migration, new Browser proof or Hosted/customer
activation is inferred. Historical proposal/review states remain history, not the current P4 state.

Sources: owner-approved T1..T7/D6/S1/S2/R2/P2/P3; ADR-088 isolation/System Font boundary; ADR-089's
verified immutable 0100 source and restricted derivative rules; read-only inspection of the fixed
0100 builder, Renderer and existing Preview validator. Technical review: [CSP Level 3](https://www.w3.org/TR/CSP3/)
and [HTML templates](https://html.spec.whatwg.org/multipage/scripting.html#the-template-element),
accessed 2026-10-17. No new Canonical Drive review or document edit is claimed.

Modern Web Guidance search found the security guide, but retrieval was not executed because
automatic approval review hit a service usage limit. No access-check bypass or retry through an
unapproved path was attempted. Primary standards and already-read accepted repository sources
support this proposal; the unavailable guide is not presented as inspected or product authority.

#### P4.1 — Separate immutable derivative, never a 0102 profile extension

Owner-approved contract identities are `preview_bootstrap_transformer_v1` and
`preview_bootstrap_delivery_policy_v1` (2026-10-18). They are not registered runtime constants or
new DB fields. Use the existing concept of exact source plus versioned transformer/policy identity
to distinguish this packet from `preview_delivery_transformer_v1`. A ready 0102 Representation is
not rewritten or re-labelled as P1. Original ArtifactVersion, canonical AST, Renderer/Core assets,
ready 0102 files and their hashes remain unchanged. Changing the new rules requires new versions.

The input remains the exact allowlisted 0100 `artifact_manifest/v1` static bundle and its canonical
Application AST. Verify bound source identity, all file paths/types/sizes/hashes, AST references
and existing runtime-security constraints before any transformation. No Provider, customer data,
Next.js runtime bundle, remote asset, arbitrary HTML or regeneration is accepted. Preparation stays
in the existing Worker artifact. This proposal creates no new service, endpoint, public parameter,
queue type or dispatch mechanism. Exact integration and private packet metadata/SQL remain review
items; this is not a hidden command/persistence contract.

#### P4.2 — Closed HTML/CSS/media transformation

Contract preparation is structured parsing and deterministic serialization, never regex rewriting
or request-time rendering. Preserve page/section identity, content, order, headings, RTL semantics
and approved component structure except for the following explicit derivative-only adaptations:

1. Embed verified CSS after only the already-reviewed import-removal and System Font substitutions
   permitted by ADR-089. No external stylesheet, `@import`, `url()` resource, `@font-face`, style
   attribute or arbitrary new CSS is accepted. Any additional fixed navigation/accessibility CSS
   must be versioned Application code using existing tokens, with exact bytes reviewed before
   implementation/acceptance. Nothing is copied into Core CSS or the Renderer package.
2. Embed media only from the exact verified source Manifest's fixed synthetic
   `generation-fixtures/media.svg`. The builder in `scripts/artifact-generation/build-static-bundle.mjs`
   writes a different SVG from `packages/generation-renderer/fixtures/.../media.svg`; the path name
   alone does not authorize substituting that Renderer fixture or a fresh hand-written image.
   Verify the actual source bytes/hash and existing SVG safety restrictions. Reject any other
   image format, general SVG ingestion, external reference, `use`/`image` URL, script, foreignObject,
   event handler, animation or data/blob URL. Preserve verified geometry/colors, not an approximation.
3. Required accessible inline SVG adaptation: preserve the original validated image's nonempty alt
   as an escaped SVG `aria-label` with `role="img"`; do not let a fixture's generic label override it.
   Empty-alt decorative media becomes `aria-hidden="true"` and non-focusable. Remove conflicting
   fixture-only accessible labels/title/description IDs in this derivative rather than emitting
   repeated IDs. Apply the independent closed SVG validation in P4.R2 before this adaptation;
   source bytes remain intact. No canonical Page/Section identity or protection state changes.
4. Put exactly one page in the active document and all other supported pages in inert templates.
   Owner-approved initial page is `canonical_ast.pages[0]`, preserving source array order, not an
   invented root-page requirement or lexicographic/latest lookup. Apply exact DOM rules in P4.R1.
   All pages are delivered upfront; this provides neither per-page secrecy nor live revocation.
5. Convert only validated intra-AST page links into `type="button"` page-switch controls with the
   same accessible labels and approved classes; remove network-navigation attributes. No `href`,
   `target`, download, ping, base, meta refresh or external destination survives in the packet.
   The target key comes from the verified canonical page mapping, never an arbitrary caller URL.
   These controls start disabled and are enabled only after fixed-script initialization succeeds.
   No-JavaScript/CSP-blocked behavior is the initial page only, with disabled navigation and no GET.
6. Preserve SimpleForm's fieldset/native controls and `type="button"` preview-only interaction.
   No form owner, action, submission handler, request, saved field values or new validation workflow
   is added. Enter/click without JavaScript must still cause no navigation or submission.

Unknown nodes/attributes, ambiguous parsing, duplicate/conflicting identities, unsupported sources
or unsafe CSS/SVG fail preparation. The transform does not sanitize arbitrary input into trusted
output. Final bytes must meet approved S1 and be immutable before approved P3 consumption.

#### P4.3 — Fixed Application script, no generated execution

Require exactly one reviewed Application-owned inline script, identical for every packet under
its script/profile version. No content, token, IDs, labels, manifest or Provider strings are
interpolated into executable source; escaped data stays in validated markup. Reject executable
nodes inside templates and all event/style attributes. The preparation guard verifies that the
only script is the expected fixed source **before** calculating its authorized hash; hashing any
input script and accepting it would not be a security boundary.

Its closed behavior is page activation only: validate target membership, move existing verified
nodes between the active slot and their templates (not parse strings), keep at most one active
main/h1, and move keyboard focus to the newly active page heading. No page clone/ID regeneration,
innerHTML/outerHTML/insertAdjacentHTML, document.write, eval/Function, dynamic import, fetch/XHR,
WebSocket, Worker/ServiceWorker, storage, postMessage, location/history mutation or background task
is permitted. It does not copy/serialize form values or send analytics. Page-local native controls
remain local; no form persistence guarantee is created by page switching. Exact script and any
support CSS bytes are NOT WRITTEN or approved by this behavior proposal; their source review and
Browser proof remain necessary before claiming acceptance.

#### P4.4 — Contract response CSP template, not an installed header

```text
default-src 'none';
base-uri 'none';
script-src 'sha256-<reviewed-fixed-script-content-hash>';
script-src-attr 'none';
style-src 'sha256-<verified-final-style-content-hash>';
style-src-attr 'none';
img-src 'none';
font-src 'none';
connect-src 'none';
media-src 'none';
manifest-src 'none';
form-action 'none';
object-src 'none';
frame-src 'none';
worker-src 'none';
frame-ancestors <exact-approved-core-origin>;
```

Hash placeholders are not usable values. Derive hashes from the exact final inline text under a
reviewed UTF-8/LF-only serialization, excluding the surrounding tags; reject unexpected raw-text
closing delimiters instead of authorizing altered script/style. Final packet byte verification and
size counting happen after serialization. No `'self'`, wildcard, scheme source, nonce, unsafe-inline,
unsafe-eval, unsafe-hashes or strict-dynamic is proposed. No runtime policy weakening or arbitrary
script hashing is allowed to make output work. System Fonts and the existing sandbox remain.

This policy is defense in depth, not a sanitizer or a universal navigation firewall. The closed
profile must prohibit all external script/resource URLs even with matching integrity metadata;
hash sources alone do not replace that check. Sandbox does not itself prohibit every same-frame
navigation, so zero follow-up requests depends on verified markup, fixed code and Browser evidence.
Inline SVG geometry and exact CSS/script compatibility must be tested under this policy; no
`img-src data:`, CORS exception or extra sandbox permission is an authorized fallback.

Require CSP as an enforcing HTTP response header, including exact frame-ancestors, not a meta tag
or Report-Only substitution. Retain no-store, no-referrer, nosniff, the existing restrictive
Permissions Policy and narrowly scoped Local/Synthetic CORP cross-origin. ACAO, Set-Cookie and
response Content-Encoding are absent; no compression/transformation, credential forwarding or
external reporting/report-sample endpoint is added. Core strict-origin/form-action remains its
separately reviewed R1/Core policy, never a global Core header change. The iframe stays exactly
allow-scripts, without same-origin/forms/popups/downloads/top-navigation or a postMessage bridge.

#### P4.R1 — Exact page DOM, references, focus and failure boundary

This is the mandatory design refinement of P4.2/P4.3, not source code or a new Renderer contract.
Let `P[i]` denote the verified page subtree for `canonical_ast.pages[i]`. The packet has one ordinary
active-page container (not an extra `main`) and one inert **ordinary HTML template** per page in
that same source order. On initial parsing, `P[0]` is already in the active container, its own
template is empty, and each other template contains its one corresponding `P[i]`. These are logical
slots, not new AST fields, endpoint parameters or a requirement to invent public DOM identifiers.
Declarative Shadow DOM, custom elements, nested browsing contexts and executable/resource-bearing
template content are not allowed. Inertness alone is not input validation.

The page subtree includes its existing Navbar/Footer landmarks and exactly one `main` with its one
accessible `h1`. Only the active subtree is connected as visible/focusable page content. Inactive
pages live in template `content`, not CSS-hidden copies in the active accessibility/focus tree.
All pages nevertheless remain present in the delivered bytes under D6; this is not per-page secrecy.

Before delivery, recursively inspect the whole prepared packet **including every template's
content**. Build one combined inventory of all page, field, heading, wrapper and control IDs:

- IDs must not collide across any possible active page, parked template or Application wrapper.
  Preserve canonical Page/Section identities and already-valid label/control identities; do not
  repair collisions by silently renaming those identities, dropping a field or merging pages.
- Every retained `label[for]`, `aria-labelledby`, `aria-describedby` and other permitted IDREF/IDREFS
  must resolve unambiguously within its own page subtree, or to an explicitly fixed Application
  control/container where that association is defined. No cross-page label, dangling reference,
  duplicate attribute or reference to untrusted markup is accepted. Native wrapping labels remain
  wrapping labels; their control and text must not be separated. Page-navigation target keys are
  the closed verified page mapping, not arbitrary DOM/CSS selectors supplied by content.
- Preserve page-array order, Section order, field/control order, visible labels and accessible
  names. A page switch changes attachment, not source order or canonical identity. No cloning,
  `innerHTML`/string re-parsing, ID regeneration or new content is part of switching.

The fixed script validates page membership, both source/destination slots and all needed references
**before** a switch. It serializes switches without re-entrant mutations. Move the old subtree to
its own empty template before attaching the target, so two `main`/`h1` page subtrees are never active
together. After a successful switch exactly one page is active and its own template is empty;
every other page is parked exactly once. Selecting the already-active page creates no duplicate.
No network, URL/history update, new parser pass or asynchronous external work occurs in this step.

After a successful switch, move focus within the iframe to the newly active page's existing `h1`.
If a programmatic focus target needs focusability, use only an Application-owned `tabindex="-1"`,
never a positive tab order, `autofocus`, `aria-hidden` on the active heading or focus on a parked
page. Preserve existing heading/landmark semantics and visible focus. Controls that carry
Application-owned `aria-current`/`aria-controls` must reflect the actual active page/valid target;
no stale reference, unjustified tab-widget role or provider-defined ARIA state is introduced.
Inactive template pages contribute no interactive tab stops.

Initial markup is independently safe: if script is absent, blocked by CSP or fails initialization,
only `P[0]` is visible and all page-switch buttons remain disabled. Initialization enables controls
only after the graph/slot checks and handlers are ready. A detected switch failure must restore
the verified `P[0]` subtree, park the others once and disable page-switch controls; it must not leave
a mixed page, dangling labels, focus in an inactive subtree or a network-navigation fallback.
Fixed-code rollback/guard behavior and injected initialization/switch failures require source
review and Browser evidence. This clause does not claim rendering after a browser process crash
or recovery of memory lost with that process. No script bytes or DOM implementation were written.

#### P4.R2 — Independent closed SVG structural and accessibility boundary

Source Manifest binding and exact source bytes/hash remain necessary, but are **not sufficient**
to authorize inline SVG. Independently parse with external entities/DTDs disabled and validate
namespace, structure, attributes, values and references before emitting a derivative. Reject
ambiguous parsing, foreign namespaces, duplicate attributes, XML declarations, DOCTYPE/processing
instructions, unrecognized nodes or unexpected text. Only the fixed root `xmlns` declaration below
is permitted. Do not load an XML resource to validate it.

The accepted source here is the exact current 0100 builder fixture, not general SVG:

| Source element / position | Closed attributes and value authority |
|---|---|
| One root SVG in the SVG namespace | `xmlns`, `viewBox`, `role`, `aria-label` exactly as present in the verified Application-owned source profile |
| Its single `rect` child | `width`, `height`, `fill` exactly as present in that same verified source profile |

This set comes from `scripts/artifact-generation/build-static-bundle.mjs` and the existing 0102
source check; it does not authorize an arbitrary shape/attribute library or alternate geometry.
There is no SVG `id`, local fragment reference or IDREF in this exact source subset. Reject such
additions (including otherwise-local references) rather than inventing a rewrite/remapping policy.
If a future profile needs internal IDs/references it requires a separately reviewed closed graph,
uniqueness and referential-integrity contract; it is not silently supported by v1.

Explicitly reject script/event attributes, `foreignObject`, `use`, `image`, links, animation,
`href`/`xlink:href`, `xml:base`, external namespace mechanisms, CSS/style/class injection, resource
URLs of any scheme and reference-valued paint/filter/clip/mask attributes. Unknown namespaced or
case/encoding-obfuscated forms are not repaired into trusted attributes. Safe geometry/colors
are retained unchanged; neither a correct hash nor a familiar file name overrides the closed
structural check. No remote fetch, CSS URL, data/blob image or font is introduced.

Only after source validation may the derivative replace the fixture's generic accessible label:
nonempty validated source-image Alt becomes escaped `aria-label` and `role="img"`; decorative
empty Alt produces `aria-hidden="true"`, without a competing `role="img"`/accessible label. SVGs
are non-focusable, with no positive tab stop. Only the Application-owned accessibility attributes
needed for those two cases may be added; no `title`/`desc`/ID reference is synthesized. Inspect every
emitted occurrence in the combined P4.R1 identity/reference inventory. No SVG-ID collision or
dangling reference may be hidden by template inertness. Any unexpected source metadata fails
preparation rather than being broadly sanitized. Original source/0102 files are never modified.

#### P4.R3 — CSP hash provenance, version review and exact embedding boundary

The two hashes have different provenance; neither authorizes arbitrary input:

- **Script:** compare the sole inline classic script against the exact, pre-reviewed fixed
  Application script version **before** accepting its hash. The expected hash is derived from
  that trusted version, not discovered by hashing whatever script arrives in a packet. Reject
  extra/modified scripts, module/import/speculation maps, external `src`, event attributes and
  content interpolated into executable bytes, including inside templates.
- **Style:** first verify exact approved CSS inputs and only the reviewed import/System Font
  substitutions plus separately reviewed fixed support CSS. After deterministic final
  serialization, hash the one authorized inline style text. No user/Provider CSS, unexpected
  attribute, `url()` spelling/escape, import, font or style tag is authorized just because a hash
  can be calculated. The closed profile check precedes hash acceptance.

Compute CSP SHA-256/Base64 over each exact final inline text encoded as UTF-8 with the reviewed LF
serialization, without its tag delimiters; the packet must contain those same texts after HTML
parsing. Reject raw-text end-tag ambiguity, BOM/line-ending/encoding surprises or any later
serializer/transport mutation. The whole-packet integrity hash and final S1 byte count are
separate checks over the final response bytes, not interchangeable with inline CSP hashes.

Any change to script, style input/output, Transformer rules or serialization must undergo review
of the affected version identity and hash binding before further preparation/delivery under that
contract. Do not silently mutate an immutable published profile, register a new version, compute
and trust a new hash at runtime, or continue an old evidence matrix under changed bytes. Full
packet byte verification must bind the authorized source/profile, not let an attacker replace
content and its claimed hash together. Concrete script/style/serialization source bytes and
version bindings still require review; no executable fixed-script implementation is supplied here.

Hash matches do not permit an external URL/resource, matching-SRI script, scheme source or
dynamic loader. P4.R2/R4 closed parsing still rejects those inputs. Retain the hash-only enforced
HTTP CSP in P4.4, with `script-src-attr 'none'`, `style-src-attr 'none'`, System Fonts/no network
sources and no reporting endpoint/sample. There is no general `'unsafe-inline'`, `'unsafe-eval'`,
`'strict-dynamic'`, nonce, CORS or Trusted Types fallback added to this contract.

`frame-ancestors` is the exact configured Core **scheme + host + port**, not `'self'`, `null`, a
wildcard, suffix match or all Core subdomains. Emit it as an enforcing HTTP response header, not
Meta or Report-Only. Observe allowed Core embedding and foreign/nested-ancestor denial in the
actual Browser with the child still opaque under `sandbox="allow-scripts"`. An allowed ancestor
must not be inferred from the child's own opaque origin or from a successful HTTP response.
CSP neither replaces sandbox restrictions nor authorizes `allow-same-origin`, `allow-forms` or a
postMessage bridge. Compatibility failures remain failures; there is no header relaxation path.

#### P4.R4 — Zero follow-up requests AND zero unintended navigation

Treat these as two independent acceptance invariants, not the single claim "no fetch API":

1. After the one successful Bootstrap response, the delivered packet initiates **zero subsequent
   network requests**, including page documents, redirects, subresources, hints, favicons, styles,
   fonts, SVG references, telemetry/reports, WebSockets, beacons, prefetch/prerender and workers.
2. The packet performs **zero unintended navigation**, even when no HTTP request would occur:
   no same-document fragment/URL/history mutation, `about:`/`data:`/`blob:` fallback, iframe/parent/
   top navigation, form default action, auxiliary context, download or external-protocol action.
   Approved page switches move verified nodes only; they are not browser navigation.

The Bootstrap request itself is excluded from the follow-up count. Independent, already-approved
Core metadata/BFCache revalidation is outside the packet's initiator scope; this does not authorize
any new Core request, polling, session or hidden rebootstrap. Browser chrome/user-directed manual
navigation or extensions are not claimed to be controlled by packet CSP. Existing T6/D6 lifecycle
limitations remain explicit; no live access or BFCache single-frame secrecy promise is added.

Before consumption, recursively reject network/navigation surfaces in all HTML/template/CSS/SVG
content: destination/resource attributes and escaped alternatives, links/forms/base/meta-refresh,
resource hints/preload/prefetch/speculation rules, external style/script/media/object/frame/worker
references and any unsupported default behavior. Convert only the already-approved intra-AST
page links to disabled-until-ready buttons as P4.2 permits; do not silently strip arbitrary unsafe
inputs into an acceptable packet. Browser auto-generated document/icon loads must also be checked;
if they occur, the zero-request gate fails rather than being ignored or accommodated by new URLs.

Future Browser evidence must inspect document/frame URL changes, navigation attempts and all
request initiators, not just XHR/fetch or a mocked network client. Exercise ordinary/middle/modifier
clicks, keyboard activation/Enter, SimpleForm controls, JS-off/CSP-blocked initialization, switch
errors and inactive pages after activation. A CSP/sandbox denial may prove defense in depth for a
negative probe, but does not make an unsafe input packet eligible or a valid packet's attempted
navigation acceptable. Do not use request interception to manufacture normal-flow zero traffic.
Keep raw content, tokens, URLs and sensitive exception context out of persisted evidence.
The original browser-family/device matrix remains required; no Browser Proof is authorized here.

#### P4.5 — Planned profile acceptance, all NOT RUN

| Case | Required future observation |
|---|---|
| TC-103D01 | Exact three-type 0100 source produces version-distinct deterministic packets; repeated preparation matches bytes/hashes; source/0102 bytes unchanged |
| TC-103D02 | Approved pages[0] first, exact P4.R1 slot cardinality/order; one active main/h1, no duplicate IDs, detached-label/IDREF or parked-page tab stops; page controls never navigate |
| TC-103D03 | Exact source bytes/hash AND independent P4.R2 namespace/node/attribute/value/reference checks; meaningful/decorative Alt preserved; arbitrary media/IDs/active or external SVG rejected |
| TC-103D04 | Sole script matches pre-reviewed source/version/hash; CSS origin/transforms verified before final hash; modified/extra scripts/styles/serialization rejected, not auto-hashed into trust |
| TC-103D05 | Observe zero normal-flow follow-up requests AND zero unintended document/fragment/history navigation across resource/default-action/hint/SVG/CSS paths; matching integrity cannot admit a URL |
| TC-103D06 | Native SimpleForm remains usable with zero submission/navigation/storage; JS-off/init rejection leaves P0 and disabled controls; detected switch fault restores P0 with correct focus/ARIA and no mixed page |
| TC-103D07 | Enforcing HTTP CSP exact Core ancestor allowed, foreign/nested ancestor denied under unchanged opaque sandbox; absent CORS/cookie/encoding; test actual browser rather than HTTP status alone |
| TC-103D08 | Approved final-body cap and exact-byte delivery hold with all pages embedded; no mutation after measurement, no partial consumption on preparation failure; report Mobile/memory limitations honestly |
| TC-103D09 | Reject duplicate IDs/dangling or cross-page label/ARIA references even inside inactive templates; repeated switches preserve canonical IDs, field associations/order and at most one active page |
| TC-103D10 | Inject startup/switch faults and repeated/re-entrant activation; only verified P0 safe fallback with disabled controls, no duplicated nodes/focus in parked page or network fallback |
| TC-103D11 | Correct-hash-but-unapproved SVG structure, XML/namespace/entity tricks, event/URL/reference attributes and extra metadata fail closed; no ID-remapping or general SVG sanitization path |
| TC-103D12 | Changed script/style/Transformer/serialization requires affected version/hash review; extra resource with matching SRI still denied; middle/modifier/keyboard/form and JS-off interactions cause neither request nor navigation |

These add detail to, not replace or pass, TC-103T01..12. The complete browser/OS matrix, BFCache,
actual-role consumption/revoke races and exact SQL/private packet schema remain unexecuted/open.
No source script, packet, schema file, endpoint, migration, new test harness or dependency was added.

**Owner Freeze decision recorded:** P4.R1..R4 and P4's strengthened acceptance conditions are
APPROVED / FROZEN AT CONTRACT LEVEL (2026-10-24). No executable source, actual hash or Browser
result is approved by that decision. P5 SQL PENDING REVIEW; full ADR Freeze WAIT; 0103 NO-GO.

v0.10 verification: full `npm test` completed with exit 0 using the existing workspace-local uv
cache; preceding Node/Renderer/Web stages passed, API **592 passed / 246 skipped / 2 warnings**,
Worker **376 passed / 67 skipped / 1 warning**. Existing deprecation/pytest-cache warnings were not
suppressed. `npm run validate` **23/23 PASS**, Secret Scan **1,235 files PASS**, and diff whitespace
checks PASS (line-ending warnings only). No new P4 script, packet, Browser/DB test or proof ran.
The single local change after the verified checkpoint push is this ADR; the new v0.10 proposal was
not committed/pushed. Service skips and P1 acceptance remain unexecuted, not a full Runtime PASS.

### v0.11 persistence compatibility review — 2026-10-17

**Status: OPTION A APPROVED FOR DESIGN / EXACT SCHEMA AND DDL REVIEW WAIT.** The owner's subsequent
"continue" authorized independent contract design, not an inferred P4 approval or 0103 implementation.
The focused persistence question was then answered "A — additive closed support". P4 remains
PROPOSED, and the full ADR remains WAIT. This section records the source-level obstacle and the
approved direction, not permission to implement a new consumption schema or helper DDL.

Sources: [active Alembic 0040](../../apps/api/migrations/versions/0040_preview_publication.py),
[0041](../../apps/api/migrations/versions/0041_preview_failure.py),
[current resolver adapter](../../apps/worker/app/infrastructure/db/preview_access.py), ADR-089,
the architecture mirror and owner's approved single-use/retention/atomicity rules. Inspection was
read-only on 2026-10-17; no live PostgreSQL, Supabase service or customer database was contacted.
The PostgreSQL best-practices skill and its privilege/RLS, short-transaction, lock-order and FK-index
references were read. They guide security review, not new product defaults, role grants, timeout
values or the broad policy examples in those references. Canonical source links/sync context above
remain unchanged; this is not a fresh Drive review.

#### Confirmed compatibility findings, not hypothetical runtime results

| Actual source boundary | Finding | Consequence for P1 |
|---|---|---|
| 0040 Representation column CHECKs | Only `preview_delivery_transformer_v1` and `preview_delivery_policy_v1` are allowed | The distinct P4 names cannot simply be inserted into the current table |
| 0040 profile uniqueness tuple | `(account_id, artifact_version_id, transformer_version, delivery_policy_version)` is already unique | Existing identity concept can distinguish derivatives, but does not override restrictive CHECKs |
| 0040 Representation protection trigger | Source/profile identity is immutable; ready rows cannot be rewritten | No relabelling or mutation of ready 0102 representations to turn them into P1 |
| 0040 claim/finalize functions | Exact v1 transformer/policy predicates are embedded | Changing CHECKs alone would not make P1 publishing work; worker authority needs separate review |
| 0040 `aria_internal.resolve_preview` | Also checks the exact v1 profile pair | Existing per-file resolver must not silently become a generic P1 capability resolver |
| Current Worker resolver adapter | Calls that fixed function and expects its closed v1 metadata projection | No existing P1 packet or one-shot consumption authority is supplied by this adapter |
| 0041 `fail_preview` | Also checks the v1 profile pair and only three existing bounded error codes | Neither P1 failure finalization nor `PREVIEW_PACKET_TOO_LARGE` is implicitly supported; review the P1-specific failure boundary without widening v1 error semantics |

The resolver finding is a deliberate safety boundary: accepting P1 at an old per-file resolver could
mix access models. Keep existing 0102 capability resolution pinned to its reviewed profile rather
than widening it merely to make a new packet accessible. Legacy `/p/` transport remains forbidden
in 0103. Narrow function owners, RLS and tenant/project/version checks remain required; existing
shared-Worker risk is not redesigned or declared solved.

#### Persistence direction selected explicitly by the owner

| Option | Design direction only | Required later review |
|---|---|---|
| A — additive closed-profile support; APPROVED FOR DESIGN | Keep existing Representation/Publication concepts; a future reviewed migration permits only the exact accepted 0102 pair and separately approved P1 pair, never mixed/arbitrary versions. New P1 rows are distinct; old rows/files remain immutable | Exact pair CHECK, profile-aware publishing authority, dedicated P1 resolve/consume boundary and its consumed-state schema; preserve v1 resolver and all 0102 regression behavior |
| B — separate P1 metadata model; NOT SELECTED | Would keep current profile CHECKs and publishing functions unchanged but introduce separate P1 packet/publication/capability associations | Not pursued; selecting A does not authorize duplicating those aggregates under B |

Option A is now the selected design direction, not permission to change an old migration.
Any later approved additive implementation must use a new reviewed migration, not edit applied 0040/0041
history. Option B is not selected merely to avoid reading existing predicates. This decision does not
authorize arbitrary profile strings, a generic SQL helper, broad table writes, RLS bypass or a
new deployable service. Exact schema/function names, signatures and DDL remain unselected.

Under Option A, consumption must remain a durable, at-most-once effect independent of
management Idempotency TTL and transient Job/Outbox execution claims. It is not a cache or a lease.
Prepared packet IO stays outside the short final transaction; exact bound state is revalidated
under lock, and no Preview bytes precede the successful commit. No cleanup or reactivation path
is introduced. The helper owner must have only reviewed privileges, safe fixed search_path and
qualified objects, no dynamic SQL and no PUBLIC execution. No generic skill example that grants
CASCADE, broad table access or a new timeout is inherited into this contract.

#### Planned compatibility acceptance — all NOT RUN

| Case | Required observation after a separately approved design/implementation |
|---|---|
| TC-103M01 | Accepted v1 and exact P1 profiles remain distinct; mixed/arbitrary profile versions rejected at DB boundary |
| TC-103M02 | Historical ready source/0102 rows, hashes, files, commands and per-file capability behavior remain unchanged |
| TC-103M03 | V1 resolver cannot authorize P1 content, and P1 resolve/consume cannot authorize legacy per-file content or bypass profile identity |
| TC-103M04 | Cross-tenant/project/version and wrong packet identity rejected by actual limited runtime authority; no direct new table writes or PUBLIC/anon authority |
| TC-103M05 | Concurrent one-shot consumption, revoke ordering and commit failure preserve approved invariants; Idempotency/claim expiry cannot erase consumption |
| TC-103M06 | Existing v1 failure reasons/ownership remain unchanged; a separately approved P1 failure path handles packet-size failure only for the exact P1 profile without accepting arbitrary reasons |

These are future contract checks, not executed SQL tests. A complete migration-source security
review and actual-role gate remain required after this design selection. **Current boundary:**
P4 approval WAIT; persistence A direction APPROVED FOR DESIGN ONLY; exact schema/helper authority
and SQL source review WAIT; Runtime/API/Migration and Hosted/customer activation NO-GO; commit/push
not authorized for this local continuation. No schema file, DDL, new helper or runtime test was written.

#### P5 candidate under Option A — consumption ledger and authority, NOT FROZEN

Propose a minimal append-only consumption ledger, not a second Publication/Capability aggregate:

| Logical field | Proposed meaning / invariant |
|---|---|
| `publication_id` | Primary/unique identity: at most one successful consumption for the Publication's one immutable issued Capability |
| `account_id`, `project_id` | Required tenant/project consistency, with a composite FK to the same Publication and RESTRICT; never caller authority |
| `consumed_at` | Required server timestamp of the atomically committed first consumption, not receipt or rendering time |

This is a logical proposal, not accepted DB columns or a table name/schema. The immutable Publication
binding already identifies Representation/ArtifactVersion and explicit expiry; do not duplicate or
invent a mutable second binding. No raw token, duplicate token hash, content, packet bytes, guest
identity, retry counter, TTL or numeric `purge_after` is proposed. R2 prohibits cleanup, including
through Idempotency/claim deletion. Exact FKs, indexes, RLS, immutable protection and owner privileges
must be reviewed before choosing executable DDL.

Propose two fixed P1-only helper operations, with exact names/signatures/roles still awaiting SQL
review: a read-only preflight returning the closed private binding/packet reference, and an atomic
consume operation comparing that expected binding and Manifest hash to the same hash-resolved
Capability. Preflight is not a reservation or lasting authorization. Both reject wrong profile or
tenant/project/version associations; neither accepts an arbitrary relation, predicate, SQL fragment,
caller-supplied tenant context change or generic profile string.

Prepared bytes are read/verified before the short transaction. Consume locks the same Publication
row used by revoke, rechecks current server-time expiry after any lock wait, exact immutable binding
and unused state, then inserts the one consumption effect with a DB final uniqueness guard.
No check-then-insert-only protection or transaction across file IO is acceptable. Any positive
helper result is provisional until the calling transaction's commit succeeds; only then may those
already verified bytes be sent. Failed/ambiguous commit acknowledgment discloses no Preview bytes
and creates no automatic retry/reissue; durable consumed state, if committed, still blocks replay.

The helper-owner choice, fixed search_path, qualified objects, narrowly scoped grants and RLS must
be source-reviewed. Owner must not silently gain table ownership/RLS bypass, and Worker/public/anon
must receive no direct new-table write authority. The existing Worker raw SELECT/RLS behavior and
shared-credential residual risk remain outside this limited design; no complete Production tenant
isolation claim is made. This candidate does not approve new roles, EXECUTE grants, functions,
failure allowlists or changes to any existing helper. P4 remains separately unapproved.

v0.11 verification: full `npm test` exit 0 with the existing workspace-local uv cache; prior
Node/Renderer/Web stages passed, API **592 passed / 246 skipped / 2 warnings**, Worker **376 passed /
67 skipped / 1 warning**. Existing deprecation/pytest-cache warnings were not suppressed. Validate
**23/23 PASS**, Secret Scan **1,235 files PASS**, and diff whitespace checks PASS (Git line-ending
warning only). No new SQL, schema, Migration, helper, runtime test, PostgreSQL instance or Browser
proof was created/executed. The only changed file is this ADR; local v0.10/v0.11 design remains
uncommitted/unpushed. New compatibility/consumption tests are NOT RUN; no complete Runtime PASS.

### v0.12 owner P5 approval and SQL review source — 2026-10-17

The owner explicitly approved P5's append-only logical model, its four fields, no token/content,
no TTL/purge, limited Preflight/Consume, Publication locking/uniqueness and response only after
successful commit. SQL **design** is authorized; exact SQL contract/source review remains PENDING.
The subsequent authentication question was answered "valid Capability plus database binding": no
new JWT/Tenant header or Core assertion is introduced. Tenant/project derive from the unique stored
capability hash and full bound graph, never caller-selected tenant input. P4 is still WAIT.

The [separate P5 SQL contract](ADR-090-p5-sql-contract.md) supplies proposed DDL, immutable ledger
protection, composite RESTRICT FK/PK, RLS, fixed function bodies/signatures, effective-grant review,
transaction flow and twelve unexecuted race/privilege/crash scenarios. It is Markdown review text,
not an executable migration or source imported by runtime. Proposed names and reuse of the existing
restricted helper owner require source review; none is falsely marked approved by logical-model
approval. Current v1 publishing/resolution helpers and applied migration history are unchanged.

SQL inspection confirmed ready ArtifactVersion/Representation immutability and the existing revoke
Job -> Publication order. Proposed Consume locks Publication only and never later requests Job or
Representation locks; packet IO and validation are outside the short final transaction. A positive
helper return remains provisional until commit is confirmed. Unknown commit acknowledgment means
no Preview bytes and no automatic replay/reissue; existing durable consumption, if any, persists.

The exact P4 version names/private packet schema and additive publishing/failure SQL remain open
dependencies; approving this P5 source alone cannot make P1 publishable or authorize execution.
No live PostgreSQL/Supabase service, SQL parser/compiler, migration runner or new runtime test was
used. No application schema file, endpoint, Helper object, role/grant or database state changed.
**P5 Logical Model APPROVED; P5 SQL Contract PENDING REVIEW; P4/full ADR Freeze WAIT; 0103
implementation, SQL execution/Migration, Hosted/customer activation and commit/push NO-GO.**

v0.12 verification: full existing `npm test` exited 0; Node/Renderer/Web stages passed (Web
47/47), API **592 passed / 246 skipped / 2 warnings**, Worker **376 passed / 67 skipped /
1 warning**. Existing Starlette/httpx deprecation and pytest-cache permission warnings remain
visible. Documentation validation **23/23 PASS**, Secret Scan **1,236 publishable text files PASS**,
and whitespace checks PASS (Git line-ending warning only). These are regression/document checks,
not execution evidence for the proposed SQL: all twelve new P5 SQL scenarios are **NOT RUN**;
the source is **NOT COMPILED / NOT EXECUTED**. Only this ADR and its new SQL-review Markdown
changed; no completed development increment, PostgreSQL gate or full 0103 acceptance is claimed.

### v0.13 owner P4 review and required contract refinements — 2026-10-18

Authority: the owner read P4 v0.10 directly at checkpoint `d794ffa`, accepted the design in
principle, approved its two derivative identities and `canonical_ast.pages[0]`, and required four
specific refinements **before** another Freeze review. Authorization is documentation revision
only; it does not include Browser Proof, Runtime, SQL/Migration, commit/push or Hosted activation.
REQ-10320 maps these changes to P4.R1..R4 and planned TC-103D02..12. Older v0.10/v0.11 proposal
status is historical where this owner decision now supersedes identities/initial-page uncertainty.

P4 now defines the active slot/one-template-per-page model, combined ID/reference inventory,
move-without-clone ordering, focus/ARIA and initial-page failure fallback; an independent exact
SVG structural/attribute/reference boundary with meaningful/decorative Alt; trusted script-source
versus validated-style hash provenance and version review; and two distinct zero-follow-up-request
and zero-unintended-navigation invariants. New acceptance cases remain NOT RUN. No script, CSS,
DOM implementation, executable test, source SVG or packet was generated or modified.

Read-only source checks: the actual 0100 builder and 0102 transformer both accept the fixed SVG
root/rect source; Renderer field labels use Section-bound stable IDs. These facts ground the
refinements; they do not prove the proposed P4 transformer or rollback implementation works.
No fresh Canonical Drive review or write is claimed for this owner-directed contract revision.

Technical references checked 2026-10-18: [HTML template content/inertness](https://html.spec.whatwg.org/multipage/scripting.html#the-template-element),
[CSP3](https://www.w3.org/TR/CSP3/) (hash sources and frame-ancestors) and
[SVG2 structure](https://www.w3.org/TR/SVG2/struct.html). Modern Web Guidance `security` was searched
and fully retrieved for this turn. It reinforced unsafe-DOM-sink avoidance and independent
header/isolation verification; generic reporting/nonces/strict-dynamic/CORS/Trusted Types changes
were not adopted over the owner's narrower no-network/hash-only contract. The tool warned of a
newer skill revision; no repository dependency or installed skill was updated.

**Status:** P4 derivative identities/initial page APPROVED; SVG/navigation/CSP accepted in principle
with required refinements now documented; P4 Freeze WAIT. P5 logical model/authentication APPROVED,
exact SQL review PENDING and unaffected. Full ADR-090 Freeze WAIT; 0103 implementation,
SQL execution/Migration, Browser Proof, Hosted/customer use and commit/push remain NO-GO.

v0.13 documentation/regression verification: `npm test` exit 0; preceding Node/Renderer/Web stages
passed (Web 47/47), API **592 passed / 246 skipped / 2 warnings in 32.14s**, Worker **376 passed /
67 skipped / 1 warning in 21.44s**. Existing deprecation/pytest-cache warnings were not suppressed.
Service-test environment variables were absent before running; no PostgreSQL/Redis integration
gate or Browser launch was enabled. `npm run validate` **23/23 PASS**, Secret Scan **1,237 files
PASS**, and diff whitespace checks PASS (line-ending warnings only). Text-only comparison against
HEAD confirms every fenced P5 SQL block is unchanged; only its dependency-status prose reflects
the newly approved P4 names. The pre-existing local MVP assessment report was preserved unchanged.
No executable P4 test/proof, SQL compilation/execution, Runtime/API/Migration change, commit/push
or external system write occurred. TC-103D01..12 and the full P1 matrix remain **NOT RUN**;
regression PASS is not P4 Freeze, Browser acceptance or full 0103 completion.

### v0.14 final P4 contract Freeze and independent P5 source review — 2026-10-24

The owner explicitly approved the complete P4 contract after reviewing the full v0.13 P4.R1..R4
text supplied in the conversation. The decision is **not** based on the older GitHub revision.
Record P4 as **APPROVED / FROZEN AT CONTRACT LEVEL**, including both derivative identities,
`canonical_ast.pages[0]`, the HTML/CSS/SVG conversion boundary, fixed page-switch script behavior,
hash CSP and P4 acceptance conditions. The normative P4.R1..R4 text is unchanged by this status
update. Actual script/CSS/serialization bytes, real hashes, Transformer implementation and Browser
proof still require their independent executable gates; none has been authorized or run here.

The owner separately authorized continued **source review** of P5, not SQL approval or execution.
[P5 section 10](ADR-090-p5-sql-contract.md) records the static comparison against 0038/0040/0041,
the current revoke repository and PostgreSQL documentation. It distinguishes reasoned expectations
from runtime evidence and identifies installation-authority/ACL ordering questions. No fenced SQL
statement, active migration, runtime role/grant/RLS, endpoint or executable test changes as part
of the review. The PostgreSQL skill informs minimum privilege and short-transaction/lock review;
it does not authorize a new role, tenant-RLS redesign or a numeric timeout/retry policy.

| Gate | Current decision |
|---|---|
| P4 contract | APPROVED / FROZEN AT CONTRACT LEVEL |
| P4 executable bytes/hashes/Transformer/Browser proof | NOT APPROVED / NOT RUN |
| P5 logical model and Capability + stored-binding boundary | APPROVED |
| P5 exact SQL contract | PENDING OWNER SOURCE REVIEW |
| Full ADR-090 Freeze | WAIT |
| 0103 implementation / SQL execution / Migration | NO-GO |
| Hosted Preview / customer content | NO-GO |
| Commit / Push | NOT AUTHORIZED |

This decision record supersedes historical P4 WAIT/proposal labels only for P4's contract. It does
not waive the remaining D clauses, wireframe, P5 integration/private Manifest, complete browser
matrix or shared-Worker security limitations. No new Canonical Drive review/write is claimed.
Existing uncommitted reports and earlier local edits are preserved.

v0.14 verification: `npm test` exit 0; existing Node/Renderer/Web stages passed (Web 47/47),
API **592 passed / 246 skipped / 2 warnings in 33.42s**, Worker **376 passed / 67 skipped /
1 warning in 24.38s**. Existing deprecation/cache-permission warnings remain visible. Service-test
environment was absent before execution; no PostgreSQL/Redis integration or Browser Proof ran.
`npm run validate` **23/23 PASS**, Secret Scan **1,237 files PASS**, and diff whitespace checks
PASS (line-ending warnings only). Text-only comparison confirms all fenced P5 SQL blocks remain
identical to HEAD. No new SQL compilation/execution, Runtime/Migration change, commit/push or
external document/system write occurred. New P4/P5 acceptance cases remain NOT RUN; these checks
do not change any gate other than recording the owner's explicit P4 contract decision.

### v0.15 independent Installer and pre-commit ACL design — 2026-10-24

Owner decision: **P5 INSTALLATION AUTHORITY APPROVED FOR SQL CONTRACT DESIGN ONLY**. Record the
Installer as an independently controlled temporary PostgreSQL Superuser installation session in
the disposable Local/Synthetic database, not an arbitrary Admin or Worker. No Installer identity,
credential, role membership or schema CREATE is created/granted to runtime principals. Helper
owner stays restricted NOLOGIN/NOBYPASSRLS, without schema CREATE; Worker gains only exact
approved runtime EXECUTEs, no installation, ownership or direct ledger privilege.

[P5-SQL r2](ADR-090-p5-sql-contract.md), especially sections 3, 6/6.1 and 11, proposes one future
installation transaction: Installer guard -> create/alter scoped objects -> assign restricted
final SECURITY DEFINER ownership -> revoke PUBLIC -> explicit grants -> inspect raw/effective
ACLs, ownership, memberships/SET ROLE, schema privileges and RLS metadata -> assert -> COMMIT only
if all pass. Failure requires rollback without broad role/default-policy repair. Superuser may
remain ledger/invoker-trigger owner but not final owner of the two runtime definer functions.
Post-commit actual-role tests remain separate and cannot use Installer as an RLS proof identity.

This updates SQL review text only. Exact SQL r2, helper-owner reuse and executable catalog/role
behavior still require source review and separate execution authority. Existing three helper/
trigger function definitions and frozen P4.R1..R4 normative clauses are not changed. TC-103SQL13..16
extend the planned negative installation/ACL/rollback evidence; all new P5 cases remain NOT RUN.
No SQL file/migration, runtime/API, database connection, Browser Proof or executable test is added.
No new Canonical Drive read/write, commit or push is claimed or authorized. Prior source-review
statements about unchanged SQL blocks describe their historical v0.14 checkpoint, not r2.

| Gate | Current decision |
|---|---|
| P4 contract | APPROVED / FROZEN AT CONTRACT LEVEL |
| P5 logical model / Installer / pre-commit authority design | APPROVED |
| P5 exact SQL r2 / operational-role verification | PENDING SOURCE REVIEW / NOT RUN |
| Full ADR-090 Freeze | WAIT |
| SQL execution / Migration / 0103 implementation / Browser Proof | NO-GO |
| Hosted Preview / customer content / Commit / Push | NOT AUTHORIZED |

v0.15 documentation/regression verification: `npm test` exit 0; existing Node/Renderer/Web stages
passed (Web 47/47), API **592 passed / 246 skipped / 2 warnings in 33.81s**, Worker **376 passed /
67 skipped / 1 warning in 21.88s**. Existing warnings were not suppressed. `npm run validate`
**23/23 PASS**, Secret Scan **1,237 files PASS**, diff whitespace checks PASS (line-ending warnings
only). Text-only comparison confirms the three fixed function definitions remain identical to
HEAD; proposed installer/ACL review blocks changed deliberately. Service-test environment was
absent; no database/Redis integration, SQL compilation/execution, Browser Proof, runtime/migration
change, commit/push or external-system write occurred. TC-103SQL01..16 remain NOT RUN. Only the two
tracked ADR Markdown files changed; existing uncommitted MVP assessment was preserved. Regression
checks do not freeze exact SQL or authorize 0103 implementation.
