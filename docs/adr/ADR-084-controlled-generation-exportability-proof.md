# ADR-084 — Controlled Generation Exportability Proof

- **Status:** Accepted
- **Date:** 2026-10-10
- **Increment:** `0097-controlled-generation-exportability`

## Context

ADR-083 proves deterministic rendering of the canonical Generation AST across landing, corporate
and portfolio. The next ordered backlog item, `SPIKE-F1-04`, must prove that the controlled output
can build and run outside the Aria monorepo without prematurely defining the final Export format,
ArtifactVersion persistence, ExportJob or Preview hosting.

## Decision

- The proof uses a disposable Next.js static-export candidate with `output: "export"` and
  `trailingSlash: true`. It requires no Next.js server, API Route, Server Action, Backend, Database,
  Storage SDK or runtime secret.
- The exact Renderer and Design Token packages are packed into local tarballs and copied under the
  candidate's `vendor/` directory. The only permitted local dependency form is
  `file:./vendor/*.tgz`; Workspace links, parent-directory file links, absolute repository paths,
  global packages and TypeScript path aliases are prohibited.
- The candidate uses fixed Application-owned route wrappers generated from validated AST Page
  paths. AST data cannot provide executable source, imports or runtime behavior.
- Every synthetic Asset resolves under the existing ADR-083 `/generation-fixtures/` allowlist and
  is copied into the candidate. Remote Assets and direct UUID-to-URL conversion remain prohibited.
- Landing, corporate and portfolio are independently staged in operating-system temporary
  directories outside the repository. Each candidate creates its own lockfile, runs `npm ci`,
  dependency audit, static build, static serve and Page navigation checks.
- The proof scans generated HTML/CSS for active external resource references and all text output
  for known secret markers. Framework/library URL literals embedded in JavaScript are reported as
  evidence but are not treated as active network references.
- `SimpleForm` must retain the ADR-083 no-submission property in emitted HTML.
- Temporary source, dependencies and build output are always removed. Only the bounded,
  customer-content-free evidence report remains in the repository.
- Next.js `16.3.5` was rejected by the clean-room dependency Gate because the current audit reports
  a Critical advisory. The isolated candidate pins the audit-clean `16.4.0`; this decision does not
  modify the separate `apps/web` dependency in this increment.

## Consequences

- The same Renderer can produce independent static packages for all supported Project Types.
- This proof does not select the final EP-H1 Export format, dependency/license policy or delivery
  contract and does not create a production Export surface.
- Generated Runtime security review remains the next ordered Gate (`SPIKE-F1-05`).
- ArtifactVersion, GenerationJob persistence, Preview isolation, Customer Content, Real Provider
  execution and Hosted activation remain outside this increment.

## Sources

- Owner-approved frozen `0097` contract, 2026-10-10.
- [PRD — Aria AI MVP](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09 generated Artifact and FR-12 export/handoff boundaries; synchronized 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — P0-06 and schema-first exportable package direction; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — controlled Renderer, build validation and deferred final Export; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-04`; synchronized 2026-10-10.
- [ADR-082](ADR-082-generation-component-registry-and-ast.md) and [ADR-083](ADR-083-controlled-generation-renderer-proof.md).
- Modern Web Guidance `forms` and `security`, retrieved 2026-10-10.

**Unapproved assumptions:** None
