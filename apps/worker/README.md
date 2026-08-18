# Aria Worker

Python 3.12+ process boundary for long-running parsing, AI, validation, generation, revision and export work.

This bootstrap contains no queue framework or task handler because the accepted documents leave the queue framework to a dedicated spike/ADR. Future task wrappers must be durable, bounded, correlation-aware and idempotent while reusing application workflows.

Until that adapter exists, startup reports `runtime-started queue_adapter_configured=false`; it never claims that the Worker is ready to process jobs.
