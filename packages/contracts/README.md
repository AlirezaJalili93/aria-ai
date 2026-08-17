# Contracts

- `openapi.yaml` baseline قرارداد `/api/v1` است. Endpoint هر Story هم‌زمان با implementation و contract test افزوده می‌شود.
- `events.schema.json` envelope مشترک رویدادهای outbox/queue را تعریف می‌کند.

قواعد تغییر:

1. حذف یا تغییر معنای field در همان نسخه ممنوع است.
2. consumer باید field ناشناخته در payload رویداد را تحمل کند؛ envelope سخت‌گیرانه است.
3. رویداد جدید suffix نسخه دارد.
4. prompt خام، secret و PII غیرضروری نباید وارد event شود.
5. endpoint mutation حساس/گران بدون strategy و header مربوط به idempotency اضافه نشود.
6. Contract تولیدی FastAPI و snapshot این package باید در CI بدون drift بمانند.
