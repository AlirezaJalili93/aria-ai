# ADR-013: واژگان فعلی Jobs و مرز Transactional Outbox

- Status: Accepted
- Date: 2026-09-02

## Context

اسناد قدیمی‌تر Migration Plan و Production Data Architecture برای Job از نام‌هایی مانند
`task_type`، `attempt_no`، `input_ref` و `completed_at` استفاده می‌کنند. Detailed Data Dictionary
به‌روزشده نام‌های `job_type`، `attempt_count`، `payload_ref`، `finished_at` و `created_at` را به‌عنوان
واژگان فعلی داده تعریف می‌کند. S1-D02 نیز باید Source، Version، Job و Outbox را بدون dual-write ثبت
کند، اما انتخاب queue transport و retry/backoff به S1-E02 تعلق دارد.

## Decision

- schema فیزیکی `jobs` از واژگان Detailed Data Dictionary فعلی استفاده می‌کند و نام‌های قدیمی
  فقط سابقهٔ superseded محسوب می‌شوند.
- `jobs` و `outbox_events` در ماژول Jobs و PostgreSQL، Source of Truth عملیاتی هستند.
- Application Service مالک transaction است؛ Job و Outbox Event پیش از یک commit واحد نوشته می‌شوند.
- `outbox_events.payload` بعد از commit تغییرناپذیر است و event UUID کلید پایدار انتشار آینده است.
- RLS برای هر دو جدول فعال و Data API بدون policy/grant صریح fail-closed می‌ماند.
- relay، queue adapter، retry/backoff، dead-letter و duplicate-delivery handler در این تصمیم انتخاب
  نمی‌شوند؛ قرارداد جزئی Relay در [ADR-016](ADR-016-outbox-relay-contract.md) ثبت شده و Queue
  Producer/Consumer semantics همچنان به ADRهای بعدی نیاز دارد.

## Consequences

- dual-write بین Domain DB و queue وارد API نمی‌شود.
- schema برای User Jobهای tenant-anchored و System Jobهای بدون Project آماده است.
- Publisher آینده می‌تواند با event UUID، Outbox پایدار و at-least-once delivery کار کند، بدون تغییر
  payload تاریخی.
- اسناد توسعه باید صریحاً تفاوت logical migration `M008` و Alembic revision
  `0005_jobs_outbox` را ثبت کنند.
