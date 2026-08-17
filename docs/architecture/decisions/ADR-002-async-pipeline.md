# ADR-002: Pipeline غیرهمگام و transactional outbox

- Status: Accepted
- Date: 2026-08-17

## Context

فراخوانی مدل، render، build و validation کند و خطاپذیرند. dual-write مستقیم به database و queue می‌تواند job گم‌شده یا تکراری بسازد.

## Decision

API وضعیت run، credit reservation و outbox event را در یک transaction می‌نویسد. relay رویداد را به queue می‌فرستد. worker با delivery حداقل یک‌بار و handlerهای idempotent کار می‌کند.

## Consequences

- job گم نمی‌شود و retry امن است.
- UI بلافاصله `202` و شناسهٔ قابل پیگیری می‌گیرد.
- relay، dead-letter policy و reconciliation job باید مانیتور شوند.

