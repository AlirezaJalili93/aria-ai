# Development Record: 0039 Context Structuring Workflow

- Increment ID: `0039-context-structuring-workflow`
- Date: 2026-09-06
- Story: S1-H02 — Context Structuring Workflow
- [Test report](./test-report.md)

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-H02; Drive modified 2026-08-17, reviewed 2026-09-06
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-01 and validation pipeline; Drive modified 2026-08-17, reviewed 2026-09-06
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — TC-CTX-007/008/009 and deterministic Fake-provider testing; Drive modified 2026-08-17, reviewed 2026-09-06
- [Repository & Code Structure Specification v1.0](https://docs.google.com/document/d/1NkMTAZRTIgyqfd1C4pKVRRK69swPQI7T-YymV9hBzz0/edit) — shared Application use case and Worker wrapper; Drive modified 2026-08-17, reviewed 2026-09-06
- Owner-approved canonical H02 contract dated 2026-09-06

Repository documents are developer-facing mirrors. The linked approved Drive documents and the
explicit owner resolution above are canonical.

## Scope

Implement the provider-neutral H02 orchestration as one shared Backend Application use case. Resolve
an immutable latest-ready Source snapshot, execute through the existing AI port, meter the call,
validate the complete candidate Batch and persist it with an atomic gap-free Context Version.
Provide the SQLAlchemy adapters and a thin Worker wrapper without adding the deferred public API,
Job/Queue contract, repair, Provider runtime, entitlement or quota integration.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-3901 | H02 provider-neutral orchestration and Fake Adapter contract | `ContextStructuringUseCase`; shared AI port; Fake tests | TC-3901 |
| REQ-3902 | Immutable latest-ready Source snapshot | `ContextSnapshotReader`; `SqlAlchemyContextSnapshotReader` | TC-3902, TC-3903 |
| REQ-3903 | Validate-first, all-or-nothing candidate Batch | candidate types; provenance/claim validation; transactional UoW | TC-3904–TC-3907 |
| REQ-3904 | Exact duplicate rejects the complete Batch with `DUPLICATE_CONTEXT_ITEM` | exact identity set and `ContextStructuringDuplicateError` | TC-3908 |
| REQ-3905 | Atomic gap-free Context Version advancement | row-locked Project allocation; Batch insert/pointer update transaction | TC-3909, TC-3910 |
| REQ-3906 | Shared Backend Application use case invoked by Worker | `packages/backend-application`; `ContextStructuringTask` | TC-3911 |
| REQ-3907 | Safe lifecycle logging, metering and no sensitive content | safe events; `UsageLedger.append`; rationale-free write DTO | TC-3912 |
| REQ-3908 | Explicit H02 exclusions | ADR-026 and contract fitness test | TC-3913 |

## Assumptions and Clarifications

The owner resolved the exact-duplicate ambiguity on 2026-09-06: two candidates with identical
`(item_type, content)` reject the entire Batch. Merge, silent deduplication, non-exact similarity,
normalization and confidence/provenance combination remain deferred.

**Unapproved assumptions:** None

## Changes

- Added `packages/backend-application`, a non-deployable Python package shared by API and Worker.
  Moved the canonical AI Execution and Usage Ledger Application contracts into it while retaining
  compatibility re-exports at their former Worker paths.
- Added immutable Source snapshot and candidate DTOs, exact schema/value checks, explicit failure
  types and the provider-neutral `ContextStructuringUseCase`.
- Added validate-first provenance, offset, Fact evidence, unsupported-claim and exact-duplicate
  gates. `rationale_short` exists only on the candidate DTO and cannot enter the persistence DTO.
- Added authoritative Usage Ledger append for every returned provider execution before downstream
  candidate validation/persistence.
- Added SQLAlchemy snapshot and Unit-of-Work adapters. Snapshot selection uses one ranked query;
  persistence locks the Project row and commits Batch plus Project Version pointer together.
- Added a thin Worker task wrapper that only invokes the shared use case.
- Extended safe structured logging with `context_version`, added ADR-026 and synchronized the
  architecture/data-model mirrors.
- Updated both locked Python environments and Railway build contexts for the shared package.

## Architecture and Design Decisions

- The external AI call occurs outside a long database transaction. The immutable snapshot is read
  once first; a short write transaction begins only after all candidate validations pass.
- Snapshot membership—not mutable current Source state—is authoritative provenance for one run.
- Usage is written even when a paid/provider execution later fails candidate validation; this keeps
  the Ledger truthful while Context state remains all-or-nothing.
- Exact equality means Python string equality over unchanged `content`; no trim, Persian/Arabic
  character conversion, case folding, similarity or semantic merge occurs.
- The Project row lock serializes Version allocation. The guarded pointer update and Batch flush
  share the same transaction, so failure produces neither partial items nor consumed numbers.
- Unsupported-claim semantics remain behind an injected Application port because the approved
  contract defines the validation stage, not a concrete detection algorithm.

## Structure Preservation

- `web`, `api` and `worker` remain the only deployables; the shared package adds no service.
- API Infrastructure implements snapshot/persistence ports; the shared Application package imports
  neither FastAPI, SQLAlchemy, Celery, Redis nor any Provider SDK.
- Worker contains only a transport-facing wrapper and no copied Context Domain, provenance,
  duplicate or persistence rules.
- Existing AI and Usage import paths remain compatibility facades, avoiding unrelated consumer
  rewrites while establishing the canonical shared boundary.
- No OpenAPI route, UI, concrete Job type/envelope, Queue producer, retry/repair/fallback,
  entitlement/quota policy, Provider adapter or model name was added.

## Senior Review

- PASS: the Source query filters by Account/Project, excludes deleted Sources and non-ready
  Versions, ranks per Source and returns only the highest ready `version_no`.
- PASS: the snapshot is resolved exactly once before AI execution and every reference must address
  that same immutable set; offset ranges require canonical text and fit its length.
- PASS: schema, Fact evidence, provenance, unsupported-claim and duplicate validation complete
  before the Unit of Work opens, so invalid Batch cases cannot partially persist.
- PASS: duplicate identity is exactly `(item_type, content)`; all non-exact content remains distinct
  and exact duplicates raise the stable `DUPLICATE_CONTEXT_ITEM` contract.
- PASS: real PostgreSQL tests demonstrate serialized concurrent allocation (`1, 2`) and rollback of
  both flushed Context Items and Project pointer when a later transaction step fails.
- PASS: Usage metering captures provider/model/token/cost/version metadata through the pre-existing
  provider-neutral port; no concrete Provider behavior was introduced.
- PASS: lifecycle events carry only safe IDs, duration, Version, status and reason. Candidate
  content, canonical text, raw Source References and `rationale_short` never reach the logger.
- PASS: compatibility wrappers, Docker build contexts, lockfiles, lint, strict types, builds and all
  repository test suites were reviewed and passed.

## Verification

See [test-report.md](./test-report.md). Contract, Application, PostgreSQL concurrency/rollback,
Worker delegation and repository-wide quality gates passed.

## Remaining Risks

- H02 is an Application foundation, not a runnable AI vertical slice. Public trigger integration,
  concrete Job/Queue composition and a real Provider remain intentionally deferred.
- The unsupported-claim checker has an approved port and fail-closed path, but its concrete policy
  cannot be implemented until that algorithm/evaluation contract is approved.
- Workflow/prompt/pricing/routing/budget/timeout values remain caller-owned; this Increment creates
  no defaults or task vocabulary.
- Semantic duplicate merge remains deferred and exact duplicates intentionally fail the Batch.

**Final status:** PASS
