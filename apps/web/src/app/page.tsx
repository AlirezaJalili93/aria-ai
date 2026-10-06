'use client';

import Link from "next/link";
import { useState } from "react";
import { 
  ArrowLeft, 
  Layers, 
  FileSearch, 
  ShieldCheck, 
  Sparkles,
  Lock
} from "lucide-react";

export default function HomePage() {
  const [activeTab, setActiveTab] = useState(0);

  const workflowSteps = [
    {
      id: "input",
      title: "۱. دریافت ورودی خام",
      subtitle: "یادداشت‌ها، چت یا فایل TXT بریف",
      desc: "ورودی‌های پراکنده، پیام‌های کارفرما و متون نامنظم را وارد کنید بدون اینکه نگران فرمت باشید.",
      badge: "Context Source",
      previewText: "کارفرما در تلگرام: 'می‌خوام یه سایت شرکتی داشته باشم با پرداخت آنلاین و پنل مشتریان، کاربرا بتونن تیکت بزنن و وضعیت سفارش رو ببینن...'"
    },
    {
      id: "requirements",
      title: "۲. استخراج نیازمندی‌ها",
      subtitle: "تحلیل دقیق و فکت‌محور",
      desc: "هوش مصنوعی فکت‌های فنی، نقش‌های کاربری و رفتارهای سیستم را استخراج کرده و قابل ردیابی (Traceable) می‌کند.",
      badge: "Requirements Spec",
      previewText: "• REQ-01: پورتال احراز هویت دومرحله‌ای مشتریان\n• REQ-02: پنل ثبت تیکت پشتیبانی با تاریخچه گفتگو\n• REQ-03: درگاه پرداخت آنلاین شاپرک با ثبت تراکنش"
    },
    {
      id: "gaps",
      title: "۳. کشف هوشمند گپ‌ها",
      subtitle: "جلوگیری قطعی از Scope Creep",
      desc: "ابهامات پنهان در قرارداد، قوانین نامشخص بازپرداخت، معماری دیتابیس و الزامات امنیتی پیش از کدنویسی آشکار می‌شوند.",
      badge: "Gap Detection",
      previewText: "⚠️ گپ بحرانی: درگاه پرداخت برای اشخاص حقیقی است یا حقوقی؟ سیستم مالیات و فاکتور رسمی چگونه صادر می‌شود؟\n→ سؤال شفاف‌ساز آماده ارسال برای کارفرما"
    },
    {
      id: "scope",
      title: "۴. اسنپ‌شات قطعی Scope",
      subtitle: "نسخه رسمی و غیرقابل تغییر",
      desc: "پس از پاسخ به گپ‌ها، دامنه کار قفل شده و به یک سند حقوقی و فنی با شماره نسخه و هش اختصاصی تبدیل می‌شود.",
      badge: "Immutable Snapshot",
      previewText: "نسخه Scope v1.0.0 (هش SHA-256: 4f8b2c...) تصویب شد. هر تغییر جدید نیازمند Change Request و محاسبه مجدد زمان و هزینه است."
    },
    {
      id: "approval",
      title: "۵. پورتال تأیید کارفرما",
      subtitle: "لینک اختصاصی بدون نیاز به لاگین",
      desc: "کارفرما با یک کلیک و ثبت امضای دیجیتال محدوده کار را تأیید می‌کند؛ یا با دلیل مشخص درخواست اصلاح می‌دهد.",
      badge: "Public Client Sign-off",
      previewText: "کارفرما (علی محمدی) در تاریخ ۱۴۰۵/۰۵/۱۸ محدوده پروژه را رسماً تأیید کرد. وضعیت: APPROVED ✓"
    }
  ];

  return (
    <div className="app-shell">
      {/* Navigation Header */}
      <header className="app-header" aria-label="سربرگ اصلی">
        <Link href="/" className="header-brand">
          <div className="brand-logo-icon">A</div>
          <span className="product-name">Aria AI</span>
          <span className="release-label">نسخه ۱.۰</span>
        </Link>

        <nav className="header-nav" aria-label="ناوبری اصلی">
          <a href="#workflow" className="header-nav-link">نحوه کارکرد</a>
          <a href="#features" className="header-nav-link">مزیت‌ها</a>
          <a href="#manifesto" className="header-nav-link">فلسفه محصول</a>
        </nav>

        <div className="header-actions">
          <Link href="/auth/login" className="btn btn-secondary btn-sm">
            ورود به سیستم
          </Link>
          <Link href="/auth/signup" className="btn btn-primary btn-sm">
            شروع رایگان
            <ArrowLeft size={16} />
          </Link>
        </div>
      </header>

      <main id="main-content">
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-glow" />
          <div className="hero-container">
            <div className="hero-eyebrow">
              <Sparkles size={16} />
              <span>پایان دوباره‌کاری در پروژه‌های وب و نرم‌افزار</span>
            </div>

            <h1 className="hero-title">
              تبدیل بریف آشفته مشتری به{" "}
              <span className="hero-title-highlight">Scope رسمی و تاییدشده</span>
            </h1>

            <p className="hero-subtitle">
              فضای کاری هوشمند برای مدیران آژانس و فریلنسرهای حرفه‌ای.
              ورودی‌های ناقص کارفرما را به نیازمندی‌های شفاف تبدیل کنید، ابهامات را پیش از کدنویسی بسنجید و تاییدیه رسمی مشتری را ثبت نمایید.
            </p>

            <div className="hero-actions">
              <Link href="/projects" className="btn btn-primary btn-lg">
                ورود به داشبورد پروژه‌ها
                <ArrowLeft size={20} />
              </Link>
              <a href="#workflow" className="btn btn-secondary btn-lg">
                مشاهده زنجیره تبدیل (Workflow)
              </a>
            </div>

            {/* Quick Metrics Bar */}
            <div className="badge badge-indigo" style={{ padding: '0.625rem 1.25rem', fontSize: '0.875rem' }}>
              ✓ کنترل کامل چندمستأجری • ایزولاسیون کامل دیتابیس • عدم وابستگی به ارائه‌دهنده (No Lock-in)
            </div>
          </div>
        </section>

        {/* Interactive Workflow Section */}
        <section id="workflow" className="workflow-section">
          <div className="section-container">
            <div className="section-header">
              <span className="badge badge-cyan" style={{ marginBottom: '0.5rem' }}>چرخه حیات پروژه</span>
              <h2 className="section-title">چگونه Aria مانع از Scope Creep می‌شود؟</h2>
              <p className="section-subtitle">از پیام‌های نامنظم پیام‌رسان‌ها تا تاییدیه حقوقی در یک چرخه شفاف ۵ مرحله‌ای</p>
            </div>

            {/* Steps grid */}
            <div className="workflow-steps-grid" style={{ marginBottom: '2.5rem' }}>
              {workflowSteps.map((step, index) => (
                <div 
                  key={step.id} 
                  className={`workflow-step-card ${activeTab === index ? 'active' : ''}`}
                  style={{ 
                    cursor: 'pointer',
                    borderColor: activeTab === index ? 'hsl(var(--primitive-color-cyan-400))' : undefined 
                  }}
                  onClick={() => setActiveTab(index)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') setActiveTab(index); }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div className="workflow-step-num">{index + 1}</div>
                    <span className="badge">{step.badge}</span>
                  </div>
                  <h3 className="workflow-step-title">{step.title}</h3>
                  <p className="workflow-step-desc">{step.subtitle}</p>
                </div>
              ))}
            </div>

            {/* Active Step Preview Canvas */}
            <div className="card" style={{ borderColor: 'hsl(var(--color-primary))', background: 'hsl(var(--color-surface))' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div className="brand-logo-icon" style={{ inlineSize: '2.25rem', blockSize: '2.25rem', fontSize: '1rem' }}>
                    {activeTab + 1}
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.25rem' }}>{workflowSteps[activeTab].title}</h3>
                    <p style={{ margin: 0, color: 'hsl(var(--color-text-muted))', fontSize: '0.875rem' }}>{workflowSteps[activeTab].desc}</p>
                  </div>
                </div>
                <span className="badge badge-cyan">{workflowSteps[activeTab].badge}</span>
              </div>

              {/* Mock Terminal / Code Preview */}
              <div style={{ 
                background: 'hsl(var(--primitive-color-neutral-900))', 
                borderRadius: 'var(--primitive-radius-md)', 
                padding: '1.25rem',
                border: 'var(--border-width-default) solid hsl(var(--color-border))',
                fontFamily: 'monospace',
                fontSize: '0.9375rem',
                lineHeight: 1.8,
                whiteSpace: 'pre-wrap',
                color: 'hsl(var(--primitive-color-neutral-100))'
              }}>
                {workflowSteps[activeTab].previewText}
              </div>
            </div>
          </div>
        </section>

        {/* Core Value Pillars */}
        <section id="features" className="features-section">
          <div className="section-container">
            <div className="section-header">
              <span className="badge badge-indigo" style={{ marginBottom: '0.5rem' }}>چرا Aria AI؟</span>
              <h2 className="section-title">ساخته‌شده برای نیاز واقعی آژانس‌ها</h2>
              <p className="section-subtitle">مسئله کندی کدنویسی نیست؛ مسئله اتلاف زمان در دوباره‌کاری و سوءتفاهم با مشتری است.</p>
            </div>

            <div className="features-grid">
              <div className="feature-card">
                <div className="feature-icon-wrapper">
                  <ShieldCheck size={28} />
                </div>
                <h3 className="feature-title">ضد Scope Creep</h3>
                <p className="feature-desc">
                  هیچ تغییری بدون ثبت رسمی و مقایسه با اسنپ‌شات اولیه پذیرفته نمی‌شود. مشتری متوجه اثر تغییر روی زمان و هزینه خواهد شد.
                </p>
              </div>

              <div className="feature-card">
                <div className="feature-icon-wrapper">
                  <FileSearch size={28} />
                </div>
                <h3 className="feature-title">کشف زودهنگام گپ‌ها (Gaps)</h3>
                <p className="feature-desc">
                  قوانین نقادانه هوش مصنوعی تمامی ابهامات پنهان در قرارداد و نیازمندی‌ها را پیش از استارت توسعه استخراج می‌کنند.
                </p>
              </div>

              <div className="feature-card">
                <div className="feature-icon-wrapper">
                  <Layers size={28} />
                </div>
                <h3 className="feature-title">ردیابی کامل (Traceability)</h3>
                <p className="feature-desc">
                  هر نیازمندی دقیقاً به متن بریف یا چت اولیه کارفرما متصل است؛ بنابراین منشأ هر تصمیم کاملاً شفاف و مستند است.
                </p>
              </div>

              <div className="feature-card">
                <div className="feature-icon-wrapper">
                  <Lock size={28} />
                </div>
                <h3 className="feature-title">امنیت چندمستأجری و RLS</h3>
                <p className="feature-desc">
                  داده‌های پروژه‌ها با ایزولاسیون سخت‌گیرانه در سطح پایگاه‌داده و توکن‌های معتبر ایمن‌سازی شده‌اند.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section style={{ 
          paddingBlock: 'var(--primitive-space-12)', 
          paddingInline: 'var(--responsive-gutter)',
          background: 'hsl(var(--color-surface))',
          borderBlockStart: 'var(--border-width-default) solid hsl(var(--color-border))'
        }}>
          <div className="section-container" style={{ textAlign: 'center', maxWidth: '40rem' }}>
            <h2 style={{ fontSize: '2rem', marginBlockEnd: '1rem' }}>آماده تحویل شفاف‌تر پروژه‌ها هستید؟</h2>
            <p style={{ color: 'hsl(var(--color-text-muted))', marginBlockEnd: '2rem', lineHeight: 1.7 }}>
              همین حالا وارد فضای کاری Aria شوید و اولین پروژه خود را تعریف کنید.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link href="/projects" className="btn btn-primary btn-lg">
                ورود به پروژه‌ها
                <ArrowLeft size={18} />
              </Link>
              <Link href="/auth/signup" className="btn btn-secondary btn-lg">
                ثبت‌نام حساب کاربری
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p style={{ margin: 0 }}>
          © ۱۴۰۵ تمامی حقوق محفوظ است — فضای کاری هوشمند Aria AI برای آژانس‌های توسعه وب
        </p>
      </footer>
    </div>
  );
}
