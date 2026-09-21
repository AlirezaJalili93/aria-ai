# Worker tasks

S1-E04 provides the provider-neutral `JobExecutionGuard` and execution coordinator foundation.
Increment 0064 supplies the approved controlled TXT Parser path: an exact versioned message is
validated, PostgreSQL remains authoritative, and a PostgreSQL advisory lock suppresses concurrent
execution. Automatic retry is disabled. Queue ACK/requeue policy, retry/backoff policy and
artifact-specific constraints remain deferred until separately approved.

S1-F01/F02 provides the provider-neutral `TextParser` boundary and deterministic
`CanonicalTextParser`. Increment 0064 adds Source Version persistence, strict private TXT reread,
lowercase SHA-256 canonical hashing and atomic Parser finalization.

ADR-057 supersedes the earlier registration deferral. The Worker now registers exactly one Parser
task, `aria.context.parse.v1`, and the explicit `relay` process mode continuously claims eligible
`job_queue` Outbox rows with a lease before publishing. The controlled runner remains available for
direct verification. Hosted Relay activation is still disabled until the 0070 recovery gate passes;
`domain_event` delivery and any other task mapping remain deferred.

ADR-058 defines the additional task identity `aria.context.structure.v1` and its registration
function for controlled synthetic tests only. Increment 0071 deliberately does not call that
registration from the Worker runtime and does not compose its Fake Provider. Its exact Queue
envelope contains `message_version`, `outbox_event_id` and `job_id`; all Context is resolved from
PostgreSQL. Hosted registration and real Provider execution require later contracts.

