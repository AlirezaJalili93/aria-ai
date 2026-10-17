# Development Record: 0095 Generation Output Contract

- Increment ID: `0095-generation-output-contract`
- Date: 2026-10-10
- Owner: Platform/API/Generation Engineering
- Related domain: Controlled Generation / Component Registry
- [Test report](./test-report.md)

## Scope

Freeze and implement the contract-first boundary for controlled site-generation output: a
versioned fourteen-Component registry, strict Provider candidate and Application-owned canonical
AST schemas, deterministic business validation, tenant/project-scoped Asset authorization,
Application enrichment and one atomic finalizer port. No Artifact persistence, Renderer runtime,
Provider promotion, Customer Content or Hosted Generation is introduced.

## Source Documents

- Owner-approved frozen `0095-A Component Registry` contract and final refinements, 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — Generation architecture and MVP Component allowlist; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 3 schema-first generation and Controlled Renderer; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-02`; synchronized 2026-10-10.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09; synchronized 2026-10-10.
- [ADR-082](../../adr/ADR-082-generation-component-registry-and-ast.md), `design-system/MASTER.md` and `packages/design-tokens/tokens.json`.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9501 | 0095-A / FR-09 | Immutable Registry and strict candidate/canonical JSON schemas cover exactly fourteen Components | TC-9501, TC-9502 |
| REQ-9502 | 0095-A | Closed props, limits, style vocabulary and layout/responsive compatibility | TC-9501, TC-9503 |
| REQ-9503 | 0095-A ownership | Provider identity/protection rejected; Application adds unique Page/Section IDs and `unprotected` | TC-9502, TC-9504 |
| REQ-9504 | Final Asset refinements | UUID-only exact authorization, Asset/alt pairing and media-layout Asset requirement | TC-9503, TC-9505 |
| REQ-9505 | 0095-A references | Unique ASCII Page paths, in-AST navigation targets and pinned Requirement references | TC-9503, TC-9506 |
| REQ-9506 | 0095-A SimpleForm | Preview-only bounded form fields with no action, endpoint or network behavior | TC-9503, TC-9507 |
| REQ-9507 | 0095-A text/security | NFC, multiline LF exception, C0/C1 rejection and content-safe stable errors | TC-9503, TC-9508 |
| REQ-9508 | 0095 persistence boundary | Validation/authorization/enrichment precede one atomic finalizer invocation | TC-9504, TC-9505, TC-9509 |

## Assumptions and Clarifications

The owner froze all Component props, nested structures, Asset slots, paired alt fields,
layout/responsive combinations, semantic style vocabulary, path and navigation rules,
Application-owned identity/protection behavior, SimpleForm preview-only behavior and the deferred
Artifact/Renderer/Provider boundaries.

**Unapproved assumptions:** None

## Changes

- Added ADR-082 and architecture mirrors for the controlled Generation boundary.
- Added immutable Registry, Provider candidate schema and Application canonical schema v1.
- Added a framework-free Application validator, Asset authorization port, deterministic
  enrichment and atomic finalizer port.
- Added three Persian synthetic fixtures spanning landing, corporate and portfolio and all fourteen
  Components.
- Added executable positive, negative, security, ownership and atomic-boundary contract tests.

## Structure Preservation

- The Application package imports no FastAPI, SQLAlchemy, Provider SDK, browser or Infrastructure
  implementation.
- No endpoint, migration, table, DB role, deployable service or Provider integration was added.
- Existing design tokens are referenced through a closed semantic vocabulary; raw CSS/HTML/JS is
  not accepted.
- Asset lifecycle remains outside this increment; the Port consumes only a scoped
  `authorized_for_generation` decision.
- Artifact persistence, Preview, Renderer execution, revision matching and real form submission
  remain deferred to explicit later contracts.

## Senior Review

- PASS: Registry and schemas separate Provider-owned candidate fields from Application-owned IDs
  and protection state.
- PASS: all fourteen Components are represented by the versioned fixtures and executable validator.
- PASS: unknown fields, remote URLs, invalid references, incompatible layouts and unauthorized
  Assets fail before finalization.
- PASS: paired Asset/alt semantics and Hero/About media requirements match the final refinements.
- PASS: finalizer failure exposes no successful artifact through this Application boundary.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- The PostgreSQL Artifact model and finalizer implementation are intentionally deferred; atomicity
  is verified at the Application port boundary only.
- Renderer escaping, Preview isolation and revision identity matching require their own approved
  contracts before execution of generated output.
- Real Provider, Customer Content and Hosted Generation remain prohibited.

**Final status:** PASS
