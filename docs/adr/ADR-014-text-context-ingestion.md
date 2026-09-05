# ADR-014: قرارداد Text Context Ingestion و Idempotency عمومی

- Status: Accepted
- Date: 2026-09-05

## Context

Story `S1-D02` باید ورودی متنی را بدون از دست‌دادن محتوا ثبت و پردازش غیرهمزمان را آغاز کند.
اسناد موجود طول مجاز، canonicalization مربوط به checksum و دامنه/TTL idempotency را کامل قفل
نکرده بودند. مالک محصول این موارد را برای Increment حاضر صریحاً تصویب کرد. در عین حال Source،
Version، Job و Outbox Event باید یک واحد تراکنشی باشند و متن مشتری نباید وارد payload عملیاتی یا
log شود.

## Decision

- Endpoint برابر `POST /api/v1/projects/{project_id}/context-sources` و body دقیقاً شامل
  `source_type=text` و `raw_text` است؛ فیلد اضافه رد می‌شود.
- متن بین ۱ تا ۵۰٬۰۰۰ Unicode character پذیرفته می‌شود. متن whitespace-only، NUL و سایر control
  characterهای ممنوع رد می‌شوند؛ tab، LF و CR مجازند.
- `raw_text` دقیقاً بدون trim یا HTML stripping ذخیره می‌شود. `checksum` برابر lowercase SHA-256
  روی byteهای UTF-8 همین متن دقیق است.
- Source با وضعیت `uploaded`، Version شماره ۱ با `parse_status=pending`، Job از نوع
  `context_source_parse` و Outbox Event از نوع `context_added.v1` در یک transaction ثبت می‌شوند.
- `jobs.payload_ref` فقط `source_id` و `source_version_id` دارد. متن خام، متن canonical و URL
  ذخیره‌سازی وارد Job، Outbox یا log نمی‌شوند.
- جدول عمومی `idempotency_records` دامنهٔ یکتا را با
  `(account_id, actor_id, route_key, idempotency_key)` و TTL دقیق ۲۴ ساعت نگه می‌دارد.
- fingerprint علاوه بر body دقیق، Project مقصد را هم پوشش می‌دهد تا یک کلید نتواند نتیجهٔ Project
  دیگری را replay کند. همان key و input کامل همان پاسخ `202` را replay می‌کند؛ input متفاوت
  `409 IDEMPOTENCY_CONFLICT` می‌دهد.
- Queue transport، parse implementation، retry/backoff و Source-ready transition در این ADR تعیین
  نمی‌شوند و متعلق به Storyهای بعدی هستند.

## Consequences

- retry شبکه duplicate Source/Version/Job ایجاد نمی‌کند و expiration پس از ۲۴ ساعت امکان درخواست
  جدید می‌دهد.
- PostgreSQL منبع حقیقت عملیات است و انتشار queue آینده از Transactional Outbox انجام می‌شود.
- checksum Source برای traceability محتوای خام است؛ idempotency request hash مفهوم جداگانه‌ای دارد
  و تمام input مؤثر بر نتیجه را پوشش می‌دهد.
- فعال‌کردن `file`، `message` یا `url_reference` در Application نیازمند Increment مصوب مستقل است.
