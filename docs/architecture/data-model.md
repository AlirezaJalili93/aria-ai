# مدل داده‌ی Sprint 1 — Architecture v2

- منبع حاکم: [Production Data Architecture & Database Schema v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit)
- فرهنگ داده: [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit)
- برنامه‌ی اجرا: [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit)
- تاریخ همگام‌سازی: 2026-09-01

این سند mirror توسعه‌دهنده‌محور مدل مصوب است. Migrationها فقط در Story پایگاه داده و با Alembic versioned ایجاد می‌شوند؛ وجود این سند مجوز ساخت schema خارج از آن Story نیست.

## اصول

- PostgreSQL منبع حقیقت تراکنشی Domain، Version، Job، Outbox و Usage است.
- Tenant Anchor برابر `account_id` است و در جدول‌های محتوایی مستقیم ذخیره می‌شود.
- timestampها `timestamptz` و UTC هستند.
- `updated_at` جدول‌های mutable را PostgreSQL با trigger مصوب ADR-010 مدیریت می‌کند.
- UUIDها server-side تولید می‌شوند.
- Shared/Approved ScopeVersion تغییرناپذیر و UsageRecord append-only است.
- Redis فقط Queue/Cache/Quota Projection است.
- JSONB برای Snapshot، metadata و source reference مجاز است؛ جایگزین Entityهای عملیاتی اصلی نیست.

## ترتیب Migration مصوب

```text
M000 extensions
→ M001 accounts / profiles / account_memberships
→ M002 projects
→ M003 context_sources / context_source_versions
→ M004 context_items
→ M005 requirements
→ M006 gaps / clarifications
→ M007 scope_drafts / scope_versions
→ M008 jobs / outbox_events
→ M009 provider_price_versions / usage_records
→ M010 RLS baseline
```

## Identity و Tenancy

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| accounts | id=`gen_random_uuid()`, plan_id, status, created_at, updated_at | Tenant root |
| profiles | user_id, display_name, locale=`fa-IR`, profile_data, timestamps | Email/password در Aria کپی نمی‌شود؛ Auth Provider منبع هویت خارجی است |
| account_memberships | id, account_id, user_id, role, status, joined_at | `UNIQUE(account_id,user_id)`؛ Role متعلق به Membership است؛ status فقط active/invited/suspended |

`suspended` یعنی Membership همچنان وجود دارد اما authority عملیاتی ندارد. حذف Membership
عملیات مستقل است و با suspended مدل نمی‌شود.

## Project و Context

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| projects | id, account_id, owner_id, title, project_type, status, current_context_version=`0`, created_at, updated_at, deleted_at | `owner_id` به Profile وصل است؛ type فقط landing/corporate/portfolio؛ status فقط draft/active/awaiting_approval/approved/generating/delivered/archived؛ version نامنفی؛ حذف نرم |
| context_sources | id, account_id, project_id, source_type, status, original_name, mime_type, storage_ref, raw_text, checksum, created_by, created_at, updated_at | type در DB برابر text/file/message/url_reference و در S1-D01 Application فقط text؛ status برابر uploaded/parsing/ready/failed/deleted؛ query عادی deleted را حذف می‌کند |
| context_source_versions | id, account_id, project_id, source_id, version_no, content_hash, canonical_text/storage_ref, metadata, parse_status, created_at | parse status برابر pending/parsing/ready/failed؛ `version_no>=1` و `UNIQUE(source_id,version_no)`؛ ready immutable و دارای canonical text/ref؛ history حفظ می‌شود |
| context_items | id, account_id, project_id, context_version, item_type, content, source_refs, confidence, status | item_type: fact/assumption/decision/constraint/reference/unknown |

## Requirement، Gap و Scope

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| requirements | id, account_id, project_id, context_version, category, content, status, source_refs | حذف traceable با deactivate/supersede |
| gaps | id, account_id, project_id, context_version, gap_type, severity, status, source_refs, accepted_assumption | accepted assumption فقط با action صریح |
| clarifications | id, account_id, project_id, gap_id, question, answer, resolution metadata | history پاسخ حفظ می‌شود |
| scope_drafts | id, account_id, project_id, context_version, content, updated_by | Draft mutable است |
| scope_versions | id, account_id, project_id, version_no, context_version, snapshot_data, snapshot_hash | `UNIQUE(project_id,version_no)` و Snapshot immutable است |

## Async و Metering

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| jobs | id, account_id, project_id, task_type, status, idempotency_key, attempts, payload/result refs | at-least-once و duplicate-safe |
| outbox_events | id, event_type, aggregate, account_id, payload, status, available/published time | همراه تغییر Business در یک Transaction |
| provider_price_versions | id, provider, model, unit prices, currency, validity | Historical price version تغییر نمی‌کند |
| usage_records | id, account_id, project_id, job_id, provider/model/task/workflow/prompt/pricing versions, tokens, latency, cost, status | append-only و traceable |

## Index و RLS Baseline

- Indexهای list/query با `account_id` آغاز می‌شوند.
- Projects: `(account_id, created_at desc)`, `(account_id, status)`, `(account_id, project_type)`.
- Entityهای Context/Requirement/Gap/Scope با account/project/version یا status index می‌شوند.
- RLS روی جدول‌های tenant-owned فعال است؛ Backend authorization مستقل از RLS باقی می‌ماند.
- Cross-Tenant tests برای SELECT/UPDATE/DELETE و child tableها Release Blocker هستند.
- Queryهای عادی Project فقط `deleted_at IS NULL` را می‌خوانند؛ بازیابی حذف‌شده مسیر داخلی
  صریح می‌خواهد.
- Current Source Version برابر بیشترین `version_no` با `parse_status=ready` است؛ pointer ذخیره‌شده
  ندارد. Version با composite FK نمی‌تواند Account/Project متفاوت از Source داشته باشد و حذف
  فیزیکی Source دارای Version با `RESTRICT` متوقف می‌شود.
- Create Project فقط با Membership فعال همان Account مجاز است و `owner_id` از subject احرازشده
  می‌آید.

## Migration Guardrails

- Migration پس از merge immutable است.
- Fresh DB chain و upgrade path در CI تست می‌شوند.
- تغییر destructive از Expand/Contract و recovery plan استفاده می‌کند.
- Seed فقط Local/Staging و شامل Tenant A/B است.
- Schema دستی در Staging/Production ممنوع است.
