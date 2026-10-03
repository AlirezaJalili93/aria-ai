# Durable Queue evaluation plan

- Status: Celery 5.6.3 selected in accepted ADR-015 and integrated into the Worker; S1-E03 partial
  Outbox Relay Contract is accepted in ADR-016 and S1-E04 Worker Idempotency Foundation in ADR-017;
  storage/transport execution policy remains deferred
- Source sync: 2026-09-05
- Sources: [Sprint 1 Backlog](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit), [Final Architecture](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit), [ADR-004](../adr/ADR-004-stack-and-repository-bootstrap.md), [ADR-013](../adr/ADR-013-jobs-outbox-persistence.md).

## Current evidence

PR #18 is open at `c706b178212ec33acfef8e7bafe11085f30e7d4b` (GitHub connector
readback, 2026-09-05). D02 persists durable work; the Worker still reports
`queue_adapter_configured=true` when the required Queue runtime configuration is present. End-to-end
task parsing is not implemented.

## Sequence

1. S1-E02: evaluate the documented Celery/Dramatiq/RQ candidates against the existing Redis-compatible
   staging backend, select an exact dependency version, and integrate the accepted Celery adapter with
   explicit runtime configuration.
2. S1-E03: implement the provider-neutral partial relay contract; demonstrate recovery after
   publication succeeds but marking the event published fails. Queue producer wiring remains deferred.
3. S1-E04: establish the provider-neutral Worker Idempotency Foundation and prove duplicate
   suppression through a recoverable repository fixture. PostgreSQL claim/lease, bounded execution,
   task handlers and artifact constraints remain deferred.
4. S1-F01/F02: lock the canonical text normalization contract and implement the provider-neutral
   parser boundary. Source Version persistence and the content-hash algorithm remain separate
   follow-up contracts.
5. S1-E05/D04: expose documented Job status and connect the Context Inbox to real processing state.

## Candidate evidence and decision boundary

[Upstash documents Celery integration](https://upstash.com/docs/redis/integrations/celery), but also
warns that idle polling consumes Redis commands. This makes idle-command measurement necessary
under the owner's free-service constraint. Compatibility documentation is not proof that the
existing account quota is sufficient.

[Celery documents worker-loss acknowledgement behavior](https://docs.celeryq.dev/en/main/userguide/configuration.html).
Late acknowledgement alone does not prove crash recovery; test forced worker termination and
bounded redelivery explicitly.

[Dramatiq documents Redis support and automatic retry](https://dramatiq.io/guide.html).
Its middleware defaults must not silently become Aria's approved retry contract.

Celery was evaluated first because the current hosting provider documents the integration. The
subsequent three-candidate evidence supported its selection in accepted ADR-015. That decision does
not authorize a paid plan, production deployment, runtime adapter or a new service.

## Required evidence

- Worker absent during publish: work survives and executes when the worker returns.
- Worker killed during execution: work is recoverable with no duplicate committed outcome.
- Duplicate publish/delivery: one business outcome remains.
- Broker unavailable: the committed Outbox event remains recoverable.
- Invalid tenant/project references: rejected without customer data in logs.
- Idle and active command usage: measured and checked against the actual staging plan.
- Application transaction ends before external broker IO.

## Decisions still open after framework selection

Visibility or lease duration, execution timeout, retry/backoff, exhausted-message handling and the
canonical text normalization rules require a documented decision. Celery 5.6.3 is selected by
ADR-015; no remaining implementation defaults are asserted by this plan.

## Evaluation preflight — 2026-09-05

The owner approved continuing the isolated Celery evaluation. No runtime dependency, paid service
or deployment has been changed. Candidate documentation currently identifies Celery 5.6.3; package
resolution, dependency audit and pinning remain part of the experiment setup.

| Check | Observed result | Status |
|---|---|---|
| Local Docker CLI | Installed; owner account reports Client 29.5.2 | PASS |
| Linux Docker engine | Owner account reports Server 29.5.2, Docker Desktop Linux, WSL2 kernel | PASS |
| WSL inventory | Owner account reports docker-desktop distribution; default version 2 | PASS |
| Background Docker Desktop launch | Owner account service is running | PASS |
| Host startup log | Prior startup issue superseded by successful owner-account engine readback | PASS |
| Worker-absent delivery, forced restart, duplicate delivery | No Linux runtime available; not executed | NOT RUN |
| Idle/active command measurement and hosted quota comparison | Not executed | NOT RUN |

Commands: `docker info --format '{{.ServerVersion}}'`, `docker image ls`, `wsl --list --quiet`,
`wsl --status`, a hidden Docker Desktop launch, and bounded reads of Docker's host startup logs.
The startup entry at `2026-09-05T05:40:22Z` reports that installation registry key
`SOFTWARE\Docker Inc.\Docker Desktop` cannot be found. This establishes a local installation/startup
problem; it does not establish a Celery or Redis failure.

[Celery explicitly does not support Windows](https://docs.celeryq.dev/en/stable/faq.html#windows).
A native Windows run would therefore not provide the intended Linux worker-recovery evidence.
[Redis transport documentation](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)
also requires testing visibility-timeout recovery; successful publication alone is insufficient.

Next prerequisite: run the isolated infrastructure compose stack and capture health/readiness output
from the owner account. The Codex sandbox cannot use that account's Docker named pipe, so commands
must be run in the owner's terminal. No production queue writes or paid plan changes are authorized.
Experiment remains pending; no S1-E02 completion or framework adoption is claimed.

## Local infrastructure verification — 2026-09-05

The owner ran the approved local Compose stack from the authenticated Windows account after the
Docker Desktop repair. `postgres:16-alpine` and `redis:7-alpine` pulled successfully and both
services reported `healthy`. Authenticated Redis `PING` returned `PONG`; PostgreSQL
`pg_isready -U aria_local -d aria_local` returned `accepting connections`. This proves the local
dependencies are reachable; it does not select a queue framework or prove worker recovery semantics.

Repository verification in the isolated worktree completed with `npm test` (6 record tests, 63
contract tests, 18 Web tests, 143 API tests passed with 33 documented skips, and 16 Worker tests)
and `npm run validate` (22 checks passed). Pytest emitted only cache-permission/deprecation
warnings; no test failed. The queue evaluation remains pending the documented candidate experiment.

## Celery candidate result — 2026-09-05

The owner executed the isolated Celery 5.6.3 Compose harness on Docker Desktop's WSL2 Linux engine.
Observed results:

- A message published while no Worker existed remained available and completed after Worker startup
  (`attempts=1`, `outcomes=1`).
- A Worker was force-killed after task start and restarted after the five-second experiment
  visibility window. The task was redelivered (`attempts=2`) and the idempotent probe retained one
  committed outcome (`outcomes=1`).
- Publishing the same business probe twice produced two executions and one committed outcome,
  confirming that at-least-once delivery requires an application idempotency guard.
- A ten-second idle Worker observation increased Redis `total_commands_processed` by 36. This local
  measurement is evidence only; it is not a hosted quota or cost projection.

`QUEUE_EVALUATION_RESULT=PASS` was emitted. This establishes that Celery can satisfy the tested local
durability behavior with the explicit candidate configuration. It does not compare Dramatiq/RQ,
prove hosted Upstash quota suitability, implement Outbox recovery, or authorize runtime adoption.

## Candidate comparison preparation — 2026-09-05

The documented remaining candidates are locked in isolated projects as Dramatiq 2.2.1 and RQ
2.12.0. Both receive the same worker-absent, forced-loss, duplicate-outcome, delayed-delivery and
idle-command probes. RQ also receives an ordinary exception-retry probe because its retry contract
is opt-in. RQ explicitly uses `JSONSerializer`; its documented default `pickle` serializer is not
accepted for this evaluation.

Dramatiq's five-second Redis heartbeat and RQ's one-second maintenance/monitoring intervals plus
16-second Worker TTL are short experiment fixtures. RQ's actual abandoned-job lease remains
approximately 61 seconds; the short Worker TTL only bounds the idle dequeue block so maintenance
can run after lease expiry. The harness does not edit Redis time or registry scores.

## Comparative result — 2026-09-05

| Candidate | Worker absent | Forced loss | Duplicate outcome | Delayed delivery | Idle commands / 10s |
|---|---:|---:|---:|---:|---:|
| Celery 5.6.3 | PASS | PASS (`attempts=2`, `outcomes=1`) | PASS | Not measured in 0026 | 36 |
| Dramatiq 2.2.1 | PASS | PASS (`attempts=2`, `outcomes=1`) | PASS | PASS | 141 |
| RQ 2.12.0 | PASS | PASS (`attempts=2`, `outcomes=1`) | PASS | PASS | 249 |

RQ ordinary exception retry also passed with two attempts and one outcome. Its first forced-loss run
timed out because the replacement Worker performed registry maintenance at startup and then entered
its default long idle dequeue block. Setting a 16-second experiment Worker TTL bounded that block;
the clean rerun recovered after the native lease expired without changing registry scores or time.

ADR-015 selected Celery 5.6.3 because all mandatory tested behavior passed, it recorded the lowest
local idle command delta, and the current Redis-compatible provider documents its integration. The
owner accepted that framework/version decision on 2026-09-05. The decision does not authorize
hosted capacity claims or unapproved retry/timeout values. Increment 0028 now implements the
accepted framework boundary; execution timeout, retry/backoff and exhausted-message behavior remain
outside that implementation.

## Repair attempts

- The existing signed all-users installer (`4.75.0.227598`) was run against the existing
  `C:\Program Files\Docker\Docker` installation with `--backend=wsl-2` and
  `--no-windows-containers`; it returned exit code `-5` and the service remained stopped.
- The same signed installer package was run in documented per-user mode with
  `--user --accept-license --backend=wsl-2 --no-windows-containers`; it also returned `-5` and did
  not create a per-user installation.
- The owner subsequently completed the host repair and supplied an authenticated readback showing
  the Docker Desktop server, Compose 5.1.3 and WSL2 are operational. The prior installer failure
  is retained as history; no uninstall, data-volume deletion, registry edit or WSL distribution
  deletion was performed by the repository workflow.
