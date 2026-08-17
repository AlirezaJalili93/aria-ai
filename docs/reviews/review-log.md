# Senior review log

تاریخ بازبینی: 2026-08-17

## مرحلهٔ ۱ — دامنه و محصول

### یافته‌ها

- سه سند Customer Discovery صراحتاً شبیه‌سازی‌شده‌اند و تعداد High/Medium/Low، تاریخ‌ها و پرسونای آن‌ها با هم سازگار نیست.
- دامنهٔ اولیه از wireframe تا backend، deploy، debug، payment و Figma بسیار گسترده بود.
- خطوط قرمز مشترک، کنترل انسانی، کد قابل‌ویرایش، RTL و امنیت کد مشتری بودند.

### اصلاح انجام‌شده

- شواهد discovery به‌عنوان hypothesis علامت‌گذاری شد.
- beachhead به فریلنسر حرفه‌ای/آژانس کوچک فنی محدود شد.
- MVP به brief clarification → wireframe → static responsive code → review/approval → export محدود شد.
- معیارهای موفقیت قابل اندازه‌گیری و Definition of Done اضافه شد.

### نتیجه

تأیید مشروط: scope برای شروع مهندسی مناسب است، اما قبل از pricing و گسترش feature باید مصاحبهٔ واقعی انجام شود.

## مرحلهٔ ۲ — معماری کلان

### یافته‌ها

- microservice از روز اول هزینهٔ عملیاتی و distributed transaction غیرضروری ایجاد می‌کرد.
- اجرای generation در HTTP باعث timeout، retry مبهم و تجربهٔ کاربری ضعیف می‌شد.
- ذخیرهٔ HTML آزاد به‌عنوان حقیقت اصلی، versioning و rendererهای آینده را قفل می‌کرد.
- outbox اولیه tenant context صریح نداشت.

### اصلاح انجام‌شده

- modular monolith + worker مستقل انتخاب و در ADR ثبت شد.
- async pipeline با transactional outbox و idempotent worker تعریف شد.
- canonical structured artifact از preview/export جدا شد.
- `workspace_id` به مدل outbox افزوده شد.
- معیارهای واقعی استخراج سرویس اضافه شد تا جداسازی سلیقه‌ای رخ ندهد.

### نتیجه

تأیید: معماری برای MVP ساده، قابل رشد و متناسب با failure profile محصول است.

## مرحلهٔ ۳ — قراردادها و قواعد دامنه

### یافته‌ها

- approval اگر فقط concern رابط باشد، worker یا export می‌تواند ناخواسته آن را دور بزند.
- queue با delivery حداقل یک‌بار بدون idempotency خطر دوباره‌هزینه‌کردن credit دارد.
- تغییر مستقل stateها در API و core خطر contract drift دارد.
- یک وضعیت شکست مشترک برای generation/export، recovery اشتباه و هزینهٔ دوباره ایجاد می‌کرد.

### اصلاح انجام‌شده

- state machine executable ساخته شد و approval فقط از `AWAITING_REVIEW` مجاز است.
- export تنها پس از `APPROVED` آغاز می‌شود.
- endpointهای mutation دارای `Idempotency-Key` و approval دارای artifact hash + expected version شدند.
- validator تطابق enum وضعیت بین OpenAPI و core را بررسی می‌کند.
- event envelope، prompt خام و PII غیرضروری را ممنوع کرد.
- شکست‌ها به `GENERATION_FAILED` و `EXPORT_FAILED` تفکیک شدند تا retry دقیقاً از مرز درست ادامه دهد.

### نتیجه

تأیید: invariants مهم قابل اجرا و قابل تست شده‌اند. implementation آینده باید contract test و database isolation test اضافه کند.

## مرحلهٔ ۴ — Design system، امنیت و زیرساخت

### یافته‌ها

- height کنترل‌ها ابتدا مستقیماً در component token آمده بود و زنجیرهٔ primitive → component را دور می‌زد.
- قفل‌کردن محیط محلی به یک S3 emulator مشخص، lifecycle بیرونی را به foundation تحمیل می‌کرد.
- generated code، preview و asset URL سه ورودی untrusted مستقل هستند.
- toneهای اولیهٔ primary/danger در dark mode برای متن عادی به contrast 4.5:1 نمی‌رسیدند.

### اصلاح انجام‌شده

- اندازهٔ کنترل به primitive منتقل و component فقط alias شد.
- emulator مشخص حذف و storage port تعریف شد: filesystem در local و S3-compatible در deployment.
- toneهای `indigo300` و `red400` برای متن dark اضافه و contrast check خودکار وارد validator شد.
- RTL، dark mode، reduced motion، focus و حداقل target 44px در master design system ثبت شد.
- sandbox بدون network، preview origin جدا، CSP، SSRF guard و content hash وارد threat model شدند.
- portهای local فقط روی loopback bind شدند.

### نتیجه

تأیید: foundation با قواعد دو فایل راهنمای UI/UX و design system هم‌راستاست. contrast واقعی باید هنگام ساخت componentها با ابزار خودکار اندازه‌گیری شود.

## مرحلهٔ ۵ — Verification نهایی

### Gateها

- `npm test`: پنج تست state machine پاس شد.
- `npm run validate`: وجود artifactها، JSON، token references، raw color، idempotency، state drift، loopback binding و لینک‌ها را بررسی می‌کند.
- OpenAPI با validator ساختاری و تطابق stateها بررسی می‌شود؛ semantic lint کامل در vertical slice بعدی اضافه خواهد شد.
- Compose با `docker compose config` بررسی می‌شود.

اولین اجرای validator یک لینک شکسته به همین review log را پیدا کرد؛ فایل ایجاد و gate دوباره اجرا شد. این رفتار مطلوب validator بود، نه خطای پنهان‌شده.

## ریسک‌های پذیرفته‌شده و کار بعدی

| ریسک | وضعیت | اقدام بعدی |
|---|---|---|
| discovery شبیه‌سازی‌شده | پذیرفته‌شده برای foundation | 8 تا 12 مصاحبه واقعی با beachhead |
| stack اجرایی هنوز scaffold کامل ندارد | آگاهانه؛ این تحویل architecture foundation است | vertical slice با fake provider |
| data residency/PSP نامشخص | blocker برای production، نه local MVP | بررسی حقوقی و adapter selection |
| sandbox فقط specification است | blocker برای اجرای کد untrusted | prototype + escape test قبل از provider واقعی |
| contrast component واقعی هنوز اندازه‌گیری نشده | منتظر implementation UI | axe + contrast CI + viewport tests |

## حکم نهایی بازبین

نسخهٔ 0.1 برای شروع vertical slice مورد تأیید است. برای production مورد تأیید نیست تا tenant isolation، sandbox، backup restore، provider privacy و payment reconciliation به‌صورت integration/e2e اثبات شوند.
