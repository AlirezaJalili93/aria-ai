# ADR-083 — Controlled Generation Renderer Proof

- **Status:** Accepted
- **Date:** 2026-10-10
- **Increment:** `0096-controlled-generation-renderer`

## Context

ADR-082 freezes the Provider candidate and Application-owned canonical Generation AST. The next
approved milestone is a reusable rendering proof across landing, corporate and portfolio without
introducing Preview hosting, Artifact persistence, Export, Customer Content or a real Provider.

## Decision

- `packages/generation-renderer` is an independent React/TypeScript package. It has no Next.js,
  Backend, Database, Storage SDK or Provider SDK dependency and can be reused by later Preview and
  Export contracts.
- The Renderer accepts only `generation_ast_schema_v1`. A Provider candidate or structurally
  incomplete Application AST fails before markup is produced.
- A fixed fourteen-Component map is the only rendering dispatch mechanism. No arbitrary HTML,
  CSS, JavaScript, iframe, dynamic import, generated code or executable dependency is accepted.
- Layout, responsive and semantic-style values map to fixed classes backed by Aria design tokens.
  Application text is rendered through React escaping.
- Navigation targets are revalidated against exact Page paths in the same canonical AST.
- Asset UUIDs are resolved only by an injected `AssetResolver`. The synthetic proof uses
  `SyntheticAssetResolver` and fixed same-origin fixture paths; unknown or remote Assets fail
  closed before rendering. Asset UUIDs never become `src` directly.
- Every Page renders independently with exactly one `main` and one accessible visually-hidden
  `h1` from `page.title`. Navbar and Footer remain outside `main`; Component headings use `h2` and
  item headings use `h3`. When an optional heading is absent, the Renderer uses a fixed Persian
  label from `SECTION_LABELS_FA_V1`, never Provider-generated repair text.
- Visually-hidden headings remain in the accessibility tree and do not use `display:none` or
  `aria-hidden`.
- `SimpleForm` remains `preview_only`. Static markup contains no `form`, action, method, submit
  button or field name, so Enter/click cannot issue GET/POST even without JavaScript. Native fields,
  labels and bounded local constraints remain available for the visual proof.
- Rendering the same canonical Page twice is structurally deterministic.

## Consequences

- The three 0095 Persian synthetic fixtures are enriched deterministically by the test harness and
  together exercise all fourteen Components; no new product content is introduced.
- Native `img` plus resolver-supplied dimensions preserves portability beyond Next.js. Only the two
  package-inapplicable Next.js page/image lint rules are disabled; React, TypeScript and
  accessibility lint rules remain active.
- Renderer feasibility does not imply Generation completion, Preview isolation, ArtifactVersion,
  Export, Product acceptance or Hosted activation.
- Real Providers and Customer Content remain prohibited by ADR-073.

## Sources

- Owner-approved frozen `0096` contract, 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — controlled Generation and MVP Component allowlist; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Controlled Renderer and three-Project-Type proof; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-03`; synchronized 2026-10-10.
- [ADR-082](ADR-082-generation-component-registry-and-ast.md), `design-system/MASTER.md` and `packages/design-tokens/tokens.css`.
- Modern Web Guidance `accessibility`, `forms` and `html` references, retrieved 2026-10-10.

**Unapproved assumptions:** None
