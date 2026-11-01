# ADR-090 R1 — Disposable HTTPS Browser Proof

**Date:** 2026-10-17

**Result:** PASS for the limited native POST / Origin feasibility proof in desktop Chrome and Edge
(headless). **Owner Freeze review: WAIT. 0103 implementation: NO-GO.**

This is evidence for [ADR-090](ADR-090-controlled-preview-workspace-contract.md), not a completed
0103 development increment, Production security approval or the full P1 Browser Acceptance Matrix.

## Authority and scope

The owner's explicit R1 approval in this conversation authorizes a disposable Local/Synthetic
proof: strict-origin only on the submitting Core proof document, unchanged iframe referrer policy
and sandbox, valid HTTPS, rejection of missing/null/foreign Origin, no real capability/customer
artifact, no product DB/session/cookie and no Runtime/Migration/commit/push/Hosted activation.

Sources: owner R1 decision; ADR-090 T1..T7 and approved D6. No Canonical Drive write or claim of new
Drive approval was made. Platform references used for test setup, not product authority:

- [Fetch Origin-header algorithm](https://fetch.spec.whatwg.org/#append-a-request-origin-header)
- [Referrer Policy: strict-origin](https://w3c.github.io/webappsec-referrer-policy/#referrer-policy-strict-origin)
- [HTML native form submission](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#form-submission-algorithm)
- Chromium's [profile-keyed certificate service](https://chromium.googlesource.com/chromium/src/+/main/chrome/browser/net/server_certificate_database_service_factory.cc)
  and [certificate trust metadata](https://raw.githubusercontent.com/chromium/chromium/main/components/server_certificate_database/server_certificate_database.proto)

## Environment and valid HTTPS

| Item | Executed configuration |
|---|---|
| OS | Windows desktop, user-owned disposable profiles only |
| Chrome | Chrome/155.0.8059.40, headless |
| Edge | Edg/155.0.4283.45, headless |
| Node | v24.11.1, existing installation |
| TLS | TLSv1.3 observed by the HTTPS endpoint |
| Core | `https://core.r1-core.test:10117` |
| Preview | `https://preview.r1-preview.test:10117` |
| Foreign sender | `https://foreign.r1-foreign.test:10117` |
| Negative certificate host | `https://wrong.r1-wrong.test:10117` |

The sites use distinct registrable test domains, not only different localhost ports. All resolve to
127.0.0.1 using disposable browser-process host resolver rules. No hosts file or DNS was changed.
The HTTPS server bound only to 127.0.0.1 and used the same HTTPS scheme throughout, without redirect
or downgrade.

No usable server certificate/private key existed in CurrentUser/My or LocalMachine/My; mkcert was
absent. An ephemeral self-signed **leaf**, CA=false with exact SANs for the three approved test
hosts, was generated for the proof. Only that leaf was trusted in each disposable browser profile's
own certificate configuration. This is local test trust, **not a publicly trusted CA certificate**.
The browser's private certificate configuration is SQLite-backed; no application database, SQL
server, schema migration, product repository or tenant data was accessed.

Neither Windows CurrentUser nor LocalMachine Trust was modified. Normal browser TLS validation
remained enabled: no ignore-certificate-errors, SPKI exception, accept-insecure-certs, no-sandbox,
disabled web security or CDP certificate-error override. The Core response had browser-observed
securityState=secure. A navigation to the host absent from SANs failed with
`net::ERR_CERT_COMMON_NAME_INVALID`, and did not reach the HTTP handler. The direct negative HTTPS
client also used ordinary certificate/name validation with this explicit local trust leaf.

## Method and controls

1. A small standalone HTTPS server and fresh profiles were created under an exact owned `.tmp/r1-proof-*`
   directory. No app/renderer/storage/database code was imported. Browser network requests were not
   intercepted or given injected headers. CDP was used only to drive/observe the disposable browser.
2. The Core proof document contained a native POST form targeting an already existing named iframe:
   `sandbox="allow-scripts" referrerpolicy="no-referrer"`. The form lived outside the sandbox.
   A browser input click submitted it; the server, not a mocked fetch, received the request.
3. A random canary, not a real capability, was kept in process/browser volatile memory and placed
   transiently in the hidden input's value property. Its raw value was never printed, put in a URL,
   frame name, saved report or request-body diagnostic. Form controls were cleared/removed after
   the request. No token was echoed in the returned document.
4. The baseline used Core no-referrer; R1 changed **only that Core document** to strict-origin.
   Core CSP narrowly allowed form-action/frame-src to the exact Preview origin. There was no Core
   global policy change. Preview policies and sandbox were not relaxed between cases.
5. The dummy endpoint required both exact Core Origin and the correct canary. Valid Origin with an
   incorrect canary was denied, so Origin alone was not treated as authorization. This is not a
   proof of actual Capability/Publication validation or tenant authorization.
6. The expected synthetic heading inside the iframe was read independently through the automation
   target. iframe.load was not used as render-success evidence. The child had opaque self.origin,
   parent DOM access was denied, and child resource performance entries numbered zero.

The HTTPS server captured only allowlisted request headers, HTTP result, TLS protocol and bounded
booleans. It did not capture raw bodies/canaries, cookies, credentials or arbitrary exception text.
No HAR, browser trace, screenshot, NetLog or raw generated artifact was retained.

## Actual request headers and HTTP results

The following values were observed independently in **both** listed browser versions. All browser
requests were native POST navigations to `https://preview.r1-preview.test:10117/bootstrap`.

| Case | Actual Origin | Actual Referer | HTTP | Result |
|---|---|---|---|---|
| Core no-referrer baseline, correct canary | literal `null` | absent | 403 | Correctly denied |
| Core strict-origin, correct canary | `https://core.r1-core.test:10117` | `https://core.r1-core.test:10117/` | 200 | Correct heading rendered inside unchanged sandbox |
| Core strict-origin, incorrect canary | `https://core.r1-core.test:10117` | `https://core.r1-core.test:10117/` | 404 | Correctly denied; Origin alone insufficient |
| Foreign strict-origin, correct canary | `https://foreign.r1-foreign.test:10117` | `https://foreign.r1-foreign.test:10117/` | 403 | Correctly denied |
| Direct HTTPS client, Origin omitted | absent | absent | 403 | Endpoint-negative check only; not claimed as a native browser-generated missing-Origin request |

Other actual native browser request headers:

```text
Host: preview.r1-preview.test:10117
Content-Type: application/x-www-form-urlencoded
Sec-Fetch-Site: cross-site
Sec-Fetch-Mode: navigate
Sec-Fetch-Dest: iframe
Cookie: ABSENT
Authorization: ABSENT
```

The direct missing-Origin client did not send Sec-Fetch headers. No browser header was modified to
simulate its absence. Referer in the successful browser cases contained neither Core path nor query.
The request target contained no token, query or fragment. Headers establish what these executions
did, not a guarantee about other browser versions or environments.

## Response and iframe policy

The endpoint emitted these response headers, unchanged across baseline/R1/denial responses:

```text
Content-Type: text/html; charset=utf-8
Cache-Control: no-store
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Cross-Origin-Resource-Policy: cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Access-Control-Allow-Origin: ABSENT
Set-Cookie: ABSENT
```

```text
Content-Security-Policy:
  default-src 'none'; base-uri 'none'; script-src 'none'; style-src 'none';
  img-src 'none'; font-src 'none'; connect-src 'none'; form-action 'none';
  object-src 'none'; frame-src 'none'; worker-src 'none';
  frame-ancestors https://core.r1-core.test:10117
```

The tiny synthetic response had no scripts/styles/media or external dependencies, so script/style
none is appropriate and does not test or approve P1's proposed hash-authorized navigation script,
inline CSS or SVG derivative. Core form permission was not added to the iframe: allow-forms and
allow-same-origin were absent. iframe referrerpolicy remained no-referrer and **did not suppress
the Core Origin on the tested form-parent navigation**. The heading was present, the child origin
was opaque, parent DOM access failed, and the child's observed resource-entry count was zero in
each browser. This is not a complete generated-runtime egress/security audit.

## Test summary and boundaries

| ID | Assertion | Chrome | Edge |
|---|---|---|---|
| R1-01 | Valid HTTPS without downgrade or certificate bypass | PASS | PASS |
| R1-02 | no-referrer baseline produces null Origin and is rejected | PASS | PASS |
| R1-03 | strict-origin preserves exact Core Origin; Referer origin only | PASS | PASS |
| R1-04 | Native form reaches existing allow-scripts-only iframe and renders expected content | PASS | PASS |
| R1-05 | Foreign/null/missing Origin denied | PASS | PASS |
| R1-06 | Valid Origin with invalid dummy canary denied | PASS | PASS |
| R1-07 | Opaque child, parent DOM denied, no child subresource entries | PASS | PASS |
| R1-08 | Wrong TLS hostname rejected by normal browser verifier | PASS | PASS |

Firefox desktop, Safari desktop, Chrome Android and Safari iOS: **NOT RUN**. No mobile viewport or
WebKit emulation was used as a substitute. Headless Windows results are not headed/mobile results.

0103's twelve full acceptance cases remain **NOT EXECUTED end-to-end**. R1-03/04/05 provide limited
supporting evidence for portions of TC-103T01/06, not PASS for those complete cases. No DB-level
consumption atomicity, concurrency/revoke ordering, Publication validation, real tenant isolation,
BFCache/stale-paint control, all-pages delivery, retention, size caps or product UI was tested here.
The server's experimental request-size guard and local harness timeouts are not product decisions.

## Preliminary failures and corrections

- Restricted execution initially timed out during CDP renderer enable; no native POST or header
  evidence was produced. Running only the owned proof outside the outer process sandbox allowed
  renderer control. The browser sandbox remained enabled; no product policy was relaxed.
- The first profile-trust seed used a directory layout inconsistent with the installed version.
  Normal TLS correctly rejected it with ERR_CERT_AUTHORITY_INVALID; it was not bypassed. A fresh
  browser-created profile showed the correct certificate-config file location; the final proof
  seeded the exact leaf there. No global trust was added.
- A temporary harness startup variable-shadowing error was corrected before the successful run.
  These unsuccessful preparations are not transport PASS evidence. No Origin/Sandbox acceptance
  condition was loosened to obtain the final results.

Final temporary harness identities (SHA-256; source is intentionally disposable):

| File | SHA-256 |
|---|---|
| proof.mjs | `CFF0981E63C9A17F74E03E5D5FA4F23ED527A3BC6CCBFCA7DFFAFB7DD882608B` |
| prepare_tls.py | `29CA4C502F83FDB1045F00767FC76FAF22A61C5A191197B822DF5888E5231961` |
| seed_profile.py | `1535B9FA5EBDF8141C32A779D2F1C6EB877C60E89729C1BEE3A0A3D87E19F5AD` |

## Cleanup and repository verification

Proof servers and owned browsers were closed. A connection check to final proof port 10117 returned
ECONNREFUSED. No user browser/profile/service was stopped. The exact owned temporary directory was
resolved/validated within the worktree `.tmp` boundary and removed, including all disposable
profiles, TLS certificate/private key, proof sources and regression temporary files. Its absence
was verified. Initial removal of sandbox-owned pytest files from the full-user context was denied;
cleanup succeeded under the owning sandbox context, without changing ACLs or user data.

The pre-cleanup secret scan correctly flagged the generated temporary TLS private-key file.
Nothing was allowlisted or ignored to bypass the gate. After deletion, the final secret scan
**PASS** inspected **1,235 publishable text files**. No private-key bytes or raw canary appeared in
the report/diagnostics, and no TLS or profile material remains in the worktree.

| Check | Actual result |
|---|---|
| Disposable files/profiles/key cleanup | PASS; exact proof directory absent |
| Owned HTTPS service cleanup | PASS; final port refused connection |
| Windows My stores / generated leaf in Root stores | My store counts remained zero; generated leaf absent from CurrentUser/LocalMachine Root stores |
| Full existing `npm test` | PASS, exit 0; Node/Renderer/Web passed |
| API regression | 592 passed / 246 skipped / 2 warnings |
| Worker regression | 376 passed / 67 skipped / 1 warning |
| `npm run validate` | 23/23 PASS |
| Final `npm run scan:secrets` | PASS, 1,235 publishable text files |
| Tracked/new-document diff and whitespace checks | PASS; Git line-ending warnings only |

Regression used an owned temporary directory and workspace UV cache. Database/Redis URL variables,
paid-evaluation confirmation and real Provider keys were removed from the regression child process.
Skipped service integrations did not execute. The API Starlette/httpx deprecation and API/Worker
pytest cache-write warnings remain reported, not suppressed. These regressions do not constitute
execution of the twelve full 0103 acceptance cases.

**Cleanup: PASS. Existing repository regression: PASS with the skips/warnings above.** Only the
ADR proposal, this safe report and the existing ADR index edit remain dirty; no Runtime source change.

**Decision handoff:** limited R1 proof evidence is ready for owner review; R1 is not self-Frozen.
ADR-090 remains WAIT, 0103 implementation and Hosted/Customer Content remain NO-GO. No commit/push,
Migration, primary API change, product database or Canonical Drive mutation was performed.
