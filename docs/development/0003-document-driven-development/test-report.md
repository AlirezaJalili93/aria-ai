# Test Report: Document-driven development policy

- Increment ID: `0003-document-driven-development`
- Date: 2026-08-17
- Environment: Windows, Node.js v24.11.1, npm 11.6.2
- [Development record](./development.md)

## Environment

تست‌ها با Node test runner و fixtureهای موقت در مسیر سیستم اجرا می‌شوند. هیچ سرویس خارجی یا دادهٔ production درگیر نیست.

## Test Cases

| ID | Type | Scenario | Expected result |
|---|---|---|---|
| TC-301 | Static/Policy | قواعد source، سؤال در ابهام و حفظ ساختار | در AGENTS و governance doc موجود باشند |
| TC-302 | Unit/Negative | development record بدون `REQ-*` | validator آن را رد کند |
| TC-303 | Unit/Schema | development record بدون headingهای ساختاری جدید | validator آن را رد کند |
| TC-304 | Unit/Negative | مقدار Unapproved assumptions غیر از None | validator آن را رد کند |
| TC-305 | Integration/Static | اجرای validator روی تمام incrementها | تمام رکوردها traceable، linked و PASS باشند |
| TC-306 | Regression | state machine و quality-gate tests قبلی | بدون regression پاس شوند |
| TC-307 | Static | syntax و marker scan | syntax معتبر و marker ناقص وجود نداشته باشد |

## Execution Results

| ID | Command or steps | Actual result | Status |
|---|---|---|---|
| TC-301 | بررسی محتوای `AGENTS.md` و governance doc با UTF-8 | source، سؤال در ابهام، حفظ ساختار و منع فرض تأیید شدند | PASS |
| TC-302..304 | `npm test` | تست‌های فقدان traceability، فقدان Structure Preservation و فرض تأییدنشده، هر سه ورودی نامعتبر را رد کردند | PASS |
| TC-305 | `npm run validate` | pre-final گزارش PENDING را رد کرد؛ اجرای نهایی همهٔ 12 check را پاس کرد | PASS |
| TC-306 | `npm test` | مجموع 11 تست، شامل 5 تست domain و 6 تست documentation gate، پاس شد | PASS |
| TC-307 | `node --check ...` و scan markerها | syntax معتبر و marker ناقص پیدا نشد | PASS |

## Failures and Corrections

- اجرای pre-final validator با failure مورد انتظار، وضعیت PENDING همین گزارش را رد کرد.
- بررسی اولیهٔ متن فارسی در PowerShell به‌علت encoding پیش‌فرض false negative داد؛ command با `Get-Content -Encoding utf8` اصلاح و دوباره با موفقیت اجرا شد. کد محصول تحت تأثیر نبود.

## Final Status

**Final status:** PASS
