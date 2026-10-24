# Development Record: 0101 Preview Isolation Architecture

- Increment ID: `0101-preview-isolation-architecture`
- Date: 2026-10-12
- Related domain: Preview / Runtime Security
- [Test report](./test-report.md)

## Scope

Define and prove the Local/Synthetic isolation boundary for rendering one exact immutable
ArtifactVersion in a cross-site opaque-origin iframe. Hosted Preview, customer content, private
assets and Production access capabilities remain prohibited.

## Source Documents

- Engineering Backlog, `DEVOPS-F3-01` and `SEC-F3-04` — [Canonical Drive](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit), synchronized 2026-10-12.
- Engineering Master Plan, Sprint 3 §14.4 and `TB-08` — [Canonical Drive](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit), synchronized 2026-10-12.
- Owner-approved 0101 CORP and System Font Only decisions, 2026-10-12.
- [ADR-088](../../adr/ADR-088-preview-isolation-architecture.md).
- W3C CSS Fonts font-fetching requirements, checked 2026-10-12.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-10101 | 0101; `TB-08` | Separate registrable Core/Preview test sites and exact ArtifactVersion namespace | TC-10101 |
| REQ-10102 | 0101; `SEC-F3-04` | Exact opaque-origin `sandbox="allow-scripts"`; no messaging bridge | TC-10102 |
| REQ-10103 | 0101 | Build-byte hash CSP, HTTP `frame-ancestors` and restrictive response headers | TC-10103 |
| REQ-10104 | 0101 CORP decision | Manifest-bound `CORP: cross-origin` with CORS absent | TC-10104 |
| REQ-10105 | 0101 Font decision | `font-src 'none'`, fixed system stack and no font network request | TC-10105 |
| REQ-10106 | 0101 Browser Gate | DOM/Cookie/Storage/API/form/popup/download/navigation/embed negative checks | TC-10106 |
| REQ-10107 | 0101 | Disposable synthetic harness with no customer content, secret or Hosted activation | TC-10107 |

## Assumptions and Clarifications

Universal subresource `CORP: same-origin` is browser-proven incompatible with the opaque-origin
Preview. The owner froze `CORP: cross-origin` only for verified Local/Synthetic manifest files and
selected System Font Only rather than granting Font CORS. Typography differences across devices
are an accepted Preview v1 limitation.

**Unapproved assumptions:** None

## Changes

- Added ADR-088 with the frozen isolation, CORP and System Font Only decisions.
- Added a disposable three-site loopback harness with strict Host, ArtifactVersion and exact-file
  Manifest validation.
- Added Browser-level CDP/OOPIF automation so Chrome exercises the real cross-site sandbox.
- Added strict build-derived CSP hashes, `font-src 'none'`, no-store, no-referrer, nosniff and
  restrictive Permissions Policy controls.
- Added fail-closed rejection for font extensions, traversal, unknown paths, versions and Hosts.
- Added the universal/approved CORP matrix and complete negative Browser Gate.
- Added Contract tests and wired them into the repository test command.

## Structure Preservation

- No deployable service, endpoint, database schema, Provider call or customer-data path was added.
- The harness remains under `scripts/` and does not alter Renderer, Artifact or Core runtime APIs.
- No sandbox permission was weakened, no `postMessage` channel was introduced and no CORS access
  grant was added.
- Hosted/Production access capabilities, private assets, CDN/DNS and custom fonts remain deferred.

## Senior Review

- PASS: distinct registrable sites are resolved only inside a disposable browser process.
- PASS: the Preview executes as an OOPIF with an opaque origin and cannot access Core state.
- PASS: exact ArtifactVersion resources are allowlisted; invalid Host/path/version requests fail
  closed and no fallback exists.
- PASS: the approved CORP candidate loads JS/CSS/images without weakening the sandbox or CORS.
- PASS: System Font renders with zero Font requests; Artifact fonts and `@font-face` are absent.
- PASS: error/evidence output contains no token, customer content, secret or Artifact payload.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- Production domain, CDN/DNS, access capability/session, private-asset authorization and operational
  delivery controls require a separate contract before Hosted Preview.
- System-font Persian glyph shapes and text metrics can differ across platforms in Preview v1.
- Environment-gated skipped suites are not represented as PASS by this increment.

**Final status:** PASS
