# مدل داده‌ی Sprint 1 — Architecture v2

- منبع حاکم: [Production Data Architecture & Database Schema v2.0](https://docs.google.com/document/d/1w7k1hUHbWLS4YLsZU9QmLJDRkuSnG5zJ77_US82_x1w/edit)
- فرهنگ داده: [Detailed Data Dictionary v1.0](https://docs.google.com/document/d/1TIZ96m-VvtdR3-_QtnsC5sK_maqfi_aMcUhj9xTDCaQ/edit)
- برنامه‌ی اجرا: [Database Migration Execution Plan v1.0](https://docs.google.com/document/d/1VyLMX73lvXsmkR9PvDIJH5Qe29Ulga4Qw6gA4WZ1qaQ/edit)
- تاریخ همگام‌سازی: 2026-09-09

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
→ M006 gaps (J01) / clarifications (J03 deferred)
→ M007 scope_drafts / scope_versions
→ M008 jobs / outbox_events
→ M009 usage_records (S1-G05) / provider_price_versions deferred to S1-G06
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
| context_items | id, account_id, project_id, context_version, item_type, content, source_refs, confidence, status, created_by_type, created_by, created_at, updated_at | version >=1؛ item type برابر fact/assumption/decision/constraint/reference/unknown؛ status برابر proposed/confirmed/rejected/superseded؛ Fact تأییدشده حداقل یک provenance معتبر دارد؛ user-created دارای created_by است؛ updated_at را PostgreSQL مدیریت می‌کند |

## Requirement، Gap و Scope

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| requirements | id, account_id, project_id, context_version, category, title, description, priority, status, source_refs, confidence, is_unsupported, duplicate_group_key, generation_job_id, acceptance_note, created_by_type, created_by, created_at, updated_at | version بین 1 و current Project؛ category شش‌حالته؛ priority اجباری بدون default؛ status برابر draft/confirmed/superseded/removed؛ AI batch با Job non-unique قابل replay است؛ acceptance note nullable است؛ provenance و creator tenant-safe |
| gaps | id, account_id, project_id, context_version, gap_type, severity, status, source_refs, explanation, suggested_resolution_type, generation_job_id, created_at, updated_at, resolved_at | type برابر missing_information/ambiguity/conflict/decision_required/unsupported_assumption/scope_risk؛ generated rows دارای explanation، resolution enum و Job association هستند؛ Critical فقط پس از validated AI-assisted Rule Signal و Rule Pack نسخه‌دار authoritative است و Critical مدل بدون Rule Match به High تبدیل می‌شود؛ status برابر open/resolved/dismissed؛ `resolved_at` فقط در status resolved و برای open/dismissed تهی؛ حذف فیزیکی ممنوع |
| gap_requirement_links | account_id, project_id, gap_id, requirement_id, created_at | affected Requirements رابطه‌ای و tenant/snapshot-consistent هستند؛ JSONB و semantic merge ممنوع |
| clarifications | id, account_id, project_id, gap_id, question_text, status, created_by_type, created_by, created_at, updated_at | status برابر open/answered/ignored؛ سؤال user-created دارای created_by است؛ فقط سؤال open قابل ویرایش است و متن normalized سؤال باز در هر Gap یکتا است |
| clarification_resolutions | id, account_id, project_id, gap_id, clarification_id, resolution_type, answer_text, author_type, author_id, actor_id, created_at | هر Clarification حداکثر یک Resolution terminal دارد؛ actor داخلی احرازشده اجباری است؛ author فقط user/client و client بدون Profile مجاز است؛ تاریخچه با RESTRICT حفظ می‌شود |
| scope_drafts | id, account_id, project_id, context_version, content, updated_by | Draft mutable است |
| scope_versions | id, account_id, project_id, version_no, context_version, snapshot_data, snapshot_hash | `UNIQUE(project_id,version_no)` و Snapshot immutable است |

## Async و Metering

| Table | کلیدهای اصلی | Invariant |
|---|---|---|
| jobs | id, account_id, project_id, job_type, status, payload_ref, attempt_count/max_attempts, idempotency_key, correlation_id, available/started/finished/created time, safe error | state machine پایدار؛ Queue transport منبع حقیقت نیست؛ J02-A نتیجه terminal Gap را با کلید خصوصی `payload_ref.gap_count` ثبت می‌کند تا replay صفر نیز قابل اثبات باشد |
| outbox_events | id, account_id, aggregate_type/id, event_type, payload, status, attempt_count, available/created/published time | همراه تغییر Business در یک Transaction؛ payload immutable |
| idempotency_records | id, account_id, actor_id, route_key, idempotency_key, request_hash, response_status/ref, expires_at, created_at | `UNIQUE(account_id,actor_id,route_key,idempotency_key)`؛ TTL برابر ۲۴ ساعت؛ request hash تمام input مؤثر از جمله Project را پوشش می‌دهد |
| provider_price_versions | id, provider, model, unit prices, currency, validity | Historical price version تغییر نمی‌کند |
| usage_records | id؛ account_id اجباری؛ project_id/job_id nullable؛ task_type؛ workflow_version؛ prompt_version؛ provider/model/provider_request_id؛ input/cached/output tokens؛ latency_ms؛ status؛ error_code؛ retry_no؛ repair_no؛ estimated_cost؛ currency؛ pricing_version؛ correlation_id؛ created_at | append-only و traceable؛ status فقط success/failed/partial؛ مقدارهای عددی نامنفی؛ cost بدون default؛ نقش `aria_worker` فقط INSERT دارد؛ FKهای Account/Project/Job همگی `ON DELETE RESTRICT` |

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
- `jobs` و `outbox_events` با `(status, available_at)` و tenant-created-at index می‌شوند؛ Project Job
  باید Account همان Project را حمل کند. نام‌های قدیمی `task_type/attempt_no/input_ref/output_ref` طبق
  [ADR-013](../adr/ADR-013-jobs-outbox-persistence.md) superseded هستند.
- Usage Ledger با `(account_id, created_at desc)` و FKهای Project/Job index می‌شود. واژهٔ
  `retry_no` برای Usage canonical است و `attempt_no` قدیمی را supersede می‌کند. Provider و Model
  دادهٔ ثبت‌شده‌اند، نه enum یا branching در Domain/Application.
- `repair_no` اجرای معنایی AI را از Provider retry جدا می‌کند: اجرای اصلی `0` و Repair نخست `1`
  است. سقف Sprint 1 در Policy نسخه‌دار Application است و DB فقط `repair_no >= 0` را enforce می‌کند؛
  جزئیات در [ADR-027](../adr/ADR-027-context-validation-repair.md) ثبت شده است.
- Context Item با `(account_id, project_id, context_version)` index می‌شود. `context_version`
  عدد صحیح canonical است و `context_version_id` قدیمی را supersede می‌کند. هر عنصر `source_refs`
  به Source و Source Version آماده در همان Tenant اشاره می‌کند و offset اختیاری آن نیم‌بازهٔ
  صفرمبنا روی `canonical_text` است. `source_ref` مفرد و `state=active` قدیمی supersede شده‌اند؛
  جزئیات در [ADR-025](../adr/ADR-025-context-item-provenance-contract.md) ثبت شده است.
- H04 روی همان Context Itemها `updated_at` را برای CAS مدیریت می‌کند؛ فهرست فعلی با
  `(account_id, project_id, context_version, created_at desc, id desc)` و فیلتر provenance با GIN
  ایندکس می‌شود. جزئیات در [ADR-028](../adr/ADR-028-context-review-contract.md) ثبت شده است.
- H02 آخرین Version آمادهٔ هر Source حذف‌نشده را یک‌بار snapshot می‌کند. Batch فقط پس از اعتبارسنجی
  کامل persist می‌شود؛ Project با row lock نسخهٔ بعدی را تخصیص می‌دهد و درج همهٔ Context Itemها و
  پیشروی `current_context_version` در یک Transaction انجام می‌شود. جزئیات در
  [ADR-026](../adr/ADR-026-context-structuring-workflow.md) ثبت شده است.
- H03 فقط defectهای deterministic خروجی مدل را حداکثر یک‌بار با همان Workflow/Routing و Prompt
  نسخه‌دار Repair می‌کند. هر خروجی دوباره کل validation را طی می‌کند و exhaustion هیچ Context
  write یا Version increment ندارد؛ جزئیات در [ADR-027](../adr/ADR-027-context-validation-repair.md)
  ثبت شده است.
- Requirement با `context_version INTEGER` به Context موجود Project متصل می‌شود و نسخهٔ آینده یا
  Project بدون Context را نمی‌پذیرد. `title+description` جای `content` و `created_by_type` جای
  `source_type` را گرفته‌اند. `source_refs` قرارداد provenance مصوب H01 را حفظ می‌کند؛ جزئیات در
  [ADR-030](../adr/ADR-030-requirement-domain-contract.md) ثبت شده است.
- I02 از مجموعهٔ دقیق Context Itemهای `proposed|confirmed` برای نسخهٔ درخواست‌شده Snapshot
  می‌گیرد. Requirement پشتیبانی‌شده حداقل یک Source Reference معتبر از همان Snapshot دارد؛
  unsupported می‌تواند بدون reference باشد. Duplicateهای دقیق فقط provenance را stable-union
  می‌کنند، دادهٔ موجود کاربر بازنویسی نمی‌شود و تعارض‌ها به‌صورت ردیف‌های مستقل همراه Outbox signal
  اتمیک ثبت می‌شوند. `generation_job_id` unique نیست و index
  `(account_id, project_id, generation_job_id)` همراه status نهایی Job همان Tenant replay را
  پشتیبانی می‌کند. جدول result یا Snapshot تاریخی Generation در I02 ایجاد نمی‌شود؛ جزئیات در
  [ADR-031](../adr/ADR-031-requirement-generation-contract.md) ثبت شده است.
- I03 افزودن دستی را به Context Version فعلی و Idempotency ۲۴ساعته متصل می‌کند؛ ویرایش با
  `expected_updated_at` انجام می‌شود و ویرایش Requirement تأییدشده آن را به draft برمی‌گرداند.
  حذف عمومی فقط draft را به removed تبدیل می‌کند؛ `acceptance_note` nullable است و Snapshot/restore
  همچنان خارج Scope است. جزئیات در [ADR-032](../adr/ADR-032-requirement-crud-contract.md) ثبت شده است.
- J01 از `context_version INTEGER` و provenance مصوب H01 استفاده می‌کند. `missing_info`،
  `context_version_id` و accepted-assumption Boolean قدیمی supersede شده‌اند. Account/Project
  deletion با RESTRICT متوقف می‌شود؛ detection/linkage در J02 و Clarification/resolution behavior
  در J03 می‌مانند. جزئیات در [ADR-035](../adr/ADR-035-gap-domain-contract.md) ثبت شده است.
- J03-A مدل سادهٔ قدیمی Clarification را با دو موجودیت سؤال و Resolution ممیزی‌پذیر supersede
  می‌کند. `provided_information/internal_decision/accepted_assumption` سؤال را answered و `ignored`
  آن را ignored می‌کند؛ Gap فقط وقتی resolved می‌شود که هیچ سؤال open باقی نمانده باشد. Ignore سؤال
  هرگز Gap را dismissed نمی‌کند و dismiss تنها command صریح مستقل است. همهٔ FKها RESTRICT و linkage
  Account/Project/Gap/Clarification با composite FK محافظت می‌شود. Data API roleهای عمومی دسترسی
  مستقیم ندارند و RLS فعال است؛ جزئیات در
  [ADR-038](../adr/ADR-038-clarification-domain-api.md) ثبت شده است.

## Migration Guardrails

- Migration پس از merge immutable است.
- Fresh DB chain و upgrade path در CI تست می‌شوند.
- تغییر destructive از Expand/Contract و recovery plan استفاده می‌کند.
- Seed فقط Local/Staging و شامل Tenant A/B است.
- Schema دستی در Staging/Production ممنوع است.
- `aria_worker` تنها نقش Runtime دارای `INSERT` مستقیم روی Usage Ledger است؛ `aria_api`، `anon` و
  `authenticated` هیچ دسترسی مستقیم ندارند و Worker نباید با super/service bypass اجرا شود.
