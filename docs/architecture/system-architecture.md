# معماری سیستم Aria AI — v2.0

- وضعیت منبع: FINAL / Approved for Sprint 1
- منبع حاکم: [Aria AI — Final System Architecture v2.0](https://docs.google.com/document/d/1X1GXQniuZ1RANrnlV1eRAyV8DJ1nQh9e4xaFbT96SSM/edit)
- تاریخ همگام‌سازی: 2026-08-17

## تصمیم پایه

سبک معماری `Modular Monolith + Durable Async Worker Pool` است. سه deployable پایه `web`، `api` و `worker` هستند. Domain جدید تا زمانی که evidence قابل اندازه‌گیری برای Scale، Isolation، Ownership یا Release مستقل وجود نداشته باشد به Microservice تبدیل نمی‌شود.

Stack مصوب:

- Web: Next.js + React + TypeScript Strict
- API: Python 3.12+ + FastAPI/Pydantic
- Persistence: PostgreSQL به‌عنوان Transactional Source of Truth
- Object IO: S3-compatible private storage port
- Async: Durable Queue با at-least-once delivery و idempotent consumer
- Cache/Quota projection: Redis-compatible؛ نه Domain یا Financial Source of Truth

## توپولوژی

```mermaid
flowchart TD
    U["Agency / Freelancer"] --> W["Next.js Web"]
    W --> A["FastAPI Modular Monolith"]
    A --> P[("PostgreSQL")]
    A --> O["Transactional Outbox"]
    A --> S[("S3-compatible Storage")]
    O --> Q["Durable Job Queue"]
    Q --> K["Python Worker Pool"]
    K --> G["Provider-neutral AI Gateway"]
    K --> P
    K --> S
    K --> R["Controlled Renderer"]
    R --> X["Separate Preview Trust Boundary"]
```

## لایه‌ها و جهت وابستگی

```text
API / Presentation → Application Use Cases → Domain
Infrastructure Adapters ─implements→ Domain/Application Ports
```

- Router فقط transport validation، identity/tenant resolution، use-case invocation و error mapping انجام می‌دهد.
- Application transaction، authorization، repository coordination، domain policy و outbox scheduling را کنترل می‌کند.
- Domain فقط Entity، Value Object، Invariant، Policy و Port دارد و FastAPI، Pydantic، SQLAlchemy، Redis، Supabase و AI SDK را import نمی‌کند.
- Provider SDK فقط در Infrastructure Adapter مجاز است.

## Domain Boundaries

| Module | مسئولیت |
|---|---|
| Identity & Membership | identity projection، account، membership، tenant context |
| Projects | project lifecycle و project type |
| Context | source، source version، structured item و context version |
| Requirements | requirement lifecycle و source trace |
| Gaps & Clarifications | gap، question، answer و resolution |
| Scope | draft، readiness policy و immutable version snapshot |
| Jobs | durable job lifecycle و idempotency |
| Metering | provider price version و append-only usage ledger |
| Sharing & Approval | Sprint 2 |
| Artifact & Revision | Sprint 3/4 |
| Billing & Entitlement | Sprint 5 |

Cross-module write فقط از Application Service انجام می‌شود. Side effect async حیاتی از Transactional Outbox عبور می‌کند.

## Multi-Tenant Invariants

- Tenant Anchor برابر `account_id` است.
- Aggregateهای محتوایی `account_id` مستقیم دارند.
- Client-supplied `account_id` authority نیست.
- Authorization در Backend، tenant-scoped repository، RLS و Cross-Tenant Test به‌صورت defense-in-depth استفاده می‌شوند.
- Service Role فقط در adapter محدود و audit‌شده مجاز است.

## Async Contract

```text
queued → running → succeeded | failed | cancelled
```

Critical parsing، AI، validation، generation، revision و export فقط در Worker اجرا می‌شوند. Job Status API منبع حقیقت Client است؛ SSE صرفاً enhancement است و Polling fallback الزامی می‌ماند. Delivery حداقل یک‌بار فرض می‌شود و duplicate نباید Artifact، Approval، Usage یا State تکراری ایجاد کند.

## AI و Generation Guardrails

- تمام Taskها از Provider-neutral Gateway عبور می‌کنند.
- Raw model output مستقیم persist نمی‌شود: schema validation → business validation → provenance/unsupported check → bounded repair → explicit failure.
- Generation از Schema-first Controlled Renderer استفاده می‌کند.
- Arbitrary server code، shell execution، secret injection و نصب آزاد npm dependency ممنوع است.
- Preview روی registrable domain جدا و بدون Core Cookie/Secret اجرا می‌شود.

## Versioning و Source of Truth

- PostgreSQL منبع حقیقت Domain، Job، Outbox و Usage Ledger است.
- Raw Source حفظ می‌شود؛ AI summary منبع حقیقت نیست.
- ScopeVersion و ArtifactVersion Snapshot تغییرناپذیرند.
- Restore تاریخچه را حذف نمی‌کند.
- Redis فقط queue/cache/quota projection است.

## مسیر Scale

API و Worker جداگانه scale افقی می‌شوند. AI Worker، Preview Runtime یا Billing/Metering فقط با evidence واقعی و ADR جدید قابل استخراج‌اند. Kubernetes، Kafka، Service Mesh، Event Sourcing کامل و Microservice-per-domain خارج از MVP baseline هستند.

