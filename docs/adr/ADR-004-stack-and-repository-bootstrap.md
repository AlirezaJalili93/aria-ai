# ADR-004: Stack and Repository Bootstrap

- Status: Accepted
- Date: 2026-08-17
- Supersedes: بخش‌های TypeScript Backend و JavaScript Domain در foundation قبلی
- Canonical references: ADR-032 و ADR-033 در Accepted ADR Pack v1.0

## Context

Architecture v2 و Repository Specification، Web را Next.js/TypeScript Strict و Backend/Worker را Python 3.12+/FastAPI تعیین می‌کنند. Foundation قبلی API و Worker را TypeScript معرفی کرده و یک Generation state machine برای Journey قدیمی داشت.

کاربر در 2026-08-17 تأیید کرد Architecture v2 جایگزین foundation قبلی شود، JavaScript ناسازگار بازنشسته گردد، تاریخچه‌ی توسعه حفظ شود و npm workspaces + uv با نسخه‌های پایدار pin‌شده استفاده شوند.

## Decision

- `apps/web`: Next.js/React/TypeScript Strict با npm workspace.
- `apps/api`: Python 3.12+/FastAPI و uv lockfile مستقل.
- `apps/worker`: Python 3.12+ و uv lockfile مستقل.
- Domain/Application هیچ Framework یا Provider SDK import نمی‌کند.
- Queue framework در این ADR انتخاب نمی‌شود؛ Celery/Dramatiq/RQ در Spike جدا ارزیابی می‌شوند.
- Dependencyهای مستقیم exact pin و dependencyهای transitively resolved در lockfile ثبت می‌شوند.
- رکوردهای توسعه قبلی حفظ و فقط artifactهای اجرایی ناسازگار بازنشسته می‌شوند.

## Consequences

- اکوسیستم Backend با AI/document processing و معماری مصوب هم‌راستا می‌شود.
- Web و Python toolchain دو lockfile family دارند و root scripts باید هر دو را orchestration کنند.
- انتخاب Queue، Auth، Database Migration و Integrationها همچنان نیازمند Story/ADR مستقل است.
- Contract و Fitness Testهای قدیمی وابسته به Generation state machine باید با guardrailهای Architecture v2 جایگزین شوند.

## Rejected

- حفظ TypeScript Backend: با سند نهایی تعارض دارد.
- انتخاب Queue در Bootstrap: ADR مربوط هنوز Open است و evidence Spike ندارد.
- تبدیل به Microservices: Architecture v2 آن را بدون evidence رد می‌کند.
