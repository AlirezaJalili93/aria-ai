"use client"

import { useState } from "react"
import {
  FileCheck,
  ShieldCheck,
  Printer,
  User,
  Building,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  FileSignature,
  Loader2,
  GitPullRequest,
  Send,
  Clock
} from "lucide-react"

import {
  signScopeAction,
  submitScopeChangeRequestAction,
  type ScopeChangeRequest,
  type ScopeSignature
} from "./actions"

export function ScopeSignoff({
  scopeId,
  initialSignature = null,
  initialChangeRequests = []
}: Readonly<{
  scopeId: string
  initialSignature?: ScopeSignature | null
  initialChangeRequests?: ScopeChangeRequest[]
}>) {
  const [activeAction, setActiveAction] = useState<"sign" | "change-request">("sign")

  // Signature state
  const [signerName, setSignerName] = useState(initialSignature?.signerName ?? "")
  const [signerRole, setSignerRole] = useState(initialSignature?.signerRole ?? "")
  const [organization, setOrganization] = useState(initialSignature?.organization ?? "")
  const [agreed, setAgreed] = useState(Boolean(initialSignature))
  const [isSubmittingSig, setIsSubmittingSig] = useState(false)
  const [sigErrorMsg, setSigErrorMsg] = useState<string | null>(null)
  const [signature, setSignature] = useState<ScopeSignature | null>(initialSignature)

  // Change request state
  const [requesterName, setRequesterName] = useState("")
  const [requesterRole, setRequesterRole] = useState("")
  const [changeCategory, setChangeCategory] = useState("scope_items")
  const [requestedChanges, setRequestedChanges] = useState("")
  const [isSubmittingChange, setIsSubmittingChange] = useState(false)
  const [changeSuccessMsg, setChangeSuccessMsg] = useState<string | null>(null)
  const [changeErrorMsg, setChangeErrorMsg] = useState<string | null>(null)
  const [changeRequests, setChangeRequests] = useState<ScopeChangeRequest[]>(initialChangeRequests)

  const handleSign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!signerName || !signerRole || !agreed) return

    setIsSubmittingSig(true)
    setSigErrorMsg(null)

    const result = await signScopeAction({
      scopeId,
      signerName,
      signerRole,
      organization: organization || undefined
    })

    setIsSubmittingSig(false)

    if (result.success && result.signature) {
      setSignature(result.signature)
    } else {
      setSigErrorMsg(result.message ?? "ثبت امضا ناموفق بود.")
    }
  }

  const handleRequestChange = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!requesterName || !requesterRole || !requestedChanges.trim()) return

    setIsSubmittingChange(true)
    setChangeErrorMsg(null)
    setChangeSuccessMsg(null)

    const result = await submitScopeChangeRequestAction({
      scopeId,
      requesterName,
      requesterRole,
      category: changeCategory,
      requestedChanges: requestedChanges.trim()
    })

    setIsSubmittingChange(false)

    if (result.success && result.changeRequest) {
      setChangeRequests((prev) => [result.changeRequest!, ...prev])
      setChangeSuccessMsg("درخواست اصلاحات با موفقیت ثبت شد و به مدیر پروژه اطلاع‌رسانی گردید.")
      setRequestedChanges("")
    } else {
      setChangeErrorMsg(result.message ?? "ثبت درخواست تغییر با خطا مواجه شد.")
    }
  }

  const formattedDate = signature?.signedAt
    ? new Date(signature.signedAt).toLocaleDateString("fa-IR", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
      })
    : ""

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
            <FileSignature className="icon-xs" aria-hidden="true" />
            <span>سند رسمی فنی</span>
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

        {changeRequests.length > 0 && (
          <section className="doc-section">
            <h3>۴. سوابق درخواست‌های اصلاحی کارفرما ({changeRequests.length})</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.5rem" }}>
              {changeRequests.map((cr) => (
                <div
                  key={cr.id}
                  style={{
                    padding: "0.75rem 1rem",
                    borderRadius: "var(--primitive-radius-md, 8px)",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid var(--primitive-color-border-subtle, rgba(255,255,255,0.1))"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                    <strong>{cr.requesterName} ({cr.requesterRole})</strong>
                    <span style={{ fontSize: "0.8rem", color: "var(--primitive-color-text-muted)" }}>
                      <Clock className="icon-xs" style={{ display: "inline", verticalAlign: "middle", marginLeft: "4px" }} aria-hidden="true" />
                      {new Date(cr.createdAt).toLocaleDateString("fa-IR")}
                    </span>
                  </div>
                  <p style={{ margin: "0.25rem 0", color: "var(--primitive-color-text-body)" }}>
                    {cr.requestedChanges}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="doc-signature-section">
          {signature ? (
            <div className="signature-success-box" role="status">
              <div className="signature-success-icon">
                <FileCheck className="icon-lg text-primary" aria-hidden="true" />
              </div>
              <h3>سند با موفقیت تأیید و امضا شد</h3>
              <p>این سند دارای ارزش استنادی فنی بوده و در بایگانی دائمی پروژه ثبت گردید.</p>
              <dl className="signature-details">
                <div>
                  <dt>امضاکننده:</dt>
                  <dd>{signature.signerName} ({signature.signerRole})</dd>
                </div>
                {signature.organization && (
                  <div>
                    <dt>سازمان / شرکت:</dt>
                    <dd>{signature.organization}</dd>
                  </div>
                )}
                <div>
                  <dt>زمان امضا:</dt>
                  <dd>{formattedDate}</dd>
                </div>
                <div>
                  <dt>کد اعتبارسنجی امنیتی:</dt>
                  <dd><code>{signature.verificationCode}</code></dd>
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
            <div>
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.25rem" }}>
                <button
                  type="button"
                  className={`button ${activeAction === "sign" ? "button--primary" : "button--secondary"}`}
                  onClick={() => setActiveAction("sign")}
                >
                  <Sparkles className="icon-xs" aria-hidden="true" />
                  <span>تأیید و امضای نهایی</span>
                </button>
                <button
                  type="button"
                  className={`button ${activeAction === "change-request" ? "button--primary" : "button--secondary"}`}
                  onClick={() => setActiveAction("change-request")}
                >
                  <GitPullRequest className="icon-xs" aria-hidden="true" />
                  <span>درخواست بازبینی یا تغییر</span>
                </button>
              </div>

              {activeAction === "sign" ? (
                <form className="signature-form" onSubmit={handleSign}>
                  <h3>تأییدیه و امضای دیجیتال کارفرما</h3>
                  <p className="signature-form__intro">
                    جهت ابلاغ شروع رسمی پروژه، مشخصات خود را وارد نموده و سند را امضا فرمایید:
                  </p>

                  {sigErrorMsg && (
                    <div className="form-feedback form-feedback--error" role="alert">
                      {sigErrorMsg}
                    </div>
                  )}

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
                    disabled={!signerName || !signerRole || !agreed || isSubmittingSig}
                  >
                    {isSubmittingSig ? (
                      <>
                        <Loader2 className="icon-xs animate-spin" aria-hidden="true" />
                        <span>در حال ثبت امن امضا...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="icon-xs" aria-hidden="true" />
                        <span>امضا و تأیید نهایی سند محدوده کار</span>
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <form className="signature-form" onSubmit={handleRequestChange}>
                  <h3>ثبت بازخورد یا درخواست تغییر در سند</h3>
                  <p className="signature-form__intro">
                    در صورتی که بندی از سند نیاز به اصلاح دارد، موارد را ذکر کنید تا در نسخه بعدی اعمال گردد:
                  </p>

                  {changeSuccessMsg && (
                    <div style={{ padding: "0.75rem", backgroundColor: "rgba(34, 197, 94, 0.1)", border: "1px solid #22c55e", borderRadius: "8px", color: "#22c55e", marginBottom: "1rem" }} role="status">
                      {changeSuccessMsg}
                    </div>
                  )}

                  {changeErrorMsg && (
                    <div className="form-feedback form-feedback--error" role="alert">
                      {changeErrorMsg}
                    </div>
                  )}

                  <div className="form-grid">
                    <div className="field-group">
                      <label htmlFor="change-req-name">
                        <User className="icon-xs" aria-hidden="true" />
                        <span>نام و نام خانوادگی درخواست‌دهنده:</span>
                      </label>
                      <input
                        id="change-req-name"
                        type="text"
                        className="text-field"
                        required
                        value={requesterName}
                        onChange={(e) => setRequesterName(e.target.value)}
                        placeholder="مثال: علیرضا محمدی"
                      />
                    </div>

                    <div className="field-group">
                      <label htmlFor="change-req-role">
                        <span>سمت سازمانی:</span>
                      </label>
                      <input
                        id="change-req-role"
                        type="text"
                        className="text-field"
                        required
                        value={requesterRole}
                        onChange={(e) => setRequesterRole(e.target.value)}
                        placeholder="مثال: مدیر محصول کارفرما"
                      />
                    </div>

                    <div className="field-group">
                      <label htmlFor="change-req-cat">
                        <span>بخش نیازمند اصلاح:</span>
                      </label>
                      <select
                        id="change-req-cat"
                        className="text-field"
                        value={changeCategory}
                        onChange={(e) => setChangeCategory(e.target.value)}
                      >
                        <option value="scope_items">اقلام درون محدوده (In-Scope)</option>
                        <option value="out_of_scope">موارد خارج از محدوده (Out-of-Scope)</option>
                        <option value="timeline">زمان‌بندی و مراحل تحویل</option>
                        <option value="technical">ملاحظات فنی و امنیتی</option>
                      </select>
                    </div>
                  </div>

                  <div className="field-group" style={{ marginTop: "1rem" }}>
                    <label htmlFor="change-req-desc">
                      <span>توضیحات و جزئیات تغییرات پیشنهادی:</span>
                    </label>
                    <textarea
                      id="change-req-desc"
                      className="text-area"
                      rows={4}
                      required
                      value={requestedChanges}
                      onChange={(e) => setRequestedChanges(e.target.value)}
                      placeholder="توضیح دهید کدام مورد باید حذف، اضافه یا تغییر داده شود..."
                    />
                  </div>

                  <button
                    type="submit"
                    className="button button--primary button--full"
                    disabled={!requesterName || !requesterRole || !requestedChanges.trim() || isSubmittingChange}
                    style={{ marginTop: "1rem" }}
                  >
                    {isSubmittingChange ? (
                      <>
                        <Loader2 className="icon-xs animate-spin" aria-hidden="true" />
                        <span>در حال ارسال درخواست...</span>
                      </>
                    ) : (
                      <>
                        <Send className="icon-xs" aria-hidden="true" />
                        <span>ارسال درخواست تغییرات به تیم پروژه</span>
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
