# Development Record: 0082 Controlled Clarification to Scope E2E

- **Status:** COMPLETE — controlled synthetic Gate passed
- **Increment ID:** `0082-controlled-clarification-to-scope-e2e`
- **Source sync date:** 2026-09-29
- [Test report](./test-report.md)

## Scope

Prove the synthetic-only E2E-02 control path from an open Critical Gap through two upfront
Clarification questions, two explicit human answers, K02 unblocking and a new explicit AI-05
command to one Scope Draft. The increment reuses existing Application commands and production
resolution semantics. It does not propagate answer text into Context or Requirements and does not
add production orchestration, a public endpoint, customer data or a real Provider.

## Source Documents

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — E2E-02 and Sprint acceptance; reread 2026-09-29.
- [ADR-038](../../adr/ADR-038-clarification-domain-api.md), [ADR-039](../../adr/ADR-039-gap-inbox-review-contract.md), [ADR-042](../../adr/ADR-042-scope-readiness-policy.md), [ADR-057](../../adr/ADR-057-durable-outbox-delivery-runtime.md), [ADR-062](../../adr/ADR-062-scope-generation-runtime-foundation.md), [ADR-063](../../adr/ADR-063-controlled-synthetic-context-to-scope-integration.md) and [ADR-068](../../adr/ADR-068-controlled-clarification-to-scope-e2e.md).
- Owner-approved and frozen 0082 sequencing and boundary, 2026-09-29.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
| --- | --- | --- | --- |
| REQ-8201 | Backlog E2E-02; ADR-063/068 | Explicit synthetic Context-to-Clarification-to-Scope harness | TC-8201 |
| REQ-8202 | ADR-038/039; owner sequencing | Create both questions before answering; first answer keeps Gap open; second resolves | TC-8202 |
| REQ-8203 | ADR-042/062 | K02 blocks before complete resolution; a new explicit AI-05 command succeeds afterward | TC-8203 |
| REQ-8204 | ADR-038 J03-B deferral | Context Version and Context/Requirement revisions stay unchanged; answers are not AI-05 input | TC-8204 |
| REQ-8205 | ADR-057/062/063/068 | Replay, tenant isolation, invalid input, pinning, duplicate delivery and leakage-negative gates | TC-8205 |

## Assumptions and Clarifications

- Question 1 and Question 2 are both persisted before either answer is submitted.
- Existing ADR-038 resolution behavior is authoritative and is not modified.
- Clarification answers affect Gap/K02 state only; J03-B answer ingestion remains deferred.
- **Unapproved assumptions:** None

## Changes

- Accepted ADR-068 and linked it from the ADR index.
- Extended the controlled Context-to-Scope harness with the isolated `--clarification-resolution`
  scenario and safe, bounded stage diagnostics.
- Created both questions for every Critical Gap before recording any answer, then verified that the
  first answer preserves `Gap=open` and the second resolves it.
- Added replay, empty-answer, cross-tenant, side-effect-free blocked Scope and answer-leakage
  assertions, plus exact Context/Requirement revision preservation checks.
- Added the controlled PowerShell Gate, package command and static contract suite.
- Corrected partial-index inference in the Clarification repository by making its approved
  `status = 'open'` predicate literal rather than bound.

## Architecture and Design Decisions

ADR-068 is accepted and frozen. The harness may orchestrate existing commands only inside a
dedicated synthetic test database; it must not create a production chain or mutate Gap state by
direct SQL.

## Structure Preservation

PASS. No public endpoint, schema, production scheduler, Provider, runtime policy or Domain state
machine changed. Existing Clarification and K02/K03 commands remain the only mutation boundaries.
The repository correction preserves the existing duplicate-question invariant and makes its SQL
predicate identical to migration 0016's partial unique index.

## Senior Review

- **Sequencing:** PASS. Both questions exist before Question 1 is answered; no iterative lifecycle
  or ADR-038 semantic change was introduced.
- **Atomicity/idempotency:** PASS. Resolution replay returns the same audit record, blocked AI-05
  creates no Job/Outbox/Usage/Draft, and existing Worker rollback/replay suites pass.
- **Tenant isolation:** PASS. A second active Tenant receives safe not-found for question and answer
  commands and leaves authoritative state unchanged.
- **J03-B boundary:** PASS. Context Version, Context Item revisions, Requirement revisions and Source
  counts remain exact; question and answer strings are absent from AI-05 payload and Scope Draft.
- **Repository safety:** PASS. The sixth repeated prepared Clarification insert exposed PostgreSQL
  generic-plan partial-index inference failure (`42P10`). A literal predicate fixes it without
  broadening persistence or authorization behavior.

## Verification

See [test report](./test-report.md). The controlled PostgreSQL/Worker Gate, contract suite, lint,
typecheck, build, full repository tests and documentation/architecture validation passed.

## Remaining Risks

- Real-model quality, customer-content processing, Hosted activation and J03-B propagation remain
  outside this increment.
- Pytest could not write optional cache metadata in the worktree because of local Windows ACLs;
  test execution and results were unaffected.
