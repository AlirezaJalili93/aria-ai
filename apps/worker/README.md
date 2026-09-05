# Aria Worker

Python 3.12+ process boundary for long-running parsing, AI, validation, generation, revision and export work.

The Worker uses the Celery 5.6.3 Redis transport selected by ADR-015. Its Queue name, visibility
duration and concurrency are required runtime configuration with no repository default. The adapter
accepts JSON only, acknowledges late, rejects delivery on Worker loss, prefetches one message and
does not use a Celery result backend.

Startup emits `worker.runtime_started` with `queue_adapter_configured=true` immediately before the
Queue runtime takes control. PostgreSQL Job state remains the Client-visible Source of Truth.

The S1-G05 Metering boundary exposes provider-neutral `UsageLedger.append(record)` and a
SQLAlchemy adapter for the append-only PostgreSQL `usage_records` ledger. The deployed Worker
database credential must resolve to the non-superuser, non-RLS-bypass `aria_worker` role; that role
has only `INSERT` on the Ledger and cannot read or mutate raw Usage. API and Worker credentials must
not be shared. No public Usage endpoint or provider-specific branch is implemented.

Business task handlers, product timeout, retry/backoff and exhausted-message behavior are deferred
to S1-E04 and must not inherit evaluation fixture values.
