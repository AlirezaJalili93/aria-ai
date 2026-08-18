export default function HomePage() {
  return (
    <div className="app-shell">
      <header className="app-header" aria-label="سربرگ محصول">
        <span className="product-name" lang="en">
          Aria AI
        </span>
        <span className="release-label">Sprint 1 foundation</span>
      </header>
      <main id="main-content" className="main-content" tabIndex={-1}>
        <p className="eyebrow">اسکلت فنی مصوب</p>
        <h1>فضای کاری Aria</h1>
        <p className="intro">
          این پوسته، مرز ارائه‌ی مسیر «Context تا Scope» است. قابلیت‌های محصول فقط طبق
          بک‌لاگ و قراردادهای تأییدشده به آن افزوده می‌شوند.
        </p>
        <section className="status-card" aria-labelledby="status-title">
          <h2 id="status-title">وضعیت این Increment</h2>
          <p>Web، API و Worker در حال آماده‌سازی محیط مستقل Staging هستند.</p>
        </section>
      </main>
    </div>
  );
}
