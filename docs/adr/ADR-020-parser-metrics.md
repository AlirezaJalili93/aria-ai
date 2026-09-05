# ADR-020 — Parser Metrics Contract

- Status: Accepted for Sprint 1 F04
- Date: 2026-09-05
- Scope: Text Parser observability boundary
- Sources: [Sprint 1 Technical Backlog v1.0](https://docs.google.com/document/d/1O0yayIY1Akal6sV1jVJa6LGkZuJZSYGL_JhqMf6UNsA/edit?usp=drivesdk), [Engineering Execution Master Plan v1.0](https://docs.google.com/document/d/1QbaAQt2jd9mmLvpMVkH-AjrKlp4QaIozRJYp3hxOJYs/edit?usp=drivesdk)

## Decision

The Worker Application exposes a provider-neutral `ParserMetrics` port for the three approved
measurements: `parse_latency`, `queue_wait`, and the derived `failure_rate`. No metrics backend or
vendor SDK is selected by this ADR.

### Measurement boundaries

- `parse_latency` is the elapsed time from entry to `TextParser.parse` until successful return or
  Parser failure. It includes normalization and empty validation, and excludes queue wait and
  persistence.
- `queue_wait` is the elapsed time from the Job `available_at` boundary to Worker execution start
  for a Parser Job. The current parser boundary exposes the sink operation; Job task wiring remains
  outside this increment because no Parser Job registration contract is approved.
- `failure_rate` is `failed_parse_attempts / (successful_parse_attempts + failed_parse_attempts)`.
  Canceled Jobs and attempts that never enter the Parser are excluded.

### Bounded dimensions

The only domain dimensions are:

- `parser_type`: `text` in this increment.
- `outcome`: `success` or `failure`.
- `failure_class` on failures only: `unsupported_format`, `empty`, `parse_error`, or `timeout`.

Tenant, Project, Source, Job, filename, raw error text, and other free-form values are forbidden
from metric labels. Resource metadata such as service/environment remains a sink concern.

### Logs and trace context

The parser may emit `parser.parse_started`, `parser.parse_succeeded`, and `parser.parse_failed`
through the existing structured logger. Trace context carries request/correlation identifiers and
logs may include validated internal identifiers; metrics never receive those identifiers as labels.
Raw text, canonical text, and free-form error messages are never emitted.

## Consequences

- Text Parser latency and outcome instrumentation is available without coupling Application code to
  Prometheus, OpenTelemetry, Redis, Celery, or another backend.
- A future Queue/Job task can call `observe_queue_wait` once its timing source is approved.
- A future sink must derive `failure_rate` from the outcome counter and preserve the bounded label
  set.
- File Parser remains blocked by its separate DOCX/PDF reliability gate; this ADR does not enable it.

**Unapproved assumptions:** None
