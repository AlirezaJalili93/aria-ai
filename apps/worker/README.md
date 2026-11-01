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

S1-L05 adds the Provider-neutral failure coordinator without promoting either candidate. Primary is
bounded to initial plus one technical retry; an explicitly authorized Fallback receives one call and
no retry, so a complete execution can never exceed three Provider invocations. SDK retry remains
disabled. Every actual invocation receives a unique `provider_attempt_id`; persistence replay is
idempotent, and timeout Usage that the Provider did not return is recorded as unavailable with NULL
token/cost fields rather than fabricated zeroes. Runtime Primary/Fallback wiring remains absent.

S1-E03/0070 adds the explicit `relay` process mode to this existing Worker artifact. It claims only
due `job_queue` Outbox rows in short PostgreSQL transactions, publishes `context_added.v1` as
`aria.context.parse.v1`, and acknowledges in a separate transaction. Claims use a 30-second lease,
batch size 20 and a two-second poll interval. Publish failure uses deterministic bounded backoff;
unknown queue events are blocked without deletion or hot-looping. Hosted Relay activation remains
disabled until the recovery gate in ADR-057 passes.

S1-E03/0071 adds the synthetic-only AI-01 runtime foundation. The approved Outbox event maps to
`aria.context.structure.v1` with an identifier-only Queue envelope, and the controlled Consumer
resolves its Tenant/Project state from PostgreSQL. Context Items, Project Context Version and Job
success commit atomically. `SyntheticContextStructuringAI` is not composed into `app.main` and the
task is not registered in the Hosted Worker. Increment 0072 adds the HTTP command and a controlled
two-process synthetic E2E harness, but does not change Worker runtime composition. Paid Providers,
customer content, Hosted task activation and automatic Queue retry remain prohibited.

S1-I02/0073 adds the synthetic-only AI-02 runtime foundation. The approved Outbox event maps to
`aria.requirements.generate.v1`; its Queue envelope contains only `message_version`,
`outbox_event_id` and `job_id`. The Job stores an exact Context Version and revision vector, while
Requirement writes, conflict Domain Events and Job success finalize atomically. The synthetic
adapter and task registration remain absent from `app.main`; public triggering, AI-01 chaining,
customer content, paid Providers, Hosted activation and automatic Queue retry remain prohibited.

S1-J02/0074 adds the synthetic-only AI-03 runtime foundation. The Job pins one exact Context
Version, both Context Item and Requirement revision vectors, and the accepted Checklist/Rule Pack
versions. An empty Requirement vector is valid; usable Context remains mandatory. The controlled
Fake Provider supplies complete Checklist signals and the deterministic Rule Pack remains the only
Critical authority. Gap rows, Requirement links, rule-result metadata and Job success finalize in
one transaction. `aria.gaps.detect.v1` and its Fake Provider remain absent from hosted composition;
public triggering, AI-02 chaining, customer content, paid Providers and automatic retry are
prohibited.

S1-K03/0075 adds the controlled, synthetic-only AI-05 runtime foundation. The internal Job pins
one Context Version and sorted Context Item, Requirement and Gap revision identities. The Worker
rechecks those inputs, validates K01's twelve-section Draft and trace, then inserts the Draft and
marks the same Job succeeded in one PostgreSQL transaction. `aria.scope.generate.v1` and the
Fake Provider are not composed into hosted `app.main`; public triggering, AI-04 chaining, customer
content, paid Providers and automatic Queue retry remain prohibited. A changed pinned input fails
with `SCOPE_GENERATION_INPUT_CHANGED` and does not create a Draft.
