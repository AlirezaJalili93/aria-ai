# Development Record: Documentation quality gate

- Increment ID: `0002-documentation-quality-gate`
- Date: 2026-08-17
- Owner: Codex
- Related plan/issue: Permanent development documentation requirement
- [Test report](./test-report.md)

## Scope

تبدیل الزام کاربر به یک اصل enforce‌شده در مخزن: هر increment تکمیل‌شده باید دارای فایل Markdown مستند توسعه و گزارش test case/نتیجهٔ تست باشد. این تغییر شامل قواعد repository، templateها، رکورد گذشتهٔ foundation و validator خودکار است.

## Source Documents

- درخواست صریح کاربر: پس از پایان هر توسعه، فایل Markdown مستند توسعه، test caseها و نتایج تست داخل پروژه قرار گیرد.
- `AGENTS.md` برای ثبت قاعدهٔ دائمی repository.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-201 | الزام مستند توسعه برای هر increment | `AGENTS.md`, `docs/development/README.md`, template | TC-201, TC-202 |
| REQ-202 | الزام test case و نتیجهٔ تست | `test-report.md` convention و validator | TC-201, TC-203 |
| REQ-203 | اجرای اصل تا پایان توسعه | `scripts/lib/development-records.mjs` | TC-202, TC-203, TC-205 |

## Assumptions and Clarifications

فرمت Markdown و قرارگیری داخل پروژه مستقیماً توسط کاربر تعیین شده بود؛ convention پوشه در این increment مستند و enforce شد.

**Unapproved assumptions:** None

## Changes

- قواعد اجباری completion در `AGENTS.md` اضافه شد.
- convention و templateها در `docs/development/` ایجاد شدند.
- رکورد `0001-architecture-foundation` برای تحویل قبلی backfill شد.
- validator قابل تست در `scripts/lib/development-records.mjs` ساخته شد.
- `npm test` برای اجرای تست‌های quality gate گسترش یافت.
- `scripts/validate-architecture.mjs` تحویل ناقص، لینک مفقود و final status غیر-PASS را رد می‌کند.

## Architecture and Design Decisions

این الزام یک quality gate مخزن است و deployable یا مرز دامنهٔ جدیدی ایجاد نمی‌کند؛ بنابراین ADR جدید لازم نیست. رکوردها per-increment و با نام پایدار `NNNN-kebab-case` ذخیره می‌شوند تا history قابل مرور و machine validation باشد.

## Structure Preservation

هیچ boundary معماری، قرارداد عمومی یا design token تغییر نکرد. تغییرات فقط به governance، documentation و validation tooling افزوده شدند و ساختار موجود توسعه یافت، نه جایگزین.

## Senior Review

- اتکا به توافق متنی کافی نبود؛ enforcement خودکار اضافه شد.
- یک گزارش مشترک برای چند increment traceability را تضعیف می‌کرد؛ پوشهٔ مستقل برای هر increment انتخاب شد.
- امکان ثبت PASS بدون test case کاهش یافت: وجود حداقل یک `TC-*`، لینک دوطرفه، headingهای اجباری و final status بررسی می‌شود.
- validator صحت ادعای نتیجه را نمی‌تواند اثبات کند؛ اجرای واقعی commandها همچنان مسئولیت توسعه‌دهنده و CI است. این ریسک در متن policy صریح شد.

## Verification

unit testهای positive/negative برای validator نوشته شدند و quality gate کلی مخزن اجرا شد. جزئیات در [گزارش تست](./test-report.md) ثبت شده است.

## Remaining Risks

- validator ساختار و status را enforce می‌کند، اما جعل دستی نتیجه را از نظر فنی تشخیص نمی‌دهد؛ CI آینده باید test report را از artifact اجرای pipeline نیز تولید/امضا کند.
