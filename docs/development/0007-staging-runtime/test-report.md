# Test Report: 0007 Staging Runtime

- Increment ID: `0007-staging-runtime`
- Date: 2026-08-17
- [Development record](./development.md)

## Environment

- Local OS: Windows
- Hosted target: Vercel Web, Render API/Worker/Queue, Supabase PostgreSQL/Auth/Storage
- Branch: `agent/staging-runtime`
- Secret values: never recorded in this report

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-0701 | Build/Runtime | Build all three deployables with staging configuration contract | Web, API, and Worker build; staging startup rejects missing critical configuration |
| TC-0702 | API/Contract | Call the approved liveness endpoint | Stable non-sensitive 200 response matches OpenAPI contract |
| TC-0703 | API/Runtime | Call the approved readiness endpoint with valid and invalid runtime state | Ready returns 200; invalid/unready state returns 503 without leaking configuration |
| TC-0704 | Security/Config | Inspect frontend env allowlist, committed files, and secret placeholders | No backend/provider secret is bundled or committed; staging-only keys are classified |
| TC-0705 | Hosted smoke | Open staging Web URL and call hosted API health/readiness | Web and API are reachable over TLS and report the expected version/environment |
| TC-0706 | Isolation | Inspect staging Supabase and Queue bindings against production identifiers | Staging resources and credentials are independent; no production data or secret is referenced |
| TC-0707 | Deployment | Validate Render/Vercel configuration and rollback metadata | Deployment configuration is valid, gated by CI, and identifies the rollback artifact/commit |
| TC-0708 | Quality/Architecture | Run repository test and validation gates | Tests, build, architecture, documentation, and secret checks pass |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-0701 | Pending | Not executed | PENDING |
| TC-0702 | Pending | Not executed | PENDING |
| TC-0703 | Pending | Not executed | PENDING |
| TC-0704 | Pending | Not executed | PENDING |
| TC-0705 | Pending | Not executed | PENDING |
| TC-0706 | Pending | Not executed | PENDING |
| TC-0707 | Pending | Not executed | PENDING |
| TC-0708 | Pending | Not executed | PENDING |

## Final Status

**Final status:** PENDING
