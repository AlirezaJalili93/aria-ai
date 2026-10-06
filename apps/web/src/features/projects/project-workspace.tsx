"use client"

import { useState } from "react"
import Link from "next/link"
import {
  FileText,
  ListChecks,
  HelpCircle,
  FileSignature,
  Sparkles,
  CheckCircle2,
  Share2,
  AlertCircle,
  Layers,
  ArrowUpRight
} from "lucide-react"

import { saveBriefAction } from "./context-actions"
import type { ContextSourceItem, Project } from "./types"

type TabKey = "context" | "requirements" | "gaps" | "scope"

type WorkspaceProps = Readonly<{
  project: Project
  initialSources?: readonly ContextSourceItem[]
}>

const activeClarifications: Readonly<Record<string, string>> = {
  gap_1: "درگاه واسط (زرین‌پال)",
  gap_2: "نسخه فاز اول بدون پیامک"
}

export function ProjectWorkspace({ project, initialSources = [] }: WorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("context")
  const [briefText, setBriefText] = useState("")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [saveFeedback, setSaveFeedback] = useState<string | null>(null)
  const [sourcesList, setSourcesList] = useState<readonly ContextSourceItem[]>(initialSources)

  const handleSaveBrief = async () => {
    if (!briefText.trim()) return
    setIsAnalyzing(true)
    setSaveFeedback(null)
    try {
      const res = await saveBriefAction(project.id, briefText)
      if (res.success && res.source) {
        setSourcesList((prev) => [res.source!, ...prev])
        setBriefText("")
        setSaveFeedback("بریف با موفقیت در پایگاه داده ثبت شد.")
      } else {
        setSaveFeedback(res.message ?? "خطا در ثبت بریف.")
      }
    } catch {
      setSaveFeedback("خطای اتصال به سرور.")
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="project-workspace">
      <div className="workspace-tabs-wrapper">
        <nav className="workspace-tabs" aria-label="بخش‌های محیط کاری پروژه">
          <button
            type="button"
            className={`workspace-tab ${activeTab === "context" ? "workspace-tab--active" : ""}`}
            onClick={() => setActiveTab("context")}
          >
            <FileText className="icon-sm" aria-hidden="true" />
            <span>Context (زمینه)</span>
          </button>
          <button
            type="button"
            className={`workspace-tab ${activeTab === "requirements" ? "workspace-tab--active" : ""}`}
            onClick={() => setActiveTab("requirements")}
          >
            <ListChecks className="icon-sm" aria-hidden="true" />
            <span>Requirements (نیازمندی‌ها)</span>
          </button>
          <button
            type="button"
            className={`workspace-tab ${activeTab === "gaps" ? "workspace-tab--active" : ""}`}
            onClick={() => setActiveTab("gaps")}
          >
            <HelpCircle className="icon-sm" aria-hidden="true" />
            <span>Gaps (ابهامات)</span>
          </button>
          <button
            type="button"
            className={`workspace-tab ${activeTab === "scope" ? "workspace-tab--active" : ""}`}
            onClick={() => setActiveTab("scope")}
          >
            <FileSignature className="icon-sm" aria-hidden="true" />
            <span>Scope (سند محدوده)</span>
          </button>
        </nav>
      </div>

      <div className="workspace-content">
        {activeTab === "context" && (
          <section className="workspace-panel" aria-labelledby="context-panel-heading">
            <div className="panel-header">
              <div>
                <h3 id="context-panel-heading">ورودی‌های اولیه و متن بریف</h3>
                <p className="panel-subtitle">
                  توضیحات و فایل‌های گفتگو با کارفرما را وارد کنید تا هوش مصنوعی Aria آن‌ها را تحلیل نماید.
                </p>
              </div>
            </div>

            <div className="brief-input-box">
              <label htmlFor="brief-text-field" className="field-label">
                متن بریف یا خلاصه گفتگو:
              </label>
              <textarea
                id="brief-text-field"
                className="text-area"
                rows={4}
                value={briefText}
                onChange={(e) => setBriefText(e.target.value)}
                placeholder="مثال: کارفرما درخواست یک پلتفرم فروشگاهی اختصاصی برای فروش محصولات دیجیتال دارد. احراز هویت با شماره موبایل و اتصال به درگاه بانکی الزامی است..."
              />
              <div className="brief-input-actions">
                <button
                  type="button"
                  className="button button--primary"
                  onClick={handleSaveBrief}
                  disabled={!briefText.trim() || isAnalyzing}
                >
                  {isAnalyzing ? (
                    <span>در حال استخراج و ساختاربندی…</span>
                  ) : (
                    <>
                      <Sparkles className="icon-xs" aria-hidden="true" />
                      <span>ثبت و تحلیل بریف</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="sources-list-section">
              <h4>سورس‌های ثبت شده در این پروژه</h4>
              {saveFeedback && (
                <div style={{ color: "hsl(var(--color-primary-default))", fontSize: "var(--font-size-sm)", marginBottom: "var(--primitive-space-2)" }}>
                  {saveFeedback}
                </div>
              )}
              {sourcesList.length === 0 ? (
                <div className="empty-mini-state">
                  <p>هنوز سورس یا متنی ثبت نشده است. اولین بریف را در کادر بالا وارد کنید.</p>
                </div>
              ) : (
                <ul className="sources-list">
                  {sourcesList.map((source) => (
                    <li key={source.id} className="source-item" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--primitive-space-2)" }}>
                        <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
                        <span>{source.original_name ?? "سند متنی"}: {source.raw_text?.slice(0, 45) ?? ""}…</span>
                      </div>
                      <span className="badge badge--success" style={{ fontSize: "0.75rem" }}>{source.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}

        {activeTab === "requirements" && (
          <section className="workspace-panel" aria-labelledby="req-panel-heading">
            <div className="panel-header">
              <div>
                <h3 id="req-panel-heading">نیازمندی‌های استخراج شده</h3>
                <p className="panel-subtitle">
                  تفکیک نیازمندی‌های کاربردی و مشخصات فنی بر مبنای قرارداد معماری Aria AI.
                </p>
              </div>
            </div>

            <div className="req-columns-grid">
              <div className="req-column">
                <div className="req-column-title">
                  <Layers className="icon-xs text-primary" aria-hidden="true" />
                  <h4>نیازمندی‌های کاربردی (Functional)</h4>
                </div>
                <div className="req-cards">
                  <div className="req-card">
                    <div className="req-card__top">
                      <span className="req-tag req-tag--p1">اولویت اصلی</span>
                      <span className="req-id">REQ-01</span>
                    </div>
                    <p className="req-title">ثبت‌نام و ورود یکپارچه کاربران</p>
                    <p className="req-note">پشتیبانی از ورود ایمیل و اعتبارسنجی امن نشست.</p>
                  </div>
                  <div className="req-card">
                    <div className="req-card__top">
                      <span className="req-tag req-tag--p1">اولویت اصلی</span>
                      <span className="req-id">REQ-02</span>
                    </div>
                    <p className="req-title">کاتالوگ محصولات با فیلترینگ چندمعیاره</p>
                    <p className="req-note">جستجو بر اساس دسته‌بندی و دامنه قیمت به همراه صفحه‌بندی ایمن.</p>
                  </div>
                  <div className="req-card">
                    <div className="req-card__top">
                      <span className="req-tag req-tag--p2">اولویت متوسط</span>
                      <span className="req-id">REQ-03</span>
                    </div>
                    <p className="req-title">فرایند سبد خرید و ثبت نهایی سفارش</p>
                    <p className="req-note">محاسبه خودکار تخفیف و مالیات قبل از ورود به درگاه پرداخت.</p>
                  </div>
                </div>
              </div>

              <div className="req-column">
                <div className="req-column-title">
                  <Layers className="icon-xs text-secondary" aria-hidden="true" />
                  <h4>الزامات کیفی و امنیتی (Non-Functional)</h4>
                </div>
                <div className="req-cards">
                  <div className="req-card">
                    <div className="req-card__top">
                      <span className="req-tag req-tag--tech">استاندارد فرانت</span>
                      <span className="req-id">NFR-01</span>
                    </div>
                    <p className="req-title">طراحی RTL-First و دسترسی‌پذیری WCAG AA</p>
                    <p className="req-note">استفاده کامل از توکن‌های طراحی، کنتراست استاندارد و فونت بومی.</p>
                  </div>
                  <div className="req-card">
                    <div className="req-card__top">
                      <span className="req-tag req-tag--tech">پرفورمنس</span>
                      <span className="req-id">NFR-02</span>
                    </div>
                    <p className="req-title">زمان بارگذاری زیر ۱.۵ ثانیه</p>
                    <p className="req-note">بهینه‌سازی تصاویر و استفاده از کشینگ ابری در استیجینگ.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "gaps" && (
          <section className="workspace-panel" aria-labelledby="gaps-panel-heading">
            <div className="panel-header">
              <div>
                <h3 id="gaps-panel-heading">نقاط مبهم و سوالات شفاف‌سازی</h3>
                <p className="panel-subtitle">
                  این ابهامات باید قبل از قفل کردن محدوده نهایی کار با کارفرما شفاف شوند.
                </p>
              </div>
            </div>

            <div className="gap-items-list">
              <div className="gap-item">
                <div className="gap-item__badge">
                  <AlertCircle className="icon-sm text-warning" aria-hidden="true" />
                </div>
                <div className="gap-item__body">
                  <h4 className="gap-item__title">روش اتصال درگاه پرداخت بانکی</h4>
                  <p className="gap-item__desc">
                    در بریف مشخص نشده که آیا درگاه مستقیم بانکی (شاپرک/سداد) مد نظر است یا درگاه واسط پرداخت؟
                  </p>
                  <div className="gap-item__clarification">
                    <span className="clarification-label">تصمیم ثبت شده:</span>
                    <span className="clarification-val">{activeClarifications.gap_1}</span>
                  </div>
                </div>
              </div>

              <div className="gap-item">
                <div className="gap-item__badge">
                  <AlertCircle className="icon-sm text-warning" aria-hidden="true" />
                </div>
                <div className="gap-item__body">
                  <h4 className="gap-item__title">سیستم ارسال پیامک‌های اطلاع‌رسانی</h4>
                  <p className="gap-item__desc">
                    آیا ارسال پیامک وضعیت سفارش‌ها در این فاز الزامی است یا در فاز دوم پروژه پیاده‌سازی خواهد شد؟
                  </p>
                  <div className="gap-item__clarification">
                    <span className="clarification-label">تصمیم ثبت شده:</span>
                    <span className="clarification-val">{activeClarifications.gap_2}</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "scope" && (
          <section className="workspace-panel" aria-labelledby="scope-panel-heading">
            <div className="panel-header">
              <div>
                <h3 id="scope-panel-heading">سند محدوده کارفرما (Scope Document)</h3>
                <p className="panel-subtitle">
                  سند نهایی و مورد توافق جهت امضا و آغاز فاز اجرایی پروژه.
                </p>
              </div>
              <div className="panel-header-actions">
                <Link
                  className="button button--primary"
                  href={`/scope/${project.id}`}
                  target="_blank"
                >
                  <ArrowUpRight className="icon-xs" aria-hidden="true" />
                  <span>مشاهده پورتال امضای کارفرما</span>
                </Link>
              </div>
            </div>

            <div className="scope-document-preview">
              <div className="doc-watermark" aria-hidden="true">ARIA AI VERIFIED</div>
              <div className="doc-meta-row">
                <div>
                  <span className="doc-meta-label">عنوان سند:</span>
                  <strong>محدوده اجرایی و مشخصات فنی {project.title}</strong>
                </div>
                <div>
                  <span className="doc-meta-label">شناسه یکتا:</span>
                  <code className="doc-token">{project.id.slice(0, 13)}…</code>
                </div>
              </div>

              <div className="scope-split-view">
                <div className="scope-box scope-box--in">
                  <h4 className="scope-box-heading">
                    <CheckCircle2 className="icon-xs text-primary" aria-hidden="true" />
                    <span>محدوده داخل پروژه (In-Scope)</span>
                  </h4>
                  <ul>
                    <li>طراحی UI/UX کامل بر پایه دیزاین‌سیستم آریا و رعایت کامل RTL</li>
                    <li>احراز هویت ایمن کاربری و مدیریت نشست‌ها</li>
                    <li>کاتالوگ محصولات به همراه سبد خرید تعاملی</li>
                    <li>اتصال به درگاه واسط بانکی</li>
                  </ul>
                </div>

                <div className="scope-box scope-box--out">
                  <h4 className="scope-box-heading">
                    <AlertCircle className="icon-xs text-muted" aria-hidden="true" />
                    <span>خارج از تعهد فاز اول (Out-of-Scope)</span>
                  </h4>
                  <ul>
                    <li>اپلیکیشن موبایل بومی (iOS / Android)</li>
                    <li>سیستم چندزبانه و تسویه‌حساب ارزی بین‌المللی</li>
                    <li>ارسال پیامک انبوه تبلیغاتی</li>
                  </ul>
                </div>
              </div>

              <div className="scope-doc-footer">
                <p className="footer-note">
                  این سند برای دریافت تأییدیه رسمی به پورتال اختصاصی کارفرما ارسال شده است.
                </p>
                <Link
                  className="button button--secondary"
                  href={`/scope/${project.id}`}
                  target="_blank"
                >
                  <Share2 className="icon-xs" aria-hidden="true" />
                  <span>باز کردن لینک اشتراک‌گذاری کارفرما</span>
                </Link>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
