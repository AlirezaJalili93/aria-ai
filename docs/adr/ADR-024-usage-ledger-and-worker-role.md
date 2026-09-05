# ADR-024: Append-Only Usage Ledger and Worker-Only Database Authority

- Status: Accepted
- Date: 2026-09-05

## Context

The Detailed Data Dictionary defines `usage_records` as the Financial/AI usage Source of Truth.
The AI Workflow and FinOps documents require traceability across the Job, Gateway, prompt/workflow
versions and provider outcome. Older documents use `attempt_no` and couple Usage creation to a
provider-price table, while the approved S1-G05 contract selects `retry_no`, tightens
`prompt_version` and `correlation_id` to non-null, and defers the provider-price table to S1-G06.

Supabase grants and PostgreSQL RLS are independent controls. Revoking Data API roles alone does not
define a safe direct-database runtime identity, while an unrestricted service/superuser credential
would bypass the intended Ledger boundary.

## Decision

- `usage_records` is the append-only Usage Ledger defined by the S1-G05 field, type, nullability,
  precision, status and non-negative constraint contract.
- `retry_no` is canonical and supersedes the older `attempt_no` vocabulary.
- `prompt_version` and `correlation_id` are required.
- `estimated_cost` has no default. A real zero must be supplied explicitly by the caller.
- `provider` and `model` are recorded data. Domain/Application code does not branch on a provider.
- The Application boundary exposes only `UsageLedger.append(record)`; no raw read/update/delete
  port or public endpoint is added.
- Physical runtime role `aria_worker` is the only ordinary runtime role granted direct `INSERT` on
  `usage_records`. It is explicitly non-superuser and non-`BYPASSRLS`, receives no table `SELECT`,
  `UPDATE` or `DELETE`, and has a single insert RLS policy.
- `anon` and `authenticated` receive no privilege. If `aria_api` exists, its privileges on the
  Ledger are revoked. S1-G05 does not create or provision the broader API database role.
- A database trigger rejects every `UPDATE` and `DELETE`, including owner-level ordinary mutation.
- Account, Project and Job foreign keys use `ON DELETE RESTRICT`. Null Project/Job means the link
  was absent at record creation, not erased later.
- `aria_worker` is a durable runtime principal. Downgrade removes the G05 policy/grant/table but
  retains the role so rollback cannot delete a pre-existing or externally credentialed principal.
- Logical M009 is delivered incrementally: S1-G05 adds `usage_records`; the provider-price table,
  pricing FK/catalog and price-selection logic remain deferred to S1-G06.

## Consequences

- Worker execution can append authoritative Usage without granting raw Ledger reads or mutation.
- API, Data API and browser identities cannot write the Ledger directly.
- Hard-deleting an Account, Project or Job with historical Usage is blocked; a future retention or
  legal workflow must resolve that history explicitly.
- Runtime password creation/rotation and secret distribution stay outside migrations. No password
  is stored in the repository.
- No paid Provider is integrated by this decision; G02/G03 and G06 remain deferred.

