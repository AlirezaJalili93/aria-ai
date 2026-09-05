# Worker tasks

S1-E04 now provides the provider-neutral `JobExecutionGuard` and execution coordinator foundation.
They suppress `already_in_progress` and `already_completed` duplicate deliveries and emit safe
telemetry. Business task wrappers, PostgreSQL claim/lock implementation, Job lifecycle transitions,
artifact-specific constraints, timeout/retry/backoff and Celery ACK/requeue behavior remain deferred
until their explicit contracts are approved. A future wrapper may deserialize a job reference, invoke
an application workflow, update Job state and emit safe telemetry; it cannot duplicate business logic
or rely on a Celery result backend.

S1-F01/F02 now provides the provider-neutral `TextParser` boundary and deterministic
`CanonicalTextParser`. Queue task registration, Source Version persistence, content-hash algorithm,
metadata schema and Job state transitions remain separate contracts.

