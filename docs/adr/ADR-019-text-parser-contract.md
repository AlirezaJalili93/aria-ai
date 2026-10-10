# ADR-019 — Text Parser Contract

- Status: Accepted for Sprint 1 / S1-F01/F02
- Date: 2026-09-05
- Scope: Provider-neutral text parser interface and deterministic canonicalization

## Decision

The Worker Application exposes a provider-neutral `TextParser` boundary:

```text
parse(source_version) → canonical_text + metadata
```

The approved text parser performs these steps in order:

1. Convert CRLF and CR to LF.
2. Apply Unicode NFC normalization.
3. Convert tabs and Unicode `Zs` space separators to ASCII space.
4. Collapse consecutive ASCII spaces within each line to one space.
5. Remove trailing ASCII spaces from each line.
6. Remove whitespace at the document boundaries.
7. Reject the result if it is empty.

Internal blank lines and line order are preserved. ZWNJ (`U+200C`), ZWJ (`U+200D`), Persian and
Arabic letters, Persian and Latin digits, and punctuation are preserved. Linguistic substitutions
such as `ي→ی` and `ك→ک` are explicitly outside this increment.

## Hash and persistence boundary

`content_hash`, when implemented, is defined over canonical text encoded as UTF-8. The hash
algorithm itself is not approved and therefore is not implemented here. Source `checksum` remains a
separate integrity contract and is not changed by this ADR. The parser does not persist a Source
Version, enqueue a Job, or select a Queue transport.

## Consequences

Equivalent newline and horizontal-spacing variants produce identical canonical text while Persian
orthographic markers and internal blank lines remain intact. Empty-after-normalization input fails
deterministically. Persistence, hash algorithm, metadata fields and task lifecycle remain explicit
follow-up decisions rather than hidden parser behavior.
