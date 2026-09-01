# ADR-011: Pre-tenant Account Discovery and Selection

- **Status:** Accepted
- **Date:** 2026-09-01
- **Required before:** S1-C02 — Project API
- **Related:** ADR-009 pre-tenant Account Bootstrap command

## Context

Project routes require `X-Account-ID`, while the Bootstrap command intentionally returns no Account
data and must not become a hidden `/me` query. A browser session therefore needs a distinct,
read-only way to discover the Accounts in which its authenticated identity has operational access.
Bootstrap and discovery have different command/query responsibilities.

## Decision

- Account discovery is a separate authenticated pre-tenant query:
  `GET /api/v1/account-contexts`.
- It requires the existing Bearer JWT verification dependency and does not accept
  `X-Account-ID`.
- It returns only active Memberships for the authenticated identity.
- Each item exposes only the fields already approved for selection: `account_id` and `role`.
- Zero items means no active Account context. One item may be selected automatically. More than one
  item requires explicit selection before a tenant-scoped request is sent.
- The selected `account_id` is transported on subsequent tenant routes through the already accepted
  `X-Account-ID` contract and is authorized again server-side.
- The query performs no Bootstrap or mutation and returns no Profile, Email, external subject,
  Membership status, preference or token data.
- No Account display-name field or multi-Account selection UI is introduced until a separate
  product requirement defines its label and UX contract.

## Consequences

Bootstrap remains a command with an empty response. Tenant selection becomes explicit and cannot
be inferred from a Project or from client-controlled claims. S1-C02 may depend on this query but
must not invent additional response fields. A multiple-Account UI remains outside scope until its
display contract is approved.

## Rejected

- Return Account data from `POST /api/v1/auth/bootstrap`: mixes command and query responsibilities.
- Read Accounts directly from Supabase in the browser: bypasses the API authorization boundary.
- Trust an Account identifier stored only in the client: does not prove current active Membership.
- Add an undocumented Account name: introduces a new data field and synchronization contract.

## Sources

- S1-B04 approved Tenant Context contract
- S1-B05 approved Bootstrap flow and ADR-009
- Access Control Matrix v1.0
- Owner-accepted architecture-hardening sequence dated 2026-09-01
