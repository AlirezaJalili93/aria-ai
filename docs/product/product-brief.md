# Product Brief — Aria AI MVP v1.0

- وضعیت منبع: Approved for UX & Architecture Breakdown
- منبع حاکم: [PRD — Aria AI MVP v1.0](https://docs.google.com/document/d/1zObOV8H1Moj2qcgAHjRqy5gVzS5ipg-CS__4CFgM9Gg/edit)
- تاریخ همگام‌سازی: 2026-08-17

## تعریف محصول

Aria فضای کاری هوشمند Agency Owner / Project Lead و Professional Freelancer است. محصول ورودی‌های پراکنده‌ی مشتری را به Context ساختاریافته، Requirement، Gap، Scope قابل تأیید، Preview قابل مشاهده و ویرایش، Feedback قابل ردیابی و Revision مبتنی بر Context تبدیل می‌کند.

مسئله‌ی اصلی «کند بودن کدنویسی» نیست؛ مسئله، دوباره‌کاری ناشی از گم‌شدن Context، Brief ناقص، تغییرات بدون Trace، Scope Creep و اختلاف بین آخرین Scope و آخرین خروجی است.

## Primary ICP و JTBD

Primary ICP آژانس کوچک تا متوسط طراحی و توسعه‌ی وب است که چند پروژه‌ی مشتری را هم‌زمان اداره می‌کند. Secondary ICP فریلنسر حرفه‌ای با پروژه‌های مستمر است.

JTBD: وقتی درخواست مشتری مبهم، پراکنده یا در حال تغییر است، کاربر می‌خواهد آن را سریع به Scope قابل تأیید تبدیل کند و تصمیم‌ها و اصلاحات را در Context واحد نگه دارد تا دوباره‌کاری، زمان تحویل و ریسک Margin کاهش یابد.

## Supported Project Types در MVP

- Landing Page
- Corporate / Service Website ساده
- Portfolio / Professional Personal Site

SaaS Dashboard چندنقشی، Marketplace پیچیده، ERP/CRM، Backend Workflow پیچیده، Full Ecommerce و Native Mobile App خارج از Supported Scope هستند.

## Core Journey

```text
Create Account
→ Create Project
→ Add Context
→ Structure Context
→ Extract Requirements
→ Detect Gaps
→ Clarify
→ Build Scope
→ Share Scope
→ Client Approves / Requests Change
→ Generate Preview
→ Review & Edit
→ Share Preview
→ Capture Feedback
→ Generate Context-aware Revision
→ Approve
→ Export/Deliver
→ Create Next Project
```

Sprint 1 فقط Vertical Slice داخلی Login → Project → Context → Structured Context → Requirements → Gaps → Internal Scope را هدف می‌گیرد. Sharing/Approval در Sprint 2، Generation/Preview در Sprint 3 و Feedback/Revision/Export در Sprint 4 قرار دارند.

## Product Principles

1. Human-in-the-loop: AI پیشنهاد می‌دهد و کاربر کنترل نهایی دارد.
2. Traceability by Default: Requirement، Scope Item، Approval، Feedback و Revision قابل ردیابی‌اند.
3. Source-aware AI: استنباط به‌عنوان Fact نمایش داده نمی‌شود.
4. Low Lock-in: Export و Handoff ممکن می‌ماند.
5. Trust before Automation: دلیل و اثر تغییر پیش از automation شدید روشن است.
6. Design for Scale, Pay for Current Load: مسیر Scale حفظ می‌شود بدون Provision بار فرضی.

## مرز MVP

Aria در MVP جایگزین IDE، Project Management Suite، Enterprise IAM، CI/CD Platform، Full Backend Builder، Database Designer عمومی یا تیم خودکار Multi-Agent نیست. Arbitrary server-side code execution و نصب آزاد dependency برای Generated Preview مجاز نیست.

## Outcomeهای محصول

- کاهش Time to Structured Context و Time to Scope Ready
- افزایش Scope Approval قبل از Development/Generation
- کاهش Revision ناشی از سوءبرداشت و Regression بخش‌های تأییدشده
- افزایش Repeat Project Behavior
- کنترل AI Cost per Completed Project

North Star Metric: پروژه‌هایی که در Aria به خروجی تأییدشده می‌رسند و همان Account برای پروژه‌ی دیگری بازمی‌گردد.

