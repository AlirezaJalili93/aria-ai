# Aria AI Design System — Master

## جهت طراحی

Aria یک ابزار کاری حرفه‌ای، اعتمادمحور و content-first است؛ نه یک landing نمایشی و نه یک رابط «جادوی AI». سبک پایه minimal و calm است، با hierarchy روشن، فضای کافی و نمایش صریح وضعیت پردازش و کنترل کاربر.

### Design dials

| Dial | مقدار | نتیجه |
|---|---:|---|
| Variance | 4/10 | ساختار آشنا با تمایز محدود در نقاط مهم |
| Motion | 3/10 | motion فقط برای علت/معلول و progress |
| Density | 6/10 | مناسب ابزار حرفه‌ای؛ فرم brief کمی خلوت‌تر |

## اصول

1. RTL-first، نه RTL-afterthought. layout با logical properties ساخته می‌شود.
2. در هر صفحه فقط یک primary action وجود دارد.
3. وضعیت job با متن، آیکن و progress مشخص می‌شود؛ رنگ به‌تنهایی معنا نمی‌دهد.
4. خروجی AI همیشه draft/preview نامیده می‌شود تا تأیید انسانی روشن بماند.
5. error باید علت، اثر و راه بازیابی را بگوید.
6. تغییر destructive نیازمند confirmation یا undo است.
7. مقدار خام رنگ/فاصله/فونت فقط در primitive layer تعریف می‌شود.

## Token architecture

```text
Primitive value
  -> Semantic purpose (surface, text, action, status)
    -> Component contract (button, field, card, progress)
```

منبع machine-readable در `packages/design-tokens/tokens.json` و خروجی CSS در `packages/design-tokens/tokens.css` است.

## رنگ و تم

- پایه: neutral slate با primary indigo؛ accent فیروزه‌ای فقط برای focus/progress محدود.
- light و dark هم‌زمان تعریف می‌شوند؛ dark mode معکوس سادهٔ رنگ‌ها نیست.
- body text حداقل 4.5:1 و UI boundary حداقل 3:1.
- success/warning/error همراه label یا icon هستند.

## تایپوگرافی

- فارسی: `Vazirmatn` در صورت self-host، سپس system sans.
- لاتین: system sans برای کاهش latency و mismatch.
- body حداقل 16px در موبایل و line-height حداقل 1.5.
- اعداد usage، credit و زمان با `font-variant-numeric: tabular-nums`.
- متن طولانی روی دسکتاپ حداکثر حدود 70 کاراکتر در هر خط.

## spacing و layout

- rhythm بر پایهٔ 4px/8px.
- breakpoints مرجع: 375، 768، 1024، 1440.
- container اصلی حداکثر 1280px؛ فرم بریف حداکثر 760px.
- desktop: sidebar برای navigation سطح اول. mobile: top bar و sheet؛ navigationهای هم‌سطح مخلوط نمی‌شوند.
- fixed bar باید inset محتوای scroll را رزرو کند.

## Component contracts

### Button

| State | الزام |
|---|---|
| Default | حداقل ارتفاع 44px، label صریح |
| Hover | تغییر رنگ token-driven، بدون جابه‌جایی layout |
| Focus-visible | ring حداقل 2px با offset |
| Loading | disabled semantics + spinner + label در حال انجام |
| Disabled | disabled واقعی، opacity و cursor متمایز |

### Field

- label همیشه visible است؛ placeholder مثال است، نه label.
- helper text قبل از error پایدار می‌ماند.
- validation روی blur/submit؛ بعد از submit focus به اولین خطا می‌رود.
- input mobile حداقل 44px و autocomplete مناسب دارد.

### Generation status

- progress region دارای `aria-live="polite"` است و روی هر tick focus نمی‌گیرد.
- step جاری، درصد و زمان تقریبی نمایش داده می‌شود.
- failure یک retry صریح و trace/reference قابل ارسال به پشتیبانی دارد.
- skeleton فقط وقتی layout نهایی را حفظ می‌کند استفاده می‌شود.

### Review canvas

- comment با keyboard قابل ایجاد و پیمایش است.
- انتخاب block فقط با outline رنگی نشان داده نمی‌شود؛ label/path هم دارد.
- approval از revision request از نظر مکان و visual weight جداست.
- پیش از approval، artifact hash/version به‌صورت قابل مشاهده خلاصه می‌شود.

## Motion

- micro interaction بین 150 تا 250ms.
- animation فقط transform/opacity و interruptible است.
- `prefers-reduced-motion` همهٔ حرکت‌های غیرضروری را حذف می‌کند.
- هیچ motionی input را block نمی‌کند یا layout shift نمی‌سازد.

## آیکن و asset

- یک خانوادهٔ SVG outline با stroke ثابت 2px.
- emoji به‌عنوان آیکن ساختاری ممنوع است.
- تصویر معنی‌دار alt فارسی دارد؛ تصویر تزئینی alt خالی.
- asset ابعاد/نسبت و rights metadata دارد تا CLS و provenance کنترل شود.

## چک‌لیست تحویل UI

- [ ] keyboard-only flow کامل است و focus گم نمی‌شود.
- [ ] screen reader نام، role، state و error را می‌خواند.
- [ ] 375px، 768px، 1024px و landscape بدون scroll افقی‌اند.
- [ ] target تعاملی حداقل 44×44px و فاصلهٔ امن دارد.
- [ ] light/dark contrast مستقل بررسی شده است.
- [ ] reduced-motion بررسی شده است.
- [ ] loading، empty، partial، timeout، error و retry وجود دارند.
- [ ] raw color داخل component وجود ندارد.
- [ ] navigation و state بعد از back حفظ می‌شوند.

