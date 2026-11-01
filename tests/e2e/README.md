# End-to-end tests

Journey tests are introduced with executable vertical slices. Sprint 1's required path is Login → Project → Context → Structured Context → Requirements → Gaps → Internal Scope.

## 0077 controlled synthetic integration

`npm run test:context-to-scope-e2e` requires `TEST_DATABASE_URL` pointing to a
dedicated database named `aria_0077_test` (or `aria_0077_test_<suffix>`) and
`TEST_REDIS_URL` pointing to local Redis DB 15 on port 6379. The harness migrates
and **resets fixture tables in that dedicated database**, then uses a unique
per-Job queue that it consumes and deletes. Never point it at staging or a
database containing customer data.

AI-01 establishes Context Version N. The test then explicitly schedules AI-02,
AI-03 and AI-05 against N, proves the open Critical Gap blocks AI-05, and uses
the existing authorized Gap dismissal Application command before a new AI-05
command. The local Relay publishes identifier-only messages through Redis/Celery;
the synthetic Worker consumes each delivery, and duplicate delivery is checked.
The same runner executes dedicated PostgreSQL negative tests for pinned revisions,
rollback, existing Draft and tenant isolation. This is **not** production workflow
chaining, hosted activation, real-Provider quality evaluation or full Login-to-Scope
acceptance.

## 0078 controlled Requirement edit to Scope

`npm run test:requirement-edit-to-scope-e2e` uses the same dedicated local
`aria_0077_test...` PostgreSQL database and Redis DB 15 as the 0077 harness;
it **resets fixture tables** and must never target staging or customer data.
It first reruns the unchanged 0077 baseline and negative gates, then repeats
the synthetic journey with one AI-02 Requirement title edited through the
existing authorized Application command. The AI-05 Job must pin that exact
edited revision, and its Draft Requirements section must include the edited
title and Requirement ID. This test-only scenario does not authorize
production chaining, customer content, paid Providers or hosted activation.

## 0102 controlled Preview subgates

These PowerShell harnesses create their own disposable loopback Docker services and clean up
only their own containers/temp data. They do not use staging/customer databases or enable Hosted.

- `run-preview-authority-controlled.ps1` verifies reviewed SQL/helper authority under actual
  `aria_worker`; `-FullRegression` also runs the sequential complete PostgreSQL suites.
- `run-preview-queue-controlled.ps1` verifies adapter contracts and real Redis/Celery transport
  with a synthetic executor double, not SQL domain effects.
- `run-preview-joined-controlled.ps1` runs fixture-allocated and Application-command-backed
  PostgreSQL relay -> Redis -> Celery -> actual `aria_worker` -> verified private copy/finalization,
  across three project types. It also verifies explicit same-ID copy recovery and duplicate delivery
  without recopy. The separate API process resolves membership from DB and calls existing Publish/
  Issue/Revoke services; no raw capability enters argv/env/file/log or idempotency persistence.
  Command-backed cases also create a temporary loopback-only HTTP listener, verify HTML/CSS/SVG
  GET/HEAD and prove deterministic revoke-versus-in-flight-read semantics. No server diagnostics
  or bearer URLs are persisted; the listener and its request threads are closed after each case.
  `-BrowserGate` additionally executes three real 0100 bundle cases in disposable Chromium profiles,
  with real capability HTTP delivery and frozen isolation. A test-only corporate path recipe
  covers /services/design; original versioned fixtures stay unchanged. Profiles/history are
  removed; no screenshot, URL or raw CDP/console data is persisted. This is Local/Synthetic only.
  Command cases also race two same-key second Publish commands, reuse one ready Representation
  through another real Relay/Worker delivery, compare every Manifest file under two capabilities,
  and prove independent revocation without changing private files/source bytes.
  `-BrowserGate -BrowserCasesOnly` is a diagnostic three-case subset: it explicitly does not
  report a full joined-matrix PASS. Only the exact armed harness-local data download probe bypasses
  request interception so native Sandbox, rather than CDP, is the download-denial authority.

The joined harness uses explicit source/actor preparation. The command-backed cases inject a
trusted test subject, not a JWT. Reads use real controlled HTTP; management still uses the approved
internal Application commands. This is not production chaining, a management HTTP/JWT API,
full human/Production security or Hosted acceptance. Browser is evaluated only with `-BrowserGate`;
none of these subgates
alone marks all of 0102 complete. See the [current report](../../docs/development/0102-local-preview-publication-and-capability/test-report.md).

