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

S1-G06 adds the read-only `ProviderPriceCatalog` boundary. The Worker resolves the exact effective
Price Version before any future paid Provider invocation, then uses the retained resolution and
normalized token counts to calculate the ledger cost with Decimal/`ROUND_HALF_UP`. The catalog has
no runtime write path or public management API.

S1-G02/G03 add evaluation-only Infrastructure adapters for OpenAI `gpt-5.6-terra` and Google
`gemini-3.8-flash`. Neither is a runtime primary or fallback. Both require Structured Output, use
5-second connect and 60-second request/read limits, disable SDK retries and tools, and may receive
only synthetic fixtures. The Application resolves and retains a Price Version before invocation.
OpenAI explicit cache mode must report `cache_write_tokens=0`; any missing/malformed/non-zero value
fails closed because the current Usage Ledger cannot price cache writes. Gemini output tokens include
both candidate and thinking tokens, while Context Cache creation remains disabled.

Business task handlers, product timeout, retry/backoff and exhausted-message behavior are deferred
to S1-E04 and must not inherit evaluation fixture values.
