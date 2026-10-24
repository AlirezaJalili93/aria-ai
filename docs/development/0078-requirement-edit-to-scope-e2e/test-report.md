# Test Report: 0078 Requirement Edit to Scope E2E

- **Status:** PASS — isolated synthetic Requirement-edit-to-Scope gate
- **Increment ID:** `0078-requirement-edit-to-scope-e2e`
- [Development record](./development.md)

## Environment

Dedicated local `aria_0077_test` PostgreSQL database and Redis DB 15, actual
`aria_worker` runtime role, deterministic Fake Providers, and versioned
synthetic Persian fixtures. The existing entry-point guard rejects other
database names before migration or fixture reset.

## Test Cases and Results

| ID | Requirement | Expected result | Actual | Status |
| --- | --- | --- | --- | --- |
| TC-7801 | REQ-7801 | Authorized CAS edit persists one Requirement revision with same ID and Context Version; stale edit fails | Existing `RequirementCrudService.update` persisted the edit and advanced `updated_at`; stale CAS raised `RequirementVersionConflict` | PASS |
| TC-7802 | REQ-7802 | AI-05 pins edited revision; Draft Requirements section contains edited text and ID, not original text | Job `payload_ref` matched the edited ID/timestamp; Draft section and trace matched the edited Requirement | PASS |
| TC-7803 | REQ-7803 | New controlled scenario and unchanged 0077 baseline both pass under `aria_worker` | `CONTROLLED_0077_E2E=PASS`, `CONTROLLED_0077_NEGATIVE_GATE=PASS`, `CONTROLLED_0078_E2E=PASS` | PASS |
| TC-7804 | REQ-7804 | No customer/paid/hosted path and no fixture text in logs or Queue payload | Test-only Fake Providers; API/Worker leakage checks and identifier-only Queue assertion passed | PASS |
| TC-7805 | Repository gate | `npm test`, `npm run validate`, lint and typecheck pass | Full tests, lint, typecheck and architecture/development-record validation passed | PASS |

## Execution Results

- `npm run test:requirement-edit-to-scope-e2e`: PASS after final leakage-test
  refinement. The baseline ran 4 API and 9 Worker PostgreSQL cases, all PASS;
  the edit-specific synthetic journey then passed under `aria_worker`.
- `npm test`: PASS; API 608 passed and 1 hosted-only skipped; Worker 188
  passed/0 skipped; Node, Web and Eval suites passed.
- `npm run lint`, `npm run typecheck`, focused Ruff and Python compilation for
  both controlled E2E scripts: PASS.
- `npm run validate`: PASS after both Markdown records were finalized.
- One hosted-only API test remains skipped because the hosted upload-security
  environment was not enabled. It is not counted as PASS or as 0078 evidence.

## Final Status

**Final status:** PASS for this isolated synthetic regression gate. It proves
that the persisted human Requirement edit reaches AI-05's pinned input and
Scope Draft output through the existing runtime. It does not prove real-model
quality, customer-data readiness, hosted activation, public orchestration or
the full Sprint 1 Login-to-Scope acceptance journey.
