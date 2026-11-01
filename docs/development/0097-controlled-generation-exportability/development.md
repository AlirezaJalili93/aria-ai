# Development Record: 0097 Controlled Generation Exportability

- Increment ID: `0097-controlled-generation-exportability`
- Date: 2026-10-10
- Owner: Web/Generation Engineering
- Related domain: Controlled Generation / Exportability Spike
- [Test report](./test-report.md)
- [Clean-room evidence](./clean-room-evidence.json)

## Scope

Prove that the canonical Renderer and Design Tokens can be vendored into disposable Next.js
static-export candidates and independently installed, built and served for landing, corporate and
portfolio outside the Aria monorepo. Final Export format/service, Artifact persistence, Preview
hosting and Generated Runtime security approval remain separate increments.

## Source Documents

- Owner-approved frozen `0097` contract, 2026-10-10.
- [PRD — Aria AI MVP](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09-03/04/09 and FR-12-02/03; synchronized 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — P0-06 export package outside Aria; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Generation pipeline/build validation and Export acceptance direction; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-04`; synchronized 2026-10-10.
- [ADR-084](../../adr/ADR-084-controlled-generation-exportability-proof.md), [ADR-083](../../adr/ADR-083-controlled-generation-renderer-proof.md) and `design-system/MASTER.md`.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9701 | 0097 static contract | Disposable Next.js `output: export` candidate | TC-9701, TC-9706 |
| REQ-9702 | 0097 package boundary | Local Renderer/Token tarballs and portable file dependencies only | TC-9701, TC-9705 |
| REQ-9703 | SPIKE-F1-04 | Independent landing, corporate and portfolio builds | TC-9706 |
| REQ-9704 | 0097 Page contract | Fixed route wrapper and real `out/` HTML for every AST Page | TC-9702, TC-9706 |
| REQ-9705 | 0097 Asset boundary | Existing local allowlist only; no remote Asset resolution | TC-9703, TC-9707 |
| REQ-9706 | 0097 Runtime boundary | No Server Action/API/backend/secret or AST-generated executable code | TC-9702, TC-9703, TC-9707 |
| REQ-9707 | ADR-083 SimpleForm | Emitted HTML has no submission surface | TC-9707 |
| REQ-9708 | 0097 clean room | `npm ci`, audit, build, serve and navigation outside the repo | TC-9705, TC-9706, TC-9708 |
| REQ-9709 | 0097 cleanup/evidence | Temporary packages removed; bounded hashes/results retained | TC-9704, TC-9709 |

## Assumptions and Clarifications

The owner froze Next.js static export, vendored package tarballs and three independent clean-room
builds. The existing ADR-083 `/generation-fixtures/` namespace remains authoritative instead of
broadening the Asset allowlist. Current dependency audit evidence selected Next.js `16.4.0` for the
disposable candidate after `16.3.5` failed with a Critical advisory. Final Export packaging remains
explicitly deferred to EP-H1.

**Unapproved assumptions:** None

## Changes

- Added a deterministic Prototype writer that enriches synthetic candidates into canonical AST,
  copies only local Assets and emits fixed per-Page route wrappers.
- Added the clean-room runner for tarball creation, portable lockfile enforcement, `npm ci`,
  dependency audit, static build, static serve/navigation and output leakage scanning.
- Added bounded JSON evidence and contract tests; integrated the contract tests into root `npm test`.
- Added ADR-084 and updated architecture/development mirrors.

## Structure Preservation

- No production app, Domain, API, Worker, Database, Storage or deployable service was added.
- No ArtifactVersion, ExportJob, public endpoint, Preview host or Customer Content path was added.
- The generated route code is a fixed Application template; AST content remains inert JSON and
  cannot select imports, source text or execution behavior.
- Renderer and Design Tokens are reused through package artifacts; their contracts are not copied
  into a competing Renderer implementation.

## Senior Review

- PASS: clean-room candidates contain no Workspace/parent/absolute monorepo dependency.
- PASS: all seven declared AST Pages were emitted and served from `out/` across the three builds.
- PASS: dependency audits report zero vulnerabilities for the isolated candidates pinned to
  Next.js `16.4.0`.
- PASS: output scans found no active external HTML/CSS resource reference and no secret marker.
- PASS: JavaScript bundle URL literals are recorded separately rather than misclassified as active
  resource loads; full Generated Runtime security approval remains correctly deferred to F1-05.
- PASS: temp roots are deleted in the runner's `finally` boundary on both success and failure.

## Verification

See [test-report.md](./test-report.md) and [clean-room-evidence.json](./clean-room-evidence.json).

## Remaining Risks

- `SPIKE-F1-05` must perform the full Generated Runtime security review before Preview/Hosted use.
- EP-H1 must still decide final Export format, dependency/license treatment and outside-Aria UX.
- The main Web application remains outside this spike; no broad dependency update was made.
- Synthetic fixtures do not authorize Real Providers or Customer Content.

**Final status:** PASS
