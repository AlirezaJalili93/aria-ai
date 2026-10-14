# Development Record: 0098 Generated Runtime Security Review

- Increment ID: `0098-generated-runtime-security-review`
- Date: 2026-10-11
- Related domain: Controlled Generation / Synthetic Runtime Security
- [Test report](./test-report.md)
- [Security evidence](./security-evidence.json)

## Scope

Review the actual 0097 static-export candidate with versioned adversarial inputs, reproducible
Artifact identities, dependency security checks, bounded static analysis and real Chromium runtime
network/submission observation. Production Preview isolation remains explicitly unevaluated.

## Source Documents

- Owner-approved frozen `0098` contract, 2026-10-11.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-05` and `SEC-K1-09`; synchronized 2026-10-11.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — `P0-07` and Generated Runtime prohibitions; synchronized 2026-10-11.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Controlled Renderer/build validation and Preview isolation sequencing; synchronized 2026-10-11.
- [ADR-085](../../adr/ADR-085-generated-runtime-security-review.md), [ADR-084](../../adr/ADR-084-controlled-generation-exportability-proof.md) and [ADR-082](../../adr/ADR-082-generation-component-registry-and-ast.md).

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9801 | 0098 exact Artifact | Reuse 0097 Prototype writer and pinned dependency contract | TC-9801, TC-9806 |
| REQ-9802 | 0098 reproducibility | Version tuple, lock hash and Artifact tree hash | TC-9801, TC-9806 |
| REQ-9803 | SPIKE-F1-05 injection | Versioned adversarial corpus and Application validation | TC-9802, TC-9807 |
| REQ-9804 | 0098 static security | Active-resource, secret, path, source-map and generated-sink scans | TC-9804, TC-9806 |
| REQ-9805 | 0098 runtime network | Fresh Chromium profile with CDP request observation/blocking | TC-9803, TC-9808 |
| REQ-9806 | 0098 SimpleForm | Enter/click exercise with zero submission | TC-9803, TC-9808 |
| REQ-9807 | 0098 read-only | GET/HEAD-only static server with rejecting write probe | TC-9804, TC-9808 |
| REQ-9808 | 0098 dependency Gate | Lockfile install, no lifecycle scripts, High/Critical blocker | TC-9804, TC-9806 |
| REQ-9809 | 0098 evidence boundary | Three separate Gate states and guaranteed cleanup | TC-9805, TC-9809 |

## Assumptions and Clarifications

The owner froze a disposable local Chromium review of the exact 0097 candidate. Chrome/Edge is
discovered locally or supplied through `ARIA_0098_BROWSER_PATH`; no browser package is added to the
product graph. Browser request interception and the read-only local server are test controls only,
not a Production CSP or Preview isolation design.

**Unapproved assumptions:** None

## Changes

- Added the versioned synthetic adversarial AST corpus and Application-level fail-closed tests.
- Added a reproducible clean-room security runner with dependency, Artifact and identity evidence.
- Added a dependency-free Chrome DevTools Protocol Browser Gate and read-only static server.
- Added ADR-085, contract tests and repository scripts for the 0098 Gate.

## Structure Preservation

- No deployable, endpoint, Database schema, ArtifactVersion, Preview URL or Hosted infrastructure
  was added.
- The 0097 Prototype writer, canonical AST, Renderer and synthetic fixtures remain authoritative.
- Provider, Customer Content, Storage credentials and Product cookies are absent from the harness.
- Production CSP, iframe sandbox policy, domain separation and scoped Asset access remain F3 scope.

## Senior Review

- PASS: the runner reused the exact 0097 Prototype writer and pinned dependency contract for
  `landing`, adversarial `landing`, `corporate` and `portfolio` candidates.
- PASS: all four clean-room installs, dependency audits, builds and bounded static scans completed;
  High/Critical dependency findings and static security findings were zero.
- PASS: Chromium executed ten generated Pages from fresh disposable profiles with zero forbidden
  runtime requests, WebSocket attempts or runtime exceptions. The intentionally remote control
  request was observed and blocked.
- PASS: the inert injection payload remained escaped data; seven invalid AST mutations failed
  closed through stable Application validation errors.
- PASS: read-only serving, no-JavaScript form behavior, deterministic evidence generation and
  temporary-workspace cleanup were verified.
- PASS: repository tests, lint, typecheck and build completed after the security proof.

## Verification

See [test-report.md](./test-report.md) and [security-evidence.json](./security-evidence.json).

## Remaining Risks

- Production Preview isolation, security headers, cookie boundary and Asset authorization require F3.
- Synthetic adversarial coverage cannot replace Production monitoring or a dedicated penetration test.
- Final Export dependency/license review remains EP-H1.

**Final status:** PASS
