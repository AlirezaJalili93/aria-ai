# Worker tasks

Task wrappers are introduced only after the durable queue ADR. A wrapper may deserialize a job reference, enforce idempotency, invoke an application workflow, update job state and emit safe telemetry; it cannot duplicate business logic.

