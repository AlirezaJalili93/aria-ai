# Development Record: 0032 Text Parser Contract

[Test report](./test-report.md)

## Scope

- Increment ID: `0032-text-parser-contract`
- Stories: `S1-F01 — Parser Interface` and `S1-F02 — Text Parser`
- Status: Completed
- Scope: Provider-neutral Worker Application parser boundary and deterministic text
  canonicalization for text Source Versions.
- Explicitly deferred: content-hash algorithm implementation, Source checksum semantics, metadata
  schema, Source Version persistence, Job/Queue task registration, file parsing, timeout/retry and
  language-specific orthographic rewrites.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk) — S1-F01/F02 parser interface and text-parser acceptance; read 2026-09-05.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk) — Context Parsing & Canonicalization workstream; read 2026-09-05.
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit?usp=drivesdk) — Source Version fields and ready invariant; read 2026-09-05.
- [ADR-012 — Context Source Versioning](../../adr/ADR-012-context-source-versioning.md)
- [ADR-019 — Text Parser Contract](../../adr/ADR-019-text-parser-contract.md)
- Repository instructions (`AGENTS.md`)

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3201 | S1-F01; ADR-019 | Provider-neutral `TextParser.parse(source_version)` boundary | TC-3201 |
| REQ-3202 | Owner approval 2026-09-05; ADR-019 | CRLF/CR to LF, NFC, tab/Zs conversion, repeated-space collapse and line/document trimming | TC-3202, TC-3203 |
| REQ-3203 | Owner approval; ADR-019 | Preserve internal blank lines, order, ZWNJ, ZWJ, letters, digits and punctuation | TC-3202, TC-3203 |
| REQ-3204 | Owner approval; ADR-019 | Empty validation occurs after normalization | TC-3204 |
| REQ-3205 | Owner approval; ADR-019 | No `ي/ی` or `ك/ک` linguistic substitutions | TC-3202, TC-3205 |
| REQ-3206 | Owner approval; ADR-019 | Canonical hash source is defined, but algorithm and implementation remain deferred | TC-3205 |

## Changes

- Added Worker Application `TextParser`, `SourceVersionInput`, `ParsedText` and
  `CanonicalTextParser`.
- Implemented the exact approved normalization order without provider, Queue or persistence
  imports.
- Added empty-after-normalization rejection.
- Added ADR-019, updated ADR-012 and the durable-queue execution plan, and added contract/unit tests.
- Kept hash generation absent until its algorithm is approved; no Source checksum behavior changed.

## Structure Preservation

- Parser code remains in the Worker Application boundary and is framework/provider-neutral.
- No Celery, Redis, SQLAlchemy, asyncpg, Queue, Source repository or Job lifecycle code was added.
- Existing Context Source/Version schema and API transaction remain unchanged.
- No file parser, language rewrite, metadata taxonomy, migration or deployable was introduced.

## Senior Review

- PASS: normalization order matches the owner-approved six transformation steps.
- PASS: NFC may compose Unicode sequences, but no Arabic/Persian character substitution is applied.
- PASS: ZWNJ/ZWJ and internal blank lines remain intact.
- PASS: empty detection occurs only after normalization.
- PASS: parser does not calculate SHA-256 or any other unapproved hash algorithm.
- PASS: parser returns an intentionally empty metadata object because metadata fields are not yet
  contracted.
- PASS: Source checksum and canonical Version content hash remain separate boundaries.

## Assumptions and Clarifications

**Unapproved assumptions:** None

The owner approved the F01/F02 semantic contract on 2026-09-05. The hash algorithm, metadata
schema and persistence orchestration remain explicitly deferred.

## Verification

See [test-report.md](./test-report.md). Parser unit/contract tests and Worker quality checks passed;
repository-wide gates are recorded there after the final run.

## Remaining Risks

- A future increment must select and implement the approved content-hash algorithm over canonical
  UTF-8 bytes.
- A future Worker task contract must connect parser output to Source Version persistence and Job
  lifecycle transitions.
- File parsing and parser metrics remain outside F01/F02.

**Final status:** PASS
