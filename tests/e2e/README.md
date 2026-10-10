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

