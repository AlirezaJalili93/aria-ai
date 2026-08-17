# ADR-001: Modular monolith برای MVP

- Status: Accepted
- Date: 2026-08-17

## Context

محصول، دامنه و الگوی مصرف هنوز در مرحلهٔ اعتبارسنجی‌اند. با این حال generation طولانی، tenant isolation و billing نیازمند مرزهای روشن هستند.

## Decision

API و منطق دامنه در یک deployable modular monolith باقی می‌مانند. worker deployable جداست، اما از همان قراردادها و domain package استفاده می‌کند. ارتباط بین ماژول‌ها از application API یا domain event انجام می‌شود.

## Consequences

- delivery و transaction ساده‌تر از microservice است.
- coupling با lint/import rules و ownership test کنترل می‌شود.
- scale worker مستقل است.
- استخراج آینده ممکن است، ولی رایگان نیست؛ قرارداد event و data ownership باید حفظ شود.

## Rejected

- Microservices از روز اول: operational cost و distributed consistency بدون شواهد کافی.
- Serverless function برای هر step: محدودیت زمان، debugging و local parity نامناسب برای pipeline اولیه.

