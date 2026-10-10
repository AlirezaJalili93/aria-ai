# ADR-063: Controlled Synthetic Context-to-Scope Integration Gate

- **Status:** Accepted / Frozen — owner approval received 2026-09-27
- **Date:** 2026-09-27
- **Candidate increment:** 0077-controlled-synthetic-context-to-scope-e2e
- **Extends:** ADR-059, ADR-060, ADR-061, ADR-062

## Context

The approved AI-01 controlled command E2E and the separate AI-02, AI-03 and AI-05
synthetic Worker foundations do not yet establish one Context-to-Scope integration gate.
The Sprint 1 Backlog and Test Strategy require critical journey coverage, while the
accepted runtime ADRs prohibit automatic workflow chaining, customer content, paid
Providers and hosted activation. A test harness must not be presented as the full
Login-to-Scope product acceptance journey.

## Accepted boundary

1. Add an **isolated, test-only** orchestration harness using the existing explicit
   commands. It may sequentially invoke AI-01, AI-02, AI-03 and AI-05, but must not
   add production chaining, a public trigger or a new deployable service.
2. Use a dedicated throwaway PostgreSQL test database, local queue/relay, deterministic
   Fake Providers and versioned synthetic Persian fixtures only. Refuse any non-test
   database before migration or state mutation. No real Provider credential, paid call,
   customer data or hosted execution is allowed.
3. AI-01 establishes Context Version N. Bind AI-02, AI-03 and AI-05 to the same
   tenant, Project and **exact N**; no execution-time selection of a later version
   or hidden repinning is permitted. Resolve each Job through the existing durable
   Outbox/Worker path. Assert that envelope
   fields remain `message_version`, `outbox_event_id` and `job_id`, without content.
4. Exercise the AI-03 Critical Gap gate before AI-05. The synthetic Fake Provider
   may produce Critical Gaps; the test must first prove that open Critical Gaps block
   Scope Generation. An explicit test actor may then use the **existing authorized
   Gap dismissal application command** to waive them. Direct DB/SQL Gap status
   mutation is prohibited. This demonstrates
   command wiring, not the semantic correctness of dismissing a real Gap.
5. After the explicit resolution, invoke AI-05 as a new internal command and verify
   one K01 Scope Draft, exact input pinning, Job success, and no duplicate committed
   effects on replay. Existing-Draft conflict must remain non-overwriting. K05 Scope
   Version publication is outside this proposed gate.
6. Negative checks must include tenant isolation, open-Critical blocking, incomplete
   or changed pinned input, duplicate delivery, rollback without partial Draft/Job
   success, and no sensitive fixture text in logs or Queue envelopes.
7. Report this only as a **controlled synthetic integration PASS/FAIL**. It cannot
   satisfy real-provider model-quality evaluation, hosted activation, public API,
   human UX, or the full Sprint 1 Login-to-Scope acceptance gate.

## Accepted decision

The owner approved this isolated, test-only 0077 gate on 2026-09-27 and clarified
that AI-01 first establishes Context Version N. All downstream jobs remain pinned
to N. The full negative path, including duplicate delivery, existing Draft,
changed pinned input and atomic rollback, is required for PASS. Production chaining,
public orchestration, customer data, real/paid Providers, hosted activation, K05
publication and Product AI acceptance remain outside this approval. This approval
does not authorize commit or push.

## Sources and traceability for proposal

| Requirement | Source | Proposed verification |
| --- | --- | --- |
| REQ-0077-01 | Sprint 1 Technical Backlog, E2E-01/02; Test Strategy critical journeys | Explicit isolated Context-to-Scope test path |
| REQ-0077-02 | ADR-059/060/061/062 | No automatic chaining, public trigger, paid/customer/hosted activation |
| REQ-0077-03 | ADR-042/062; approved J03/J04 Gap commands | Open Critical blocks; authorized explicit dismissal precedes AI-05 |
| REQ-0077-04 | ADR-057/060/061/062 | Durable delivery, pinned revisions, atomicity and replay assertions |

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — E2E stories; reread 2026-09-27.
- [Test Strategy & Test Case Master v1.0](https://docs.google.com/document/d/1ctrP7TTfaHrOPBB-sYIm0aruruTPov9t6MKUTtXg0Fk/edit) — critical journeys and isolation; reread 2026-09-27.
- [Sprint 1 Acceptance & Demo Plan](https://docs.google.com/document/d/1cNO4P5hBIzgQAvNVAnOdfI84IyTQj8UXxdN9GfGvb1Y/edit) — full product acceptance remains separate; reread 2026-09-27.
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-01/02/03/05 boundaries; reread 2026-09-27.
- [ADR-059](ADR-059-context-structuring-command-synthetic-e2e.md),
  [ADR-060](ADR-060-requirement-generation-runtime-foundation.md),
  [ADR-061](ADR-061-gap-detection-runtime-foundation.md),
  [ADR-062](ADR-062-scope-generation-runtime-foundation.md).

Implementation is authorized only within the accepted synthetic test boundary;
PASS requires execution against isolated PostgreSQL and the approved Worker path.
