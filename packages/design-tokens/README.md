# Design tokens

`tokens.json` منبع حقیقت سه‌لایه است و `tokens.css` mapping اجرایی light/dark را ارائه می‌کند.

- raw value فقط در `primitive`.
- semantic token بر اساس هدف نام‌گذاری می‌شود، نه رنگ ظاهری.
- component token فقط به semantic/primitive ارجاع می‌دهد.
- تغییر contrast یا brand ابتدا در semantic mapping انجام می‌شود.

قبل از انتشار component، `npm run validate` اجرا شود.

