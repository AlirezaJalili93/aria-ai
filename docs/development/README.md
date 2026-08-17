# Development and test records

از این نقطه به بعد، هیچ increment توسعه‌ای بدون دو artifact زیر تکمیل‌شده محسوب نمی‌شود:

```text
docs/development/NNNN-kebab-case/
├── development.md
└── test-report.md
```

## چرخهٔ اجباری

1. در شروع increment پوشه و دو فایل از روی `_template` ساخته می‌شوند.
2. source documentها و requirementهای `REQ-*` پیش از implementation ثبت می‌شوند.
3. هر ابهام یا نیاز به فرض با سؤال از کاربر رفع می‌شود؛ بخش مبهم پیاده نمی‌شود.
4. test caseها پیش از یا هم‌زمان با implementation نوشته می‌شوند.
5. پس از implementation، حفظ ساختار و senior review در `development.md` ثبت و یافته‌ها اصلاح می‌شوند.
6. آخرین اجرای testها با command، expected، actual و status در `test-report.md` ثبت می‌شود.
7. فقط وقتی همهٔ testهای الزامی پاس شدند، `**Final status:** PASS` و `**Unapproved assumptions:** None` ثبت می‌شوند.
8. `npm test` و `npm run validate` اجرا می‌شوند. validator تحویل ناقص یا گزارش PENDING/FAIL را رد می‌کند.

## قواعد نام‌گذاری و محتوا

- شناسه: `NNNN-kebab-case`، مانند `0003-project-creation`.
- فایل‌ها باید Markdown باشند و نام آن‌ها تغییر نکند.
- `development.md` و `test-report.md` باید به هم لینک داشته باشند.
- `development.md` باید sourceها، traceability، clarificationها و ارزیابی حفظ ساختار را داشته باشد.
- نتیجهٔ واقعی ثبت می‌شود؛ تست اجرا‌نشده نباید PASS نوشته شود.
- failure موقت می‌تواند در history گزارش بیاید، اما final status تحویل باید PASS باشد.
- تست‌های دستی باید device/viewport، مراحل و evidence داشته باشند.
- تغییرات امنیتی، migration، contract و UI باید case متناسب با ریسک خود داشته باشند.

## پوشش حداقلی بر اساس نوع تغییر

| نوع تغییر | حداقل تست |
|---|---|
| Domain | unit + invariant/negative path |
| API contract | schema/contract + authz + idempotency |
| Database | migration + rollback/recovery + tenant isolation |
| Worker | retry + idempotency + timeout/failure |
| UI | interaction + keyboard + RTL/LTR + responsive + accessibility |
| Security | abuse/negative case + audit evidence |
| Documentation/tooling | validator positive + validator negative case |

## رکوردها

- [0001 — Architecture foundation](./0001-architecture-foundation/development.md)
- [0002 — Documentation quality gate](./0002-documentation-quality-gate/development.md)
- [0003 — Documentation-driven development policy](./0003-document-driven-development/development.md)
