# ADR-038: Clarification Question and Human Resolution Contract

- **Status:** Accepted for S1-J03-A — owner approval received 2026-09-09
- **Date:** 2026-09-09
- **Story:** S1-J03-A — Clarification Domain and API
- **Supersedes:** the single-record Clarification/answer shape in the current Data Dictionary and
  the combined clarification-answer endpoint in the current API Contract
- **Later refinement:** ADR-039 supersedes only the Gap dismissal endpoint and its client-CAS
  semantics; all other J03-A decisions remain accepted.

## Context

The approved sources require human-controlled Gap resolution and identify AI-04 as question
generation, but they do not define a complete multi-question state machine, auditable human
resolution model, or separate command endpoints. The owner therefore approved this ADR as a new
canonical, superseding Sprint 1 contract. J03-B remains intentionally deferred.

## Decision

### Data model

`clarifications` stores the question identity and lifecycle: tenant and Gap keys, normalized
`question_text`, `open|answered|ignored`, `ai|user|system` creator metadata, and timestamps. A
user-created question requires `created_by`. Only `open` questions are editable.

`clarification_resolutions` stores the single terminal human action. Its resolution type is
`provided_information|internal_decision|accepted_assumption|ignored`; author type is only
`user|client`. `actor_id` is always the authenticated internal Profile. A client-attributed answer
may have `author_id=NULL`; a user-attributed answer uses the authenticated actor Profile. A unique
constraint on `clarification_id` makes the resolution authoritative and immutable in J03-A.

Provided information and internal decisions require non-empty `answer_text`. Accepted assumptions
and ignored actions require `answer_text=NULL`. No AI or system actor can create a terminal
resolution through the public API.

All parent deletion actions are `RESTRICT`. Composite foreign keys enforce exact Account/Project/
Gap/Clarification consistency. RLS is enabled as defense in depth and direct privileges are
revoked from `PUBLIC`, `anon`, and `authenticated`; the FastAPI service retains independent tenant
authorization. Foreign-key and tenant query paths are indexed, including a partial unique index
over normalized open questions.

### Deterministic text and duplicate policy

Question text and answer text use the approved deterministic text normalization contract: newline
normalization, Unicode NFC, horizontal space normalization and document-edge trimming while
preserving Persian ZWNJ/ZWJ and internal blank lines. For the same tenant-scoped Gap, identical
normalized `question_text` with `status=open` is rejected as `DUPLICATE_CLARIFICATION`. Semantic
deduplication is not performed.

### State machine

- `provided_information`, `internal_decision`, and `accepted_assumption` change only the target
  Clarification from `open` to `answered`.
- `ignored` changes only the target Clarification from `open` to `ignored`.
- After that transition, a deterministic evaluator resolves the open Gap and sets `resolved_at`
  only when no `open` Clarification remains.
- Ignoring a Clarification never dismisses its Gap.
- Gap dismissal is a separate explicit human command, changes only an open Gap to `dismissed`,
  keeps `resolved_at=NULL`, and does not mutate its Clarifications.

All state changes lock the Gap row first and then the Clarification, preserving a consistent lock
order. Question edits use `expected_updated_at` compare-and-swap. ADR-039 supersedes dismissal CAS
with a separate idempotent command. Terminal Clarifications and terminal Gaps remain immutable.

### API commands

- `POST /api/v1/projects/{project_id}/gaps/{gap_id}/clarifications` creates a question.
- `PATCH /api/v1/projects/{project_id}/gaps/{gap_id}/clarifications/{clarification_id}` edits an
  open question with `question_text` and `expected_updated_at`.
- `POST /api/v1/projects/{project_id}/gaps/{gap_id}/clarifications/{clarification_id}/resolutions`
  registers the one terminal Resolution.
- Per ADR-039, `POST /api/v1/projects/{project_id}/gaps/{gap_id}/dismiss` has no body, requires
  `Idempotency-Key`, and explicitly dismisses an open Gap.

Question creation, Resolution creation, and Gap dismissal require `Idempotency-Key` and use the
existing 24-hour tenant/actor/route idempotency record. Replays return the original outcome; key
reuse with different input returns `409 IDEMPOTENCY_CONFLICT`. Missing and cross-tenant resources
are indistinguishable as `404 RESOURCE_NOT_FOUND`.

### AI-04 boundary and observability

J03-A defines only a provider-neutral `ClarificationQuestionGenerator` port and a deterministic
Fake implementation in contract tests. Provider SDKs, model names, runtime routing and real-model
quality claims remain absent.

Allowed structured events are `clarification.created`, `clarification.edited`,
`clarification.answered`, `clarification.ignored`, `clarification.version_conflict`,
`clarification.duplicate_rejected`, `gap.resolved`, and `gap.dismissed`, plus safe operational
failure/security events. Logs may contain IDs, closed vocabulary metadata, correlation fields and
duration; they must not contain question/answer text, Gap explanations, Context/Requirement
content, Source References, raw AI output, prompts, or client-identifying free text.

## Consequences

- Multi-question Gaps cannot close prematurely when only one question becomes terminal.
- Resolution attribution distinguishes content author from authenticated recording actor.
- Question and answer history cannot be physically cascaded away or silently overwritten.
- The API does not yet turn answers into Context history or regenerate downstream artifacts.

## Deferred to J03-B

- Semantic answer validity and semantic question deduplication.
- Answer-to-Context Source/Version persistence and Context version advancement.
- Requirement update or regeneration after an answer.
- Full AI-04 real-provider quality evaluation and thresholds.
- Independent guest/client identity and versioned answer correction.

## Sources

- [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit) — S1-J03; read 2026-09-09
- [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit) — human-in-the-loop Gap resolution; read 2026-09-09
- [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit) — Clarification baseline; read 2026-09-09
- [AI Workflow Specification v1.0](https://docs.google.com/document/d/1a2sOibUb5C-JP1-H1UKzDqIgreve9v5RSro_y2nOXTo/edit) — AI-04 and human resolution; read 2026-09-09
- [Backend API Contract v1.0](https://docs.google.com/document/d/1nTCwyIc6pW3yPpdhkRgIvEnw9EOs66-JEj05_6iBxmQ/edit) — object authorization and superseded combined endpoint; read 2026-09-09
- Owner-approved J03-A frozen contract and refinements dated 2026-09-09.
