# ADR-088 — Local Preview Isolation Architecture

**Status:** Accepted / Frozen

**Date:** 2026-10-12
**Increment:** `0101-preview-isolation-architecture`

## Sources

- Engineering Backlog, `DEVOPS-F3-01` and `SEC-F3-04` — [Canonical Drive](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit), synchronized 2026-10-12.
- Engineering Master Plan, Sprint 3 §14.4 and Threat Boundary `TB-08` — [Canonical Drive](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit), synchronized 2026-10-12.
- Owner-approved 0101 contract, 2026-10-12.
- ADR-082 through ADR-087.

## Decision

The local proof uses two genuinely different registrable test domains:
`core.aria-core.test` for the parent and one version-bound origin,
`v-<artifact-version>.aria-preview.test`, for the immutable Preview. Different localhost ports are
not treated as evidence of site separation. Host resolution to loopback exists only in the
disposable browser process.

The Preview iframe has exactly `sandbox="allow-scripts"`. `allow-same-origin`, forms, popups,
downloads, top navigation and every other sandbox permission are absent. Version 1 has no
`postMessage` contract. The Core origin, cookies, storage, DOM, APIs and secrets are unavailable to
the opaque-origin child.

One Preview origin serves exactly one immutable ArtifactVersion. All HTML, JavaScript, CSS and
images resolve against that origin. Preview v1 uses only the fixed `system-ui, sans-serif` stack;
packaged and remote font resources, `@font-face` and font preload are prohibited. Unknown Host
values, another version origin, traversal and non-file paths fail closed. The delivery layer does
not rewrite Artifact bytes or repoint a version.

The Preview response uses a build-derived hash CSP:

```text
default-src 'none';
base-uri 'none';
script-src 'self' <hashes of exact inline script bytes>;
style-src 'self' <hashes of exact inline style bytes>;
img-src 'self';
font-src 'none';
connect-src 'none';
form-action 'none';
object-src 'none';
frame-src 'none';
worker-src 'none';
frame-ancestors <exact Core origin>;
```

`unsafe-inline` and `unsafe-eval` are prohibited. `frame-ancestors` is delivered as an HTTP header.
The proof also sends `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, a restrictive
Permissions Policy and `Cache-Control: no-store`.

## Resolved CORP compatibility decision

An iframe without `allow-same-origin` has an opaque security origin. Applying
`Cross-Origin-Resource-Policy: same-origin` to every Preview subresource may therefore block a
same-URL-origin script, stylesheet or image when requested by that opaque child. The local
proof MUST run the universal `same-origin` policy and a narrowly scoped compatibility candidate in
a real Chromium browser, while keeping the sandbox unchanged.

The owner accepted the browser-proven Local/Synthetic policy on 2026-10-12. Preview HTML and only
the immutable JS, CSS and image files present in the exact ArtifactVersion manifest receive
`Cross-Origin-Resource-Policy: cross-origin`. `Access-Control-Allow-Origin` remains absent. Core
App/API responses, private storage, customer assets, other ArtifactVersions and unknown files do
not inherit this policy.

`CORP: cross-origin` is a resource-loading policy, not access authorization. The server validates
the exact configured Preview Host, pinned ArtifactVersion and manifest file path before sending a
file. Traversal, unknown paths and any attempt to fall through to another version fail closed.
Adding `allow-same-origin` to make a test pass remains prohibited.

## Browser matrix evidence — 2026-10-12

The local proof ran in headless Google Chrome with a Browser-level DevTools session and a distinct
out-of-process iframe target. Both variants retained the exact `sandbox="allow-scripts"` boundary,
separate registrable test domains, the same hash-based CSP and the same exact ArtifactVersion.

| Candidate | JS | CSS | image | system font | isolation negative cases | Result |
|---|---:|---:|---:|---:|---:|---|
| universal subresource `CORP: same-origin` | blocked | loaded | blocked | loaded | pass | incompatible |
| version-bound subresource `CORP: cross-origin` | loaded | loaded | loaded | loaded | pass | compatible candidate |

The negative gate denied parent DOM, Cookie and Storage access; opaque-origin Storage; Core API
fetch; unapproved inline script; form submission; popup; download; top navigation; and embedding
from an unapproved registrable domain. The local SimpleForm validation remained functional and no
sandbox permission was added.

This evidence closed the browser-execution uncertainty. The Local/Synthetic policy is frozen as
explicit `CORP: cross-origin` on exact manifest-bound static Preview resources, with no CORS read
grant, while document embedding remains restricted by `frame-ancestors`.

This is not a Production or customer-asset policy. Hosted Preview must separately contract and
test access capabilities, private-asset authorization, CDN behavior and Production CSP before any
customer content is enabled.

## Final Preview v1 font policy

The owner selected System Font Only on 2026-10-12 after a manifest-bound `@font-face` verification
proved that opaque-origin web-font fetching requires CORS. The Preview CSP therefore enforces
`font-src 'none'`, the verified manifest rejects `.woff`, `.woff2`, `.ttf` and `.otf`, and the
Browser Gate requires zero font-network requests plus successful `system-ui` rendering. No CORS
header was added and no sandbox restriction was weakened.

Cross-device Persian glyph shape and text metrics may differ in Preview v1. Hosted/custom fonts,
private assets and their access capability remain deferred and require a separate contract before
customer content or Hosted Preview can be enabled. This font rule does not apply to the Core App
Design System.

## Non-goals

Production domains, DNS/CDN, capability or session design, public/guest Preview, Hosted Publishing,
customer content, Provider execution and Production operational policy remain deferred. This proof
does not authorize Preview activation.
