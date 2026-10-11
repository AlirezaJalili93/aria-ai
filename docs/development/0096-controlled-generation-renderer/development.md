# Development Record: 0096 Controlled Generation Renderer

- Increment ID: `0096-controlled-generation-renderer`
- Date: 2026-10-10
- Owner: Web/Generation Engineering
- Related domain: Controlled Generation / Renderer Proof
- [Test report](./test-report.md)

## Scope

Implement a reusable React Renderer proof for the canonical `generation_ast_schema_v1`, enforce the
fourteen-Component Registry at the consumer boundary and verify landing, corporate and portfolio
fixtures. Preview hosting, Artifact persistence, Export, Provider promotion, Customer Content and
Hosted activation remain outside this increment.

## Source Documents

- Owner-approved frozen `0096` Renderer contract, 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — Generation architecture and MVP Component allowlist; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — controlled rendering and three-Project-Type feasibility; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-03`; synchronized 2026-10-10.
- [ADR-082](../../adr/ADR-082-generation-component-registry-and-ast.md), [ADR-083](../../adr/ADR-083-controlled-generation-renderer-proof.md), `design-system/MASTER.md` and package contracts.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-9601 | 0096 / ADR-082 | Independent `@aria/generation-renderer` accepts canonical AST only | TC-9601, TC-9602 |
| REQ-9602 | 0096 security | Fixed fourteen-Component map, React escaping and no executable output surface | TC-9603, TC-9607 |
| REQ-9603 | 0096 Asset boundary | UUID Assets resolve only through local allowlisted `SyntheticAssetResolver` | TC-9605 |
| REQ-9604 | 0096 headings | One independent `main`/accessible hidden `h1`; h2/h3 policy and external Navbar/Footer | TC-9602, TC-9603 |
| REQ-9605 | 0096 SimpleForm | No-JavaScript preview form has labels but no static submission surface | TC-9604 |
| REQ-9606 | 0096 determinism/navigation | Repeat rendering is stable and navigation remains in exact AST Page set | TC-9602, TC-9606 |
| REQ-9607 | SPIKE-F1-03 | Three existing Persian Project-Type fixtures cover all fourteen Components | TC-9603 |
| REQ-9608 | Repository quality gates | Package participates in lint, typecheck, test, build and validate | TC-9608 |

## Assumptions and Clarifications

The owner froze package placement, synthetic-only Asset resolution, heading policy, SimpleForm
no-submit behavior and all deferred Preview/Artifact/Export boundaries. Existing 0095 fixtures and
Registry labels are reused; no product behavior or data is inferred.

**Unapproved assumptions:** None

## Changes

- Added the independent React/TypeScript Renderer package, strict consumer validator, fixed
  Component map and token-driven stylesheet.
- Added same-origin synthetic Asset resolution and one local fixture Asset.
- Added deterministic static-markup tests for canonical-only input, all Project Types and all
  fourteen Components.
- Added ADR-083 and updated architecture/development mirrors and root quality commands.

## Structure Preservation

- No Backend, Domain, Database, Storage, Provider or Next.js runtime dependency was added.
- No endpoint, migration, deployable service, Preview host, Artifact table or Export path was added.
- Existing Registry/AST rules remain owned by 0095; 0096 performs bounded consumer enforcement and
  does not create a second product schema.
- All CSS values use existing primitive/semantic/component tokens; no raw Component color value was
  introduced.

## Senior Review

- PASS: Renderer dispatch is a complete fixed `Record<ComponentType, renderer>` and contains no
  runtime Component discovery, dynamic import or Provider-owned execution path.
- PASS: React escaping, exact Page-path checks and same-origin Asset-path enforcement close the
  direct markup, navigation and Asset injection boundaries.
- PASS: every Page is rendered independently with one `main`/`h1`; optional headings use the fixed
  `SECTION_LABELS_FA_V1` vocabulary and remain in the accessibility tree.
- PASS: the no-`form` SimpleForm design removes native static submission rather than depending on
  hydration or an event handler to cancel it.
- PASS: React best-practices review found no hooks, shared mutable state, render-time I/O,
  waterfalls, inline Component definitions or client bundle/dynamic-loading concerns.
- PASS: only Next.js-specific page/image lint rules are disabled for this portable package; all
  package lint, strict typecheck, test and build gates pass.

## Verification

See [test-report.md](./test-report.md).

## Remaining Risks

- Preview isolation/CSP and immutable Artifact persistence require separate approved increments.
- The synthetic proof does not establish real-Provider or Customer-Content quality.
- Visual/manual browser QA belongs to the future Preview/UI contract; this increment verifies
  deterministic static semantics, accessibility structure and security boundaries.

**Final status:** PASS
