# Aria AI — Sprint 1 Foundation

Aria یک فضای کاری هوشمند برای آژانس‌ها و فریلنسرهای حرفه‌ای است که ورودی پراکنده‌ی مشتری را به Context ساختاریافته، Requirement، Gap و Scope نسخه‌دار و قابل تأیید تبدیل می‌کند. این مخزن بر اساس PRD مصوب و Architecture v2 ساخته می‌شود.

## وضعیت فعلی

Increment `0004-repository-bootstrap` فقط Foundation مخزن را تحویل می‌دهد:

- Next.js App Router + TypeScript Strict برای `apps/web`؛
- Python 3.12+ + FastAPI برای `apps/api`؛
- Python Worker خنثی نسبت به Queue در `apps/worker`؛
- npm workspaces و uv lockfileهای مستقل؛
- Design Tokenهای سه‌لایه و پوسته‌ی RTL-first؛
- Architecture Fitness، تست و مستندات توسعه.

Auth، Database Migration، Queue، Storage، AI و Endpointهای محصول هنوز پیاده‌سازی نشده‌اند و فقط در Story/ADR مربوط به خود اضافه می‌شوند.

## پیش‌نیازهای Pin‌شده

- Node.js `24.x` و npm `11.x`
- Python `3.12.13`
- uv `0.12.5`

## Bootstrap محلی

```powershell
Copy-Item .env.example .env
npm ci
uv sync --project apps/api --locked
uv sync --project apps/worker --locked
npm run quality
```

برای اجرای پوسته‌ی Web:

```powershell
npm run dev --workspace @aria/web
```

برای اجرای API bootstrap پس از تکمیل `.env`:

```powershell
uv run --project apps/api uvicorn app.main:create_app --factory --app-dir apps/api
```

API در این Increment عمداً هیچ Endpoint محصولی ندارد.

## نقشه‌ی مخزن

- `apps/web`: Presentation و UX
- `apps/api`: Modular Monolith، Application و Domain modules
- `apps/worker`: پردازش‌های طولانی و async
- `packages/ui`: primitiveهای UI مشترک پس از نیاز اثبات‌شده
- `packages/contracts`: قراردادهای versioned
- `packages/config`: قرارداد config مشترک پس از نیاز اثبات‌شده
- `packages/design-tokens`: primitive → semantic → component tokens
- `infra`: زیرساخت محلی و بعداً deployment
- `evals`: AI evaluation fixtures و reports
- `tests/e2e`: Journeyهای end-to-end
- `docs/adr`: تصمیم‌های معماری جدید

## اسناد حاکم

- [خلاصه‌ی محصول](docs/product/product-brief.md)
- [معماری سیستم](docs/architecture/system-architecture.md)
- [مدل داده](docs/architecture/data-model.md)
- [سیاست توسعه‌ی مستندمحور](docs/governance/document-driven-development.md)
- [رکوردهای توسعه و تست](docs/development/README.md)
- [Design System](design-system/MASTER.md)
- [ADRها](docs/adr/README.md)

## قواعد غیرقابل مذاکره

1. Tenant isolation، immutable versions، transactional outbox، durable jobs، AI metering و preview isolation Release Guardrail هستند.
2. Domain از Framework و Infrastructure مستقل می‌ماند.
3. عملیات طولانی داخل request همگام اجرا نمی‌شود.
4. AI assumption را Fact معرفی نمی‌کند و Human Review در نقاط critical الزامی است.
5. هر Increment دارای `development.md` و `test-report.md` نهایی و PASS است.
6. توسعه فقط براساس Requirement مستند انجام می‌شود؛ ابهام با سؤال از کاربر حل می‌شود.

