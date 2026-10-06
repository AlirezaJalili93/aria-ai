# برنامه و نقشه راه اتصال فرانت‌اند به بک‌اند (Frontend-Backend Integration Plan)

این سند، معماری فنی، پروتکل‌های ارتباطی و گام‌های اجرایی اتصال کامل رابط کاربری وب (`@aria/web`) به سرور و سرویس‌های بک‌اند FastAPI (`@aria/api`) را بر مبنای قراردادهای معماری نسخه ۲ پروژه **Aria AI** تدوین می‌کند.

---

## ۱. اصول معماری و پروتکل‌های انتقال داده (Architectural Guidelines)

1. **انزوا و احراز هویت مستأجر (Tenant-Scoped Transport):**
   - تمامی درخواست‌های دیتا به بک‌اند موظف به ارسال هدرهای زیر هستند:
     - `Authorization: Bearer <supabase_access_token>`
     - `X-Account-ID: <account_uuid>`
     - `X-Request-ID: <unique_uuid>`
     - `X-Correlation-ID: <unique_uuid>`
2. **پایداری در ارسال مجدد و عدم تکرار (Idempotency):**
   - کلیه عملیات جهش (Mutation) مانند ساخت پروژه موظف به حمل هدر `Idempotency-Key` هستند.
3. **عدم اختراع قراردادهای جدید (Contract Fidelity):**
   - روت‌های بک‌اند دقیقاً منطبق بر `api/v1` و اسکمای Pydantic تاییدشده در `apps/api/app/api/routers/` هستند.
4. **صفحه‌بندی بر مبنای Keyset Cursor:**
   - واکشی داده‌های لیست پروژه‌ها بدون offset و صرفاً با `next_cursor` ایمن انجام می‌گیرد.

---

## ۲. فازبندی گام‌به‌گام اتصال (Phased Implementation Roadmap)

### فاز ۱: زیرساخت اجرایی و سلامت سرویس‌ها (Infrastructure & Runtime Readiness)
- [ ] اجرای کانتینرهای محلی PostgreSQL 16 و Redis 7 از طریق `infra/compose.yaml`.
- [ ] اجرای اسکریپت ایجاد جداول و مایگریشن‌های دیتابیس (`python scripts/db/migrate.py`).
- [ ] اجرای سرور بک‌اند FastAPI با Uvicorn روی پورت 8000 (`http://localhost:8000`).
- [ ] اتصال و بررسی هلث‌چک‌های `/health/live` و `/health/ready`.

### فاز ۲: اتصال احراز هویت و کشف حساب (Identity & Account Discovery Flow)
- [ ] دریافت نشست کاربر از Supabase Auth در Server Actions فرانت‌اند.
- [ ] فراخوانی اندپوینت `GET /api/v1/accounts` برای تطبیق هویت کاربر با فضای کاری فعال (`AccountSelection`).
- [ ] استخراج شناسه اکانت و نقش کاربر (`owner`, `admin`, `member`) و کش کردن سشن سرور.

### فاز ۳: اتصال داشبورد و ایجاد پروژه (Projects Dashboard Integration)
- [ ] اتصال `fetchProjects` به `GET /api/v1/projects` با صفحه‌بندی داینامیک.
- [ ] اتصال فرم ساخت پروژه (`CreateProjectForm`) به `POST /api/v1/projects` با ارسال هدر یکتا.
- [ ] تست جریان کامل ساخت پروژه واقعی و نمایش آنی در لیست پروژه‌ها.

### فاز ۴: اتصال ماژول ورودی‌های زمینه (Context Sources API Integration)
- [ ] پیاده‌سازی و اتصال روتر `POST /api/v1/projects/{projectId}/context-sources` در بک‌اند با پشتیبانی از `source_type="text"`.
- [ ] اتصال فرم ثبت بریف در تب Context فضای کاری (`ProjectWorkspace`) به API واقعی بک‌اند جهت ذخیره متن بریف در دیتابیس.
- [ ] نمایش لیست واقعی سورس‌های ذخیره‌شده با متادیتا و نسخه (`current_context_version`).

### فاز ۵: اتصال پورتال امضای کارفرما (Scope Sign-Off Integration)
- [ ] اتصال ثبت تأییدیه دیجیتال کارفرما و صدور توکن اعتبارسنجی با تغییر وضعیت پروژه در بک‌اند به `approved`.
- [ ] پیوند شناسه پروژه واقعی به پورتال امضا `/scope/[projectId]`.

---

## ۳. تضمین کیفیت و اعتبارسنجی (Quality Gates)
* پاس شدن ۱۰۰٪ تست‌های قراردادی `npm run test:api` و `npm run test:web`.
* پاس شدن اعتبارسنجی معماری `node scripts/validate-architecture.mjs`.
* عدم رگرسیون در استایل‌ها، رعایت کامل RTL و دسترسی‌پذیری.
