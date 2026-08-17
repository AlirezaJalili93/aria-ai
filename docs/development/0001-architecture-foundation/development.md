# Development Record: Architecture foundation

- Increment ID: `0001-architecture-foundation`
- Date: 2026-08-17
- Owner: Codex
- Related plan/issue: Initial architecture request
- [Test report](./test-report.md)

## Scope

ساخت foundation معماری MVP شامل دامنهٔ محصول، modular-monolith boundaries، worker pipeline، قراردادهای HTTP/event، state machine، مدل داده، threat model، design tokens و زیرساخت محلی. ساخت UI یا vertical slice اجرایی خارج از دامنه بود.

## Source Documents

- درخواست اولیهٔ کاربر برای ایجاد معماری، پلن، اجرای مرحله‌ای و بازبینی سنیور.
- فایل‌های معرفی‌شدهٔ `ui-ux-pro-max.md` و `design-system.md`.
- Customer Discoveryهای شبیه‌سازی‌شده به‌عنوان سیگنال جهت‌دهنده، نه requirement قطعی.

## Requirement Traceability

| Requirement | Source | Implementation | Tests |
|---|---|---|---|
| REQ-001 | درخواست ایجاد معماری سیستم | `docs/architecture/` | TC-006 |
| REQ-002 | درخواست استفاده از راهنماهای UI/UX | `design-system/MASTER.md`, `packages/design-tokens/` | TC-006 |
| REQ-003 | درخواست بازبینی سنیور | `docs/reviews/review-log.md` | TC-006, TC-008 |
| REQ-004 | مستند MVP در Customer Discovery | `docs/product/product-brief.md`, state machine | TC-001..005 |

## Assumptions and Clarifications

داده‌های discovery به‌صراحت hypothesis علامت‌گذاری شدند و تصمیم‌های production به آینده موکول شدند.

**Unapproved assumptions:** None

## Changes

- معماری و ADRها در `docs/architecture/`.
- قراردادها در `packages/contracts/`.
- state machine اجرایی و تست‌ها در `packages/core/`.
- design system سه‌لایه در `design-system/` و `packages/design-tokens/`.
- threat model و storage abstraction.
- validator معماری و Docker Compose محلی.

## Architecture and Design Decisions

- modular monolith برای API/domain و worker مستقل برای کارهای طولانی.
- transactional outbox برای side effectهای async.
- human approval به‌عنوان invariant دامنه.
- canonical structured artifact به‌جای HTML آزاد به‌عنوان source of truth.
- filesystem storage adapter در local و S3-compatible adapter در deployment.

## Structure Preservation

در شروع این increment مخزن خالی بود؛ ساختار جدید مستقیماً از معماری مصوب همان increment ساخته شد. boundaryهای تعریف‌شده در `AGENTS.md` و قرارداد سه‌لایهٔ design token در تمام artifactها حفظ شدند.

## Senior Review

یافته‌های اصلاح‌شده شامل tenant context در outbox، تفکیک failureهای generation/export، حذف raw component token، حذف وابستگی local به emulator مشخص و اصلاح contrast dark mode بودند. جزئیات در `docs/reviews/review-log.md` ثبت شده است. ریسک production برای sandbox، tenant isolation و provider privacy همچنان صریح است.

## Verification

تست state machine، validator معماری، syntax check و `docker compose config` اجرا شدند. جزئیات و نتایج واقعی در [گزارش تست](./test-report.md) آمده است.

## Remaining Risks

- Customer Discovery هنوز شبیه‌سازی‌شده است.
- sandbox و tenant isolation فعلاً specification هستند و باید در vertical slice اثبات شوند.
- OpenAPI در این increment semantic lint کامل مستقل ندارد.
