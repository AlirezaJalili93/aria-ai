# ADR-073 — Defer Real-Provider Integration Until the MVP Feature Cycle Is Complete

- Status: Accepted
- Date: 2026-10-03
- Decision owner: Product owner
- Supersedes: ADR-072 execution timing only
- Preserves: ADR-055, ADR-056 and ADR-069–072 technical and safety contracts

## Context

ADR-072 and increment 0086 produced the controlled, fail-closed harness for comparing the two
evaluation-only Provider candidates on synthetic, versioned fixtures. The repository now has the
manual command, immutable Price Version provisioning, isolated PostgreSQL preflight, strict
Prompt/Output-Schema package, Usage accounting, budget guard, safe evidence boundary and
human-review import contract.

The first explicitly authorized remote model preflight stopped safely at the OpenAI model check.
It performed no paid generation and database verification found zero evaluation Accounts and zero
Usage records. The Product owner then explicitly changed the delivery order: real OpenAI and
Gemini integration/evaluation will be resumed after the MVP feature cycle is complete, while
product development continues without those connections.

## Decision

- The executable 0086 harness and the evaluation-only adapters remain in the repository. They are
  dormant capabilities and are not removed or weakened.
- The controlled paid 120-call evaluation, human adjudication, Provider comparison and any
  Provider promotion are deferred until the MVP feature cycle is complete.
- Continued MVP development uses deterministic Fake Providers and synthetic data wherever an AI
  boundary must be exercised.
- No Primary or Fallback Provider is selected. Customer content, Hosted Provider execution and
  production Provider credentials remain prohibited.
- The 0086 development increment may close as an implementation and fail-closed-preflight PASS.
  This PASS does not mean that either model passed a quality, cost or latency gate.
- After the MVP feature cycle, a separate activation increment must resume ADR-072, re-verify
  current models and immutable Price Versions, run the controlled evaluation and complete the
  required human review before any promotion decision.

## Release semantics

This sequencing decision permits work on the remaining MVP domains, beginning with Client Sharing
and Approval. It does not waive the canonical AI Release Gate, Closed Beta Entry Gate or Product
AI Acceptance. Those gates remain non-PASS until real-Provider evaluation evidence exists.

Specifically:

```text
0086 implementation and local safety gates     = PASS
real-Provider quality/cost/latency evaluation  = DEFERRED
Provider promotion                             = NOT AUTHORIZED
customer content to a real Provider            = PROHIBITED
Hosted real-Provider activation                = PROHIBITED
Closed Beta / Production AI acceptance         = NOT PASS
```

## Consequences

- Product feature development is not blocked by Provider credentials or model availability.
- Synthetic runtime and end-to-end tests remain deterministic and cost-free.
- Model quality and real economics remain explicit product risks; no report may describe them as
  validated.
- Provider/model/pricing drift must be rechecked when the deferred evaluation resumes.

## Sources

- Product-owner instruction to skip OpenAI for now, continue the MVP development cycle and connect
  the Provider integrations after MVP completion, 2026-10-03.
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — Core Journey and Client Sharing & Approval; reread 2026-10-03.
- [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit) — stage gates and MVP execution sequence; reread 2026-10-03.
- [ADR-072](ADR-072-controlled-real-provider-quality-evaluation.md).

**Unapproved assumptions:** None
