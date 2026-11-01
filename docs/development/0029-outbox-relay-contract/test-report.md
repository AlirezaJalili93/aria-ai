# Test Report: 0029 Outbox Relay Contract

[Development record](./development.md)

## Environment

- Windows 11 host, repository worktree `staging-migrations`
- Python 3.12 project environments managed by `uv`
- Node.js/npm repository toolchain
- No external Queue provider or hosted producer was used; the approved partial contract uses fakes
  for the publisher and PostgreSQL unit-of-work boundary.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-2901 | Contract | Inspect Queue boundary and deferred decisions | Application exposes only `QueuePublisher`; no Celery/Redis/Kombu wiring exists |
| TC-2902 | Unit | Publish succeeds, then mark transaction commits | Publisher is called before `mark_published`; event becomes published after commit |
| TC-2903 | Recovery | Publish succeeds but mark fails | Exception is surfaced, commit is not recorded, durable event remains pending |
| TC-2904 | Unit | Republish the same pending event | Same stable Outbox event ID is published again and `outbox.republished` is emitted |
| TC-2905 | Observability | Inspect relay lifecycle logs | Required lifecycle events contain safe IDs/attempt/duration and never payload data |
| TC-2906 | API regression | Run all API tests | Existing Jobs, Context and repository behavior remains green |
| TC-2907 | Quality | Run lint and strict type checking | Ruff and mypy pass |
| TC-2908 | Architecture | Run contract suite and architecture validation | Contract suite and all architecture checks pass |
| TC-2909 | Repository gate | Run full npm test | Records, contracts, Web, API and Worker suites pass |

## Execution Results

| ID | Command | Actual | Status |
|---|---|---|---|
| TC-2901 | `node --test scripts/test/outbox-relay-contract.test.js` | 3 contract tests passed | PASS |
| TC-2902–TC-2905 | `node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests/test_outbox_relay.py` | 3 relay tests passed | PASS |
| TC-2906 | `node scripts/run-uv.mjs --project apps/api run pytest -q apps/api/tests` | 146 passed, 33 skipped | PASS |
| TC-2907 | `npm run lint:api`; `npm run typecheck:api` | Ruff passed; mypy reported no issues in 79 files | PASS |
| TC-2908 | `npm run test:ci` | 81 contract/security tests passed; `npm run validate` passed 22/22 | PASS |
| TC-2909 | `npm test` | 6 record tests, 81 contracts, 18 Web, 146 API/33 skipped, 22 Worker passed | PASS |
| TC-2910 | `npm run lint`; `npm run typecheck`; `npm run build` | Web/API/Worker lint and type checks passed; Web/API/Worker builds passed | PASS |

## Notes

- Test output contained only existing non-blocking warnings: Windows pytest cache permissions and the
  existing Starlette/httpx deprecation notice.
- No Docker or hosted Queue runtime evidence is claimed because producer transport and scheduling are
  explicitly deferred by ADR-016.

## Final Status

**Final status:** PASS
