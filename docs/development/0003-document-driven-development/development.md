# Development Record: Document-driven development policy

- Increment ID: `0003-document-driven-development`
- Date: 2026-08-17
- Owner: Codex
- Related plan/issue: User-mandated no-assumption development policy
- [Test report](./test-report.md)

## Scope

ثبت و enforce کردن این اصل که توسعه فقط بر پایهٔ مستندات انجام شود، ساختار موجود کامل حفظ شود و در هر نقطهٔ نیازمند فرض یا دارای ابهام، توسعهٔ آن بخش متوقف و از کاربر سؤال شود.

## Source Documents

- درخواست صریح فعلی کاربر دربارهٔ توسعهٔ مستندمحور، منع فرض، حفظ کامل ساختار و پرسش در نقاط مبهم.
- `AGENTS.md` به‌عنوان محل قواعد دائمی repository.
- `docs/development/README.md` و quality gate increment 0002.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-301 | توسعه فقط بر اساس مستندات | `AGENTS.md`, `docs/governance/document-driven-development.md` | TC-301, TC-305 |
| REQ-302 | ممنوعیت فرض توسعه‌دهنده | policy، marker اجباری assumptions و validator | TC-302, TC-304, TC-305 |
| REQ-303 | حفظ کامل ساختار | policy و section اجباری `Structure Preservation` | TC-303, TC-305 |
| REQ-304 | سؤال از کاربر در ابهام | conflict/clarification process در policy و `AGENTS.md` | TC-301, TC-305 |
| REQ-305 | traceability requirement → implementation → test | template و validator | TC-302, TC-305 |

## Assumptions and Clarifications

درخواست کاربر صریح بود و برای ثبت این policy نیاز به تصمیم محصولی یا فنی نامستند وجود نداشت.

**Unapproved assumptions:** None

## Changes

- بخش Documentation-driven development به `AGENTS.md` افزوده شد.
- policy تفصیلی source precedence، سؤال در ابهام و حفظ ساختار در `docs/governance/` ایجاد شد.
- template توسعه با Source Documents، Requirement Traceability، Assumptions/Clarifications و Structure Preservation تکمیل شد.
- validator وجود requirement ID و نبود فرض تأییدنشده را enforce می‌کند.
- رکوردهای 0001 و 0002 برای سازگاری با قاعدهٔ جدید تکمیل شدند.
- تست‌های منفی traceability مفقود و فرض تأییدنشده اضافه شدند.

## Architecture and Design Decisions

این تغییر governance و quality tooling است و مرز deployable یا تصمیم معماری محصول را تغییر نمی‌دهد؛ ADR جدید لازم نیست. ترتیب منابع به‌صورت صریح مستند شد تا تعارض‌ها با انتخاب سلیقه‌ای حل نشوند.

## Structure Preservation

- ساختار modular monolith، قراردادها، domain package و design tokenها تغییر نکردند.
- ساختار `docs/development/<increment-id>/` حفظ و فقط headingهای الزامی آن گسترش یافت.
- رکوردهای قبلی حذف یا جابه‌جا نشدند و با requirementهای جدید backfill شدند.

## Senior Review

- قاعدهٔ متنی به‌تنهایی قابل فراموشی بود؛ validator آن را enforce کرد.
- «ذکر source» بدون traceability دقیق کافی نبود؛ شناسهٔ `REQ-*` و اتصال به test case اجباری شد.
- validator نمی‌تواند معنای کامل مستند یا صداقت پاسخ را اثبات کند؛ به همین دلیل توقف و سؤال از کاربر همچنان یک مسئولیت process-level در `AGENTS.md` است.
- تغییری در معماری محصول انجام نشد، بنابراین ADR نساختن مطابق قواعد موجود است.

## Verification

تست‌های positive و negative validator، regression state machine، validator کامل مخزن و syntax/hygiene اجرا می‌شوند. نتایج نهایی در [گزارش تست](./test-report.md) ثبت می‌شوند.

## Remaining Risks

- تشخیص semantic اینکه یک تصمیم واقعاً از سند پشتیبانی می‌شود کاملاً قابل اتوماسیون نیست؛ review انسانی و traceability همچنان لازم‌اند.

