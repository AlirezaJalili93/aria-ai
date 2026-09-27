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

ADR-060 defines `aria.requirements.generate.v1` for controlled synthetic AI-02 tests. Its exact
Queue envelope also contains only `message_version`, `outbox_event_id` and `job_id`; the Worker
loads the frozen Context revision from PostgreSQL. The registration function exists for controlled
tests but is deliberately not called from hosted Worker composition.

ADR-061 defines `aria.gaps.detect.v1` for controlled synthetic AI-03 tests. Its exact Queue
envelope contains only `message_version`, `outbox_event_id` and `job_id`; the Worker loads the
pinned Context/Requirement revision vectors and policy versions from PostgreSQL. Empty Requirements
are valid. The registration function and Fake Provider exist only for controlled tests and are not
composed into the hosted Worker.

ADR-062 defines `aria.scope.generate.v1` for controlled synthetic AI-05 tests. Its envelope has
only `message_version`, `outbox_event_id` and `job_id`; exact inputs and tenant identity remain in
PostgreSQL. Task registration and the Fake Provider remain absent from hosted Worker composition.

