# ADR-078 — Public Scope Change Request

- **Status:** Accepted
- **Date:** 2026-10-05
- **Increment:** `0091-public-scope-change-request`

## Context

The canonical PRD and API contract allow a Guest with a valid Share capability to either approve an
exact immutable Scope Version or request changes to it. The older Data Dictionary represented both
outcomes through an `approval_type` field, while ADR-077 and the implemented Approval aggregate make
Approval a final immutable consent record. Combining the two outcomes would weaken their distinct
semantics and audit trails.

## Decision

- Persist Change Requests in an independent immutable `scope_change_requests` aggregate.
- Use `POST /api/v1/public/scope-shares/request-changes`; the capability token appears only in the
  exact JSON body and `Idempotency-Key` is required.
- Normalize `guest_name` exactly as ADR-077. Normalize `comment` using Unicode NFC, CRLF/CR to LF and
  whole-document trim. Preserve internal lines and whitespace. Permit 1–4000 characters after
  normalization; prohibit NUL and C0/C1 controls except the canonical LF newline.
- A Scope Version has exactly one terminal decision:
  `awaiting_approval → approved|changes_requested`. Approval and Change Request repositories lock
  the same Scope Version row and use a compare-and-set transition inside their transaction.
- Persist the exact `version_no` and `version_hash` on the Change Request. Neither the hash nor the
  comment is exposed in the public response.
- First success returns 201. Same-key/same-command replay returns the original business result with
  200 and `meta.replayed=true`; changed semantics return `IDEMPOTENCY_CONFLICT`.
- A different command after a terminal decision returns `SCOPE_ALREADY_APPROVED` or
  `SCOPE_CHANGES_ALREADY_REQUESTED` according to the committed winner. Invalid, malformed, expired,
  revoked or superseded capabilities remain outward-safe `RESOURCE_NOT_FOUND`.
- Project status, Scope Draft, Share-Link lifecycle and existing historical resolve/view behavior
  remain unchanged. No new Scope Version or regeneration is started automatically.
- Logs, metrics, traces and analytics exclude comment, guest name, raw token, token hash, version
  hash and Scope content.

The older combined `scope_approvals.approval_type=changes_requested` persistence shape is superseded
for this implementation. `scope_approvals` continues to represent only an actual Approval.

## Consequences

- Approval-vs-Change races serialize on the immutable Scope Version identity and only one terminal
  transition can commit.
- The later authenticated revision workflow must consume the Change Request explicitly and create a
  new Scope Version under a separate contract.
- Public resolve may still display a historical immutable snapshot; decision eligibility is checked
  independently by the command.

## Sources

- PRD — Aria AI MVP v1.0, FR-08-05/07 and E2E-03; synchronized 2026-10-05.
- API Contract Specification v1.0, public Scope Change Request; synchronized 2026-10-05.
- Detailed Data Dictionary v1.0, Scope Version/Approval baseline; synchronized 2026-10-05.
- Test Strategy & Test Case Master v1.0, TC-APR-003/005 and E2E-05; synchronized 2026-10-05.
- Owner-approved frozen 0091 contract, 2026-10-05.

**Unapproved assumptions:** None
