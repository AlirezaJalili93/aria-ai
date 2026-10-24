# ADR-070 — AI-01 Durable Checkpoint Integration Gate

- Status: Accepted
- Date: 2026-09-30
- Decision owner: Product and Engineering
- Extends: ADR-058, ADR-065 and ADR-069

## Context

ADR-069 created a provider-neutral durable Attempt/checkpoint boundary but deliberately did not
compose it into a Workflow. AI-01 previously recovered a failed Domain commit by invoking its Fake
Provider again. That was safe only for the controlled synthetic foundation and cannot establish the
one-invocation/one-Usage invariant required before any future paid or customer-data activation.

## Decision

0084 composes ADR-069 into AI-01 only, using the deterministic Fake Provider and synthetic data.
The integration is exactly one attempt: `retry_no=0`, `repair_no=0`, technical retry, semantic
repair and fallback are disabled, and the maximum Provider invocation count is one. This does not
supersede the general bounded policy in ADR-056/0069; multi-attempt checkpoint recovery remains a
separate contract.

### Identity and pinned input

The Worker generates `provider_attempt_id`, persists `started`, passes that ID to the Fake Provider
and requires the response to carry the same ID. The AI-01 input fingerprint is canonical SHA-256
over deterministically ordered Source/Version identities, version numbers, content hashes and the
Workflow, Prompt and output-schema versions. Recovery never selects `latest` again. A newer Source
or Version is irrelevant; mutation or loss of pinned identity/integrity fails closed.

### Versioned checkpoint codec

`context_structuring_checkpoint_v1` stores only exact input snapshot identities and persistence-
bearing candidate fields: item type, content, source references and confidence.
`rationale_short`, Source text, prompts and raw Provider responses are excluded. Decode is strict
and is followed by schema, business, unsupported-claim and provenance validation.

### Recovery and finalization

After a successful invocation and deterministic validation, the normalized checkpoint and its one
UsageRecord commit atomically. `result_ready` recovery decodes and revalidates the same result and
does not invoke the Provider or append Usage again.

Context Items, Project Context Version advancement, the same Job's success and checkpoint
transition to `finalized` commit in one transaction. Payload removal occurs only in that
transaction; the non-content result hash remains. Any failed commit rolls back all four effects and
leaves `result_ready` plus payload available for recovery.

Invalid identity, fingerprint, hash, codec or payload fails with
`AI_INVOCATION_CHECKPOINT_INVALID`, `retryable=false`, without Provider re-invocation. An ambiguous
`started` Attempt uses `AI_INVOCATION_OUTCOME_UNKNOWN` from ADR-069. No zero Usage is fabricated.

### Activation and security boundary

The integration is exercised only in the isolated controlled test with the actual `aria_worker`
principal. RLS and cross-Tenant requirements apply to the checkpoint/Job path; 0084 does not
redesign the shared Worker's pre-existing raw SELECT policy. Hosted composition, real Providers,
customer content, paid calls and public activation remain prohibited.

## Consequences

- One actual AI-01 invocation produces exactly one durable Attempt and UsageRecord.
- A crash after `result_ready` can finish the same Job without semantic or cost duplication.
- AI-01's legacy direct and Coordinator-managed paths retain their existing behavior.
- Semantic Repair, Technical Retry and Fallback cannot use this integration until a later
  multi-attempt contract is approved.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), AI-01, Usage, E2E and recovery gates; reread 2026-09-30.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit), §§3, 6, 19–22 and 27–33; reread directly from Canonical Drive 2026-09-30.
- Owner-approved frozen `0084 — AI-01 Durable Checkpoint Integration Gate` contract,
  2026-09-30.

**Unapproved assumptions:** None
