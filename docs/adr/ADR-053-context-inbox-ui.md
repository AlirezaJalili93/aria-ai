# ADR-053 — Context Inbox UI

- Status: Accepted
- Date: 2026-09-19
- Decision owner: Product and Engineering
- Supersedes: the SCR-09 implication that URL and Internal Note ingestion are part of Sprint 1

## Context

S1-D04 needs a user-facing inbox for the approved text-paste and private TXT ingestion contracts. The existing `/projects/{projectId}/context` route is the structured Context review surface and keeps that responsibility. The backend exposes tenant-scoped Source list/detail, logical archive, explicit parser retry, and safe status projections.

## Decision

- The Inbox route is `/projects/{projectId}/context/sources`; `/projects/{projectId}/context` remains Structured Context.
- Internal navigation is labelled `منابع` and `زمینه ساختاریافته`.
- Sprint 1 supports pasted text and TXT upload only. URL and Internal Note are excluded.
- The backend returns `can_archive`; the UI never infers archive permission from role or creator metadata. The archive endpoint still authorizes independently.
- `NEXT_PUBLIC_TXT_UPLOAD_ENABLED` defaults to false and only controls UI exposure. Backend `TXT_UPLOAD_ENABLED` remains authoritative.
- Polling runs every five seconds only while a loaded Source has a latest Job in `queued` or `running`; it pauses while the document is hidden, stops at terminal state, and never overlaps requests. Manual refresh remains available.
- Retry is shown only when the backend returns `retryable=true`. Archive requires confirmation.
- Pagination uses Load More. No synthetic progress percentage or Storage internals are displayed.
- `can_archive`, `retryable`, and the UI flag retain only their explicit meanings.

## Consequences

The UI remains a projection of server-owned authorization and workflow state. It can deploy fail-closed before TXT upload exposure is enabled. Source creation and job processing remain separate; continuous scheduling stays outside this decision.
