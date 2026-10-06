"use client"

import { useState } from "react"
import {
  CheckCircle2,
  FileCheck,
  ShieldCheck,
  Building,
  User,
  Printer,
  Sparkles,
  AlertTriangle,
  Lock
} from "lucide-react"

type ScopeSignoffProps = Readonly<{
  scopeId: string
}>

export function ScopeSignoff({ scopeId }: ScopeSignoffProps) {
  const [signerName, setSignerName] = useState("")
  const [signerRole, setSignerRole] = useState("")
  const [organization, setOrganization] = useState("")
  const [agreed, setAgreed] = useState(false)
  const [signedState, setSignedState] = useState<{
    signed: boolean
    timestamp?: string
    verificationCode?: string
  }>({ signed: false })

  const handleSign = (e: React.FormEvent) => {
    e.preventDefault()
    if (!signerName || !signerRole || !agreed) return

    const now = new Date()
    const verificationCode = `SIG-${scopeId.slice(0, 8).toUpperCase()}-${Math.floor(1000 + Math.random() * 9000)}`

    setSignedState({
      signed: true,
      timestamp: now.toLocaleDateString("fa-IR", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      }),
      verificationCode
    })
  }

  return (
    <div className="signoff-portal">
      <div className="signoff-banner">
        <div className="signoff-banner__icon">
          <ShieldCheck className="icon-md text-primary" aria-hidden="true" />
        </div>
        <div>
          <h2>پورتال رسمی تأیید و امضای سند محدوده کار (Scope Document)</h2>
          <p>
            این سند توسط موتور استخراج بریف Aria AI تولید و اعتبارسنجی شده است. لطفاً پیش از امضا، مفاد سند را بررسی فرمایید.
          </p>
        </div>
      </div>

      <div className="signoff-doc-card">
        <header className="doc-header">
          <div className="doc-header__badge">
            <Lock className="icon-xs" aria-hidden="true" />
            <span>سند رسمی محافظت‌شده</span>
          </div>
          <h1>سند محدوده اجرایی و مشخصات فنی پروژه</h1>
          <div className="doc-header__meta">
            <span>شناسه سند: <code>{scopeId}</code></span>
            <span>نسخه: ۱.۰.۰ (Final Draft)</span>
          </div>
        </header>

        <section className="doc-section">
          <h3>۱. خلاصه اهداف و اقلام تحویلی</h3>
          <p>
            توسعه پلتفرم دیجیتال با معماری مدرن، پشتیبانی کامل از استانداردهای واکنش‌گرا و تجربه کاربری راست‌به‌چپ (RTL-First). تحویل نهایی شامل فرانت‌اند وب، سیستم مدیریت دسترسی، و یکپارچه‌سازی با سرویس‌های ابری است.
          </p>
        </section>

        <section className="doc-section">
          <h3>۲. محدوده مورد تعهد (In-Scope Deliverables)</h3>
          <ul className="doc-checklist">
            <li>
              <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
              <span>طراحی و پیاده‌سازی رابط کاربری با تایپوگرافی ایران‌یکان و توکن‌های طراحی آریا</span>
            </li>
            <li>
              <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
              <span>پیاده‌سازی ماژول‌های احراز هویت امن و ثبت نشست‌های کاربر</span>
            </li>
            <li>
              <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
              <span>سیستم مدیریت محتوا و لیست داینامیک پروژه‌ها</span>
            </li>
            <li>
              <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
              <span>پوشش تست‌های اعتبارسنجی و رعایت کامل اصول دسترسی‌پذیری WCAG AA</span>
            </li>
          </ul>
        </section>

        <section className="doc-section">
          <h3>۳. موارد خارج از تعهد فاز جاری (Out-of-Scope)</h3>
          <ul className="doc-checklist doc-checklist--out">
            <li>
              <AlertTriangle className="icon-xs text-muted" aria-hidden="true" />
              <span>توسعه اپلیکیشن‌های بومی موبایل برای بازارهای ثالث در این فاز گنجانده نشده است.</span>
            </li>
            <li>
              <AlertTriangle className="icon-xs text-muted" aria-hidden="true" />
              <span>سفارشی‌سازی خارج از پروتکل‌های مصوب نیازمند الحاقیه جداگانه خواهد بود.</span>
            </li>
          </ul>
        </section>

        <section className="doc-signature-section">
          {signedState.signed ? (
            <div className="signature-success-box" role="status">
              <div className="signature-success-icon">
                <FileCheck className="icon-lg text-primary" aria-hidden="true" />
              </div>
              <h3>سند با موفقیت تأیید و امضا شد</h3>
              <p>این سند دارای ارزش استنادی فنی بوده و در بایگانی دائمی پروژه ثبت گردید.</p>
              <dl className="signature-details">
                <div>
                  <dt>امضاکننده:</dt>
                  <dd>{signerName} ({signerRole})</dd>
                </div>
                {organization && (
                  <div>
                    <dt>سازمان / شرکت:</dt>
                    <dd>{organization}</dd>
                  </div>
                )}
                <div>
                  <dt>زمان امضا:</dt>
                  <dd>{signedState.timestamp}</dd>
                </div>
                <div>
                  <dt>کد اعتبارسنجی امنیتی:</dt>
                  <dd><code>{signedState.verificationCode}</code></dd>
                </div>
              </dl>
              <div className="signature-actions">
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => window.print()}
                >
                  <Printer className="icon-xs" aria-hidden="true" />
                  <span>چاپ نسخه رسمی سند</span>
                </button>
              </div>
            </div>
          ) : (
            <form className="signature-form" onSubmit={handleSign}>
              <h3>تأییدیه و امضای دیجیتال کارفرما</h3>
              <p className="signature-form__intro">
                جهت ابلاغ شروع رسمی پروژه، مشخصات خود را وارد نموده و سند را امضا فرمایید:
              </p>

              <div className="form-grid">
                <div className="field-group">
                  <label htmlFor="signer-name">
                    <User className="icon-xs" aria-hidden="true" />
                    <span>نام و نام خانوادگی امضاکننده:</span>
                  </label>
                  <input
                    id="signer-name"
                    type="text"
                    className="text-field"
                    required
                    value={signerName}
                    onChange={(e) => setSignerName(e.target.value)}
                    placeholder="مثال: علیرضا محمدی"
                  />
                </div>

                <div className="field-group">
                  <label htmlFor="signer-role">
                    <span>سمت / مسئولیت سازمانی:</span>
                  </label>
                  <input
                    id="signer-role"
                    type="text"
                    className="text-field"
                    required
                    value={signerRole}
                    onChange={(e) => setSignerRole(e.target.value)}
                    placeholder="مثال: مدیر فنی / کارفرمای پروژه"
                  />
                </div>

                <div className="field-group">
                  <label htmlFor="signer-org">
                    <Building className="icon-xs" aria-hidden="true" />
                    <span>نام شرکت یا سازمان (اختیاری):</span>
                  </label>
                  <input
                    id="signer-org"
                    type="text"
                    className="text-field"
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    placeholder="مثال: شرکت توسعه نوآوری آریا"
                  />
                </div>
              </div>

              <div className="checkbox-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    required
                    checked={agreed}
                    onChange={(e) => setAgreed(e.target.checked)}
                  />
                  <span>
                    مفاد این سند، اقلام تحویلی و موارد خارج از تعهد را مطالعه نموده و مورد تأیید است.
                  </span>
                </label>
              </div>

              <button
                type="submit"
                className="button button--primary button--full"
                disabled={!signerName || !signerRole || !agreed}
              >
                <Sparkles className="icon-xs" aria-hidden="true" />
                <span>امضا و تأیید نهایی سند محدوده کار</span>
              </button>
            </form>
          )}
        </section>
      </div>
    </div>
  )
}
