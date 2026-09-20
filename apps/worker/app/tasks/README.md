# Worker tasks

S1-E04 provides the provider-neutral `JobExecutionGuard` and execution coordinator foundation.
Increment 0064 supplies the approved controlled TXT Parser path: an exact versioned message is
validated, PostgreSQL remains authoritative, and a PostgreSQL advisory lock suppresses concurrent
execution. Automatic retry is disabled. Queue ACK/requeue policy, retry/backoff policy and
artifact-specific constraints remain deferred until separately approved.

S1-F01/F02 provides the provider-neutral `TextParser` boundary and deterministic
`CanonicalTextParser`. Increment 0064 adds Source Version persistence, strict private TXT reread,
lowercase SHA-256 canonical hashing and atomic Parser finalization.

Hosted automatic processing remains disabled: no Continuous Outbox Relay Scheduler, cadence,
claim/lease loop, periodic task or Celery Parser task name is registered. The controlled runner
accepts one explicitly supplied message for verification. Queue producer/task registration remains
deferred until its own contract is approved.

