# ADR-085 — Generated Runtime Security Review

- **Status:** Accepted
- **Date:** 2026-10-11
- **Increment:** `0098-generated-runtime-security-review`

## Context

ADR-084 proves that the controlled Generation AST can produce independently installed and served
Next.js static exports. `SPIKE-F1-05`, `P0-07` and `SEC-K1-09` require the next Gate to review the
security of that generated runtime. The review must exercise the actual 0097 candidate in a
browser, while keeping Production Preview CSP, iframe sandboxing, domain separation, scoped Asset
delivery and Hosted activation within the later F3 contract.

## Decision

- The review rebuilds the exact 0097 Prototype through the same `writePrototype` boundary, pinned
  dependency set and three versioned Persian synthetic fixtures. A fourth candidate injects the
  versioned inert-markup adversarial case through the same pipeline.
- Every candidate records Renderer, Registry, AST schema, Fixture and Security Suite versions,
  plus SHA-256 fingerprints for the lockfile and actual static Artifact tree.
- Candidate dependencies are installed from their generated lockfile with lifecycle scripts
  disabled. Critical or High audit findings block the Gate; lower severities remain in evidence.
  Provider-generated packages and Provider SDKs are prohibited from the graph.
- Static analysis rejects active remote/data/blob/javascript resource references, known secret
  markers, repository paths, source maps and executable sinks in Application-owned generated
  source. Framework JavaScript is permitted and is not judged by naive bundle string matching.
- A fresh-profile local Chromium process runs the real Artifact. DevTools request interception
  permits only same-origin GET/HEAD static resources, exact AST Page navigation and allowlisted
  fixture images. API paths, credential-bearing requests, external network, writes, WebSocket and
  non-AST navigation fail closed. A blocked control request proves the interception boundary.
- The disposable server is read-only and proves that a write request is rejected. Browser checks
  exercise Page navigation and SimpleForm controls with and without native Enter/click behavior;
  no submission, injected markup execution, remote image, cookie or persistent storage is allowed.
- The Application Generation validator consumes the versioned adversarial corpus. Markup-like text
  may remain only as inert text; unknown Component/property, unsafe navigation, remote/data Asset,
  traversal path and Provider-owned protection state are rejected with content-safe errors.
- The harness, browser profile, dependencies and Artifact are removed in `finally`. Only bounded,
  synthetic and content-safe evidence remains.
- Evidence reports three independent outcomes: Static Artifact Security, Synthetic Runtime
  Behavior and Production Preview Security. The first two must pass; the third is always
  `NOT_EVALUATED` in 0098.

## Consequences

- A passing 0098 allows work to proceed toward Generation Service/ArtifactVersion and the later
  Production Preview isolation design. It does not authorize Hosted Preview, Customer Content,
  Real Provider execution or a Production CSP/origin policy.
- Final CSP values, iframe sandbox capabilities, registrable-domain separation, scoped Asset
  access and reporting endpoints remain F3 decisions. Test-time interception is evidence, not a
  substitute for those controls.
- EP-H1 still owns final Export format and dependency/license decisions.

## Sources

- Owner-approved frozen `0098` contract, 2026-10-11.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-05` and `SEC-K1-09`; synchronized 2026-10-11.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — Generation Runtime prohibitions and `P0-07`; synchronized 2026-10-11.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Controlled Renderer and deferred Preview isolation; synchronized 2026-10-11.
- [ADR-082](ADR-082-generation-component-registry-and-ast.md), [ADR-083](ADR-083-controlled-generation-renderer-proof.md) and [ADR-084](ADR-084-controlled-generation-exportability-proof.md).
- Modern Web Guidance `security`, `validate-origins` and `trusted-types`, retrieved 2026-10-11.

**Unapproved assumptions:** None
