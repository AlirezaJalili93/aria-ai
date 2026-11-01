# ADR-082 — Generation Component Registry and Controlled AST v1

- **Status:** Accepted
- **Date:** 2026-10-10
- **Increment:** `0095-generation-output-contract`
- **Decision package:** `0095-A`

## Context

Sprint 3 begins with a schema-first generation contract before any Generation Service, Provider
promotion, Artifact persistence or Preview Runtime. Canonical product documents define three
supported Project Types, fourteen allowed Components and a controlled Renderer, but intentionally
do not define executable Component props, layout/responsive compatibility, Asset authorization or
Application-owned identity behavior. The owner reviewed and froze those missing details through the
0095-A contract.

## Decision

- Provider output is `generation_ast_candidate_v1`, a strict JSON/AST contract. Arbitrary HTML,
  CSS, JavaScript, executable code, dependency declarations, remote URLs, network actions and
  unknown properties are rejected.
- `component_registry_v1` is immutable. It defines the fourteen canonical Components, exact props,
  nested limits, Asset slots, layouts, the single compatible responsive rule, renderer-owned
  interactions and `additionalProperties: false` throughout.
- Candidate Pages contain `title`, ASCII route-safe `path` and ordered Sections. Paths are unique
  and every navigation/action target must equal a Page path in the same candidate.
- Candidate Sections contain no identity or protection fields. Application enrichment alone adds
  stable UUID `page_id` and `section_id` plus initial `protected_state=unprotected`. Revision may
  preserve identity only from trusted prior Application state. Provider-supplied identity or
  protection fails closed.
- Asset references appear only in typed Component slots. Every reference is a UUID declared in the
  root Asset set and must receive an exact positive `authorized_for_generation` result from an
  `AssetRegistryPort` scoped by Account and Project. No lifecycle enum, remote fetch or client-owned
  authorization is introduced.
- Every Asset reference and its named alt-text field are an all-or-none pair. Alt text is normalized
  text of zero to 160 characters; empty is reserved for decorative media. Media layouts for Hero
  and AboutSection require their valid primary-media Asset pair.
- Each Section has exactly one `responsive_rule_ref`. Registry compatibility is authoritative for
  layout/rule combinations and uses the fixed 375/768/1024/1440 behavior matrix.
- Style references use the closed semantic vocabulary mapped by the Renderer to existing Aria
  design tokens. Raw token values, primitive tokens, class names and CSS declarations are invalid.
- `SimpleForm` is preview-only. It performs bounded local validation and never submits, persists,
  logs or transmits entered values.
- Candidate validation, requirement-reference validation, Asset authorization and Application
  enrichment complete before a finalizer may receive the canonical AST. The finalizer port is a
  single atomic persistence boundary; its PostgreSQL Artifact implementation remains deferred to
  the Generation Service increment.

## Text and security rules

- All text is NFC normalized and document-trimmed. CRLF/CR becomes LF only for multiline fields.
- LF is the only allowed control character and only in multiline fields. NUL, tab and every other
  C0/C1 character are rejected. ZWNJ and ZWJ are preserved; Arabic/Persian letter conversion is not
  performed.
- Strings are inert text. The future Renderer must escape them and cannot interpret markup.
- Logs, metrics, traces and errors contain bounded reason codes and identifiers only; candidate AST,
  Component content, form values and raw Provider output are prohibited.

## Consequences

- Incompatible Registry, candidate-schema, canonical-schema or responsive changes require a new
  version; an existing version is never silently rewritten.
- Asset storage/lifecycle, full-regeneration identity matching, external navigation, real form
  submission, Artifact tables, Preview hosting and export remain separate contracts.
- Real Providers, Customer Content and Hosted Generation remain prohibited by ADR-073.
- 0095 adds no migration, endpoint, deployable service or Provider integration.

## Sources

- Owner-approved `0095-A` architecture and final refinements, 2026-10-10.
- [Sprint 0 Technical Decision Pack](https://docs.google.com/document/d/15iFdEFVsdaZ1U38zzwUdZ0p4gB-HemHOcLyjWZSUC0E/edit) — Generation architecture and MVP Component allowlist; synchronized 2026-10-10.
- [Engineering Execution Master Plan](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — Sprint 3 UI/Project Schema and Controlled Renderer; synchronized 2026-10-10.
- [Engineering Backlog Breakdown](https://docs.google.com/document/d/1nIgJtkpkUN5_ZEY0hj1NU2FtjokZziVxSW6VUZEaTKc/edit) — `SPIKE-F1-02`; synchronized 2026-10-10.
- [Product Requirements Document](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — FR-09; synchronized 2026-10-10.
- `design-system/MASTER.md` and `packages/design-tokens/tokens.json`.

**Unapproved assumptions:** None
