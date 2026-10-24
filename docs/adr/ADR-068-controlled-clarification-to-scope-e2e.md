# ADR-068: Controlled Clarification-to-Scope E2E

- **Status:** Accepted / Frozen
- **Date:** 2026-09-29
- **Candidate increment:** `0082-controlled-clarification-to-scope-e2e`
- **Extends:** ADR-038, ADR-039, ADR-042, ADR-062 and ADR-063

## Problem and evidence

Sprint 1 Backlog E2E-02 requires an ambiguous brief, Gap, Clarification and Scope journey.
The existing 0077 harness explicitly dismisses synthetic Gaps. It does not prove that recording
human answers through the accepted Clarification commands resolves a Gap and allows a subsequent
explicit Scope command. Unit and repository tests of those commands do not establish this complete
integration path.

ADR-038 deliberately defers answer-to-Context persistence and downstream regeneration to J03-B.
This proposal therefore verifies the existing resolution and readiness semantics only. It does
not claim that the answer becomes a new Context Source, Requirement or generated Scope content.

## Proposed contract

### Boundary

Use the isolated test-only orchestration pattern of 0077: a dedicated throwaway PostgreSQL
database, synthetic Persian fixtures, deterministic Fake Providers, existing Job/Outbox/Relay
delivery and actual `aria_worker` authority for AI runtime stages. Every workflow command is
explicitly issued by the harness. No production orchestration, public trigger, schema, runtime
policy or deployment change is introduced.

Real or paid Providers, customer data, Hosted activation, AI-04 runtime, automatic chaining,
answer-to-Context conversion, Requirement regeneration and K05 publication remain outside scope.

### Positive scenario

1. Establish Context Version N through the accepted AI-01 synthetic path. Bind AI-02 and AI-03
   to N and produce at least one eligible Requirement and a deterministic Critical Gap.
2. Attempt AI-05 through its existing explicit internal command and assert K02 blocks it before
   Provider invocation, with no new Scope Job, Outbox event, UsageRecord or Draft.
3. An authenticated test actor with active membership creates two synthetic questions for the
   target open Gap using the existing authorized Clarification Application command. Both
   questions must exist before either answer is recorded. Persist no question or resolution by
   direct SQL.
4. Record `provided_information` with a nonempty synthetic answer for the first question using
   the existing resolution command and an explicit idempotency key. Assert that this question is
   answered, its actor attribution is correct, the second question is open and the Gap remains
   open. K02 must still block AI-05.
5. Answer the second question through the same authorized command. Assert both questions are
   answered, exactly one immutable Resolution exists per question, and the Gap is `resolved`
   with a non-null `resolved_at`. If the fixture produces other blocking Gaps, resolve their
   questions through the same explicit command path; do not dismiss or mutate them in SQL.
6. Verify that Context Version N, Source/Version counts and existing Requirement revisions have
   not changed as a side effect of answering. Resolution is not answer ingestion.
7. Create a new explicit AI-05 command after resolution. Pin the now-resolved Gap revisions with
   the same Context Version N and eligible Context/Requirement revisions. Consume its existing
   Outbox/Worker path and atomically finalize one validated K01 Draft plus Job success.

### Replay, failure and isolation

- Same resolution key and input returns the same Resolution without a second audit row or state
  transition. Incompatible key reuse follows the existing `IDEMPOTENCY_CONFLICT` contract.
- Cross-tenant question/resolution attempts follow existing safe-not-found semantics and leave
  all state unchanged. Tenant authority comes from authenticated Application context.
- Reject an empty `provided_information` answer through existing validation; the Clarification
  and Gap remain unchanged.
- Terminal question/resolution mutation retains the existing invalid-state behavior. Do not
  introduce a new error code or exception contract.
- Duplicate AI-05 delivery remains a completed-job no-op with exactly one Draft and no extra
  Provider invocation or UsageRecord. A second generation command retains existing-Draft conflict.
- Changes to pinned input after AI-05 scheduling must follow ADR-062's
  `SCOPE_GENERATION_INPUT_CHANGED`, with no hidden repinning, Draft or Job success.
- Existing transactional rollback assertions remain applicable; the harness must not repair state
  by changing Gap, Job or Draft records directly.

### Observability and gate meaning

Reports contain only test identifiers, bounded state/counts, versions, outcomes and durations.
Negative leakage checks cover question/answer text as well as Context, Requirement, Gap and Scope
content, source references, prompts and raw Provider responses.

PASS means the controlled synthetic resolution-to-readiness-to-Scope integration works under
existing contracts. It does not establish answer semantic validity, answer inclusion in generated
Scope, human UX acceptance, real-model quality or the complete Hosted E2E-02 acceptance journey.

## Accepted decision

The owner approved and froze this limited interpretation of E2E-02 on 2026-09-29. Human answers
close the Gap under the unchanged ADR-038 rule only after all questions that already exist for
that Gap have been answered. The controlled sequence is therefore create Question 1, create
Question 2, answer Question 1 while the Gap stays open, then answer Question 2 and resolve the
Gap. Creating Question 2 after answering Question 1 is prohibited because it would test a
different, unapproved iterative-question lifecycle.

AI-05 subsequently uses the unchanged Context Version and Requirement revisions plus updated Gap
revisions. Incorporating answer meaning into Context/Requirements remains J03-B and requires its
own contract.

## Sources and traceability

| Requirement | Authority | Proposed evidence |
| --- | --- | --- |
| REQ-8201 | Sprint Backlog E2E-02; ADR-063 | Explicit synthetic Context-to-Clarification-to-Scope sequence |
| REQ-8202 | ADR-038/039 | Authorized questions, two human answers, immutable attributed resolutions and replay |
| REQ-8203 | ADR-042/062 | Block while questions remain; resolved Gap permits explicit Scope command |
| REQ-8204 | ADR-038 J03-B deferral | No Source/Context/Requirement mutation from answers |
| REQ-8205 | ADR-057/062/063 | Runtime authority, pinned revisions, atomic finalization, isolation and safe logs |

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — E2E-02 and Sprint acceptance; read 2026-09-29.
- [ADR-038](ADR-038-clarification-domain-api.md), [ADR-039](ADR-039-gap-inbox-review-contract.md),
  [ADR-042](ADR-042-scope-readiness-policy.md), [ADR-057](ADR-057-durable-outbox-delivery-runtime.md),
  [ADR-062](ADR-062-scope-generation-runtime-foundation.md),
  [ADR-063](ADR-063-controlled-synthetic-context-to-scope-integration.md) — read 2026-09-29.
