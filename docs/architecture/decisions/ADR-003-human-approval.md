# ADR-003: Human-in-the-loop به‌عنوان invariant دامنه

- Status: Accepted
- Date: 2026-08-17

## Context

اسناد محصول بر بی‌اعتمادی به تغییر design/architecture خودکار و نیاز به خروجی قابل‌ویرایش تأکید می‌کنند.

## Decision

approval یک state transition صریح، با actor، timestamp و artifact hash است. export production فقط از artifact تأییدشده مجاز است. revision artifact جدید می‌سازد و approval قبلی را به خروجی جدید منتقل نمی‌کند.

## Consequences

- audit و اعتماد افزایش می‌یابد.
- یک click اضافه در flow وجود دارد.
- API، UI و worker نمی‌توانند approval را ضمنی فرض کنند.

