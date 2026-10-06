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
  ArrowUpRight,
  Plus,
  Check,
} from "lucide-react"

import { saveBriefAction } from "./context-actions"
import type { ContextSourceItem, Project } from "./types"

type TabKey = "context" | "requirements" | "gaps" | "scope"

type WorkspaceProps = Readonly<{
  project: Project
  initialSources?: readonly ContextSourceItem[]
}>

type RequirementItem = {
  id: string
  type: "functional" | "non-functional"
  priority: "p1" | "p2" | "tech"
  priorityLabel: string
  title: string
  note: string
}

type GapItem = {
  id: string
  title: string
  description: string
  decision: string | null
  status: "open" | "resolved"
}

const defaultRequirements: RequirementItem[] = [
  {
    id: "REQ-01",
    type: "functional",
    priority: "p1",
    priorityLabel: "اولویت اصلی",
    title: "ثبت‌نام و ورود یکپارچه کاربران",
    note: "پشتیبانی از ورود ایمیل و اعتبارسنجی امن نشست."
  },
  {
    id: "REQ-02",
    type: "functional",
    priority: "p1",
    priorityLabel: "اولویت اصلی",
    title: "کاتالوگ محصولات با فیلترینگ چندمعیاره",
    note: "جستجو بر اساس دسته‌بندی و دامنه قیمت به همراه صفحه‌بندی ایمن."
  },
  {
    id: "REQ-03",
    type: "functional",
    priority: "p2",
    priorityLabel: "اولویت متوسط",
    title: "فرایند سبد خرید و ثبت نهایی سفارش",
    note: "محاسبه خودکار تخفیف و مالیات قبل از ورود به درگاه پرداخت."
  },
  {
    id: "NFR-01",
    type: "non-functional",
    priority: "tech",
    priorityLabel: "استاندارد فرانت",
    title: "طراحی RTL-First و دسترسی‌پذیری WCAG AA",
    note: "استفاده کامل از توکن‌های طراحی، کنتراست استاندارد و فونت بومی."
  },
  {
    id: "NFR-02",
    type: "non-functional",
    priority: "tech",
    priorityLabel: "پرفورمنس",
    title: "زمان بارگذاری زیر ۱.۵ ثانیه",
    note: "بهینه‌سازی تصاویر و استفاده از کشینگ ابری در استیجینگ."
  }
]

const defaultGaps: GapItem[] = [
  {
    id: "gap_1",
    title: "روش اتصال درگاه پرداخت بانکی",
    description: "در بریف مشخص نشده که آیا درگاه مستقیم بانکی (شاپرک/سداد) مد نظر است یا درگاه واسط پرداخت؟",
    decision: "درگاه واسط (زرین‌پال)",
    status: "resolved"
  },
  {
    id: "gap_2",
    title: "سیستم ارسال پیامک‌های اطلاع‌رسانی",
    description: "آیا ارسال پیامک وضعیت سفارش‌ها در این فاز الزامی است یا در فاز دوم پروژه پیاده‌سازی خواهد شد؟",
    decision: "نسخه فاز اول بدون پیامک",
    status: "resolved"
  },
  {
    id: "gap_3",
    title: "سطوح دسترسی و نقش‌های کاربران پنل مدیریت",
    description: "آیا نیاز به تفکیک نقش‌های حسابدار، انباردار و پشتیبان در این فاز وجود دارد یا تک‌نقش مدیر کافی است؟",
    decision: null,
    status: "open"
  }
]

export function ProjectWorkspace({ project, initialSources = [] }: WorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("context")
  const [briefText, setBriefText] = useState("")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [saveFeedback, setSaveFeedback] = useState<string | null>(null)
  const [sourcesList, setSourcesList] = useState<readonly ContextSourceItem[]>(initialSources)

  // Requirements state
  const [requirements, setRequirements] = useState<RequirementItem[]>(defaultRequirements)
  const [showAddReq, setShowAddReq] = useState(false)
  const [newReqTitle, setNewReqTitle] = useState("")
  const [newReqNote, setNewReqNote] = useState("")
  const [newReqType, setNewReqType] = useState<"functional" | "non-functional">("functional")
  const [newReqPriority, setNewReqPriority] = useState<"p1" | "p2" | "tech">("p1")
  const [extractingReqs, setExtractingReqs] = useState(false)

  // Gaps state
  const [gaps, setGaps] = useState<GapItem[]>(defaultGaps)
  const [activeEditingGap, setActiveEditingGap] = useState<string | null>(null)
  const [gapDecisionInput, setGapDecisionInput] = useState("")
  const [showAddGap, setShowAddGap] = useState(false)
  const [newGapTitle, setNewGapTitle] = useState("")
  const [newGapDesc, setNewGapDesc] = useState("")

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

  const handleAutoExtractRequirements = () => {
    setExtractingReqs(true)
    setTimeout(() => {
      // Simulate intelligent requirement extraction from context sources
      const allText = sourcesList.map((s) => s.raw_text ?? "").join(" ") + " " + briefText
      const extracted: RequirementItem[] = []

      if (allText.includes("چت") || allText.includes("پشتیبانی") || allText.includes("تیکت")) {
        extracted.push({
          id: `REQ-AUTO-${Date.now() % 1000}`,
          type: "functional",
          priority: "p1",
          priorityLabel: "اولویت اصلی",
          title: "سیستم هوشمند تیکتینگ و گفتگوی آنلاین مشتریان",
          note: "پاسخ‌دهی آنی با پشتیبانی از صف انتظار و تاریخچه پیام‌ها بر اساس بریف."
        })
      }
      if (allText.includes("درگاه") || allText.includes("پرداخت") || allText.includes("فروشگاه")) {
        extracted.push({
          id: `REQ-AUTO-${(Date.now() + 1) % 1000}`,
          type: "functional",
          priority: "p1",
          priorityLabel: "اولویت اصلی",
          title: "یکپارچه‌سازی درگاه پرداخت شاپرک با بازگشت امن",
          note: "ثبت کد پیگیری بانکی و تاییدیه خودکار تراکنش‌ها."
        })
      }
      if (allText.includes("امنیت") || allText.includes("احراز") || allText.includes("موبایل")) {
        extracted.push({
          id: `NFR-AUTO-${(Date.now() + 2) % 1000}`,
          type: "non-functional",
          priority: "tech",
          priorityLabel: "امنیت داده",
          title: "رمزنگاری End-to-End و احراز هویت دومرحله‌ای",
          note: "رعایت الزامات امنیتی افتا و ذخیره‌سازی هش‌شده اطلاعات هویتی."
        })
      }

      if (extracted.length > 0) {
        setRequirements((prev) => [...extracted, ...prev])
      } else {
        // Add a general extracted item
        setRequirements((prev) => [
          {
            id: `REQ-AUTO-${Date.now() % 1000}`,
            type: "functional",
            priority: "p1",
            priorityLabel: "استخراج‌شده",
            title: "مدیریت فرم‌ها و اعتبارسنجی ورودی‌های کاربر",
            note: "استخراج شده از مستندات بریف و استانداردهای طراحی سیستم."
          },
          ...prev
        ])
      }
      setExtractingReqs(false)
      setActiveTab("requirements")
    }, 600)
  }

  const handleAddRequirement = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newReqTitle.trim()) return

    const priorityLabels: Record<string, string> = {
      p1: "اولویت اصلی",
      p2: "اولویت متوسط",
      tech: "استاندارد فنی"
    }

    const newItem: RequirementItem = {
      id: newReqType === "functional" ? `REQ-${requirements.length + 1}` : `NFR-${requirements.length + 1}`,
      type: newReqType,
      priority: newReqPriority,
      priorityLabel: priorityLabels[newReqPriority] ?? "عادی",
      title: newReqTitle.trim(),
      note: newReqNote.trim() || "توضیحات تکمیلی توسط راهبر پروژه ثبت شد."
    }

    setRequirements((prev) => [newItem, ...prev])
    setNewReqTitle("")
    setNewReqNote("")
    setShowAddReq(false)
  }

  const handleResolveGap = (gapId: string) => {
    if (!gapDecisionInput.trim()) return
    setGaps((prev) =>
      prev.map((g) => (g.id === gapId ? { ...g, decision: gapDecisionInput.trim(), status: "resolved" } : g))
    )
    setActiveEditingGap(null)
    setGapDecisionInput("")
  }

  const handleAddGap = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newGapTitle.trim()) return
    const newGap: GapItem = {
      id: `gap_${Date.now()}`,
      title: newGapTitle.trim(),
      description: newGapDesc.trim() || "این موضوع نیاز به تایید نهایی کارفرما قبل از پیاده‌سازی دارد.",
      decision: null,
      status: "open"
    }
    setGaps((prev) => [newGap, ...prev])
    setNewGapTitle("")
    setNewGapDesc("")
    setShowAddGap(false)
  }

  const functionalReqs = requirements.filter((r) => r.type === "functional")
  const nonFunctionalReqs = requirements.filter((r) => r.type === "non-functional")

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
            <span>Gaps (ابهام‌ها)</span>
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
              <div className="brief-input-actions" style={{ display: "flex", gap: "var(--primitive-space-3)", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="button button--primary"
                  onClick={handleSaveBrief}
                  disabled={!briefText.trim() || isAnalyzing}
                >
                  {isAnalyzing ? (
                    <span>در حال ذخیره در پایگاه داده…</span>
                  ) : (
                    <>
                      <Sparkles className="icon-xs" aria-hidden="true" />
                      <span>ثبت و تحلیل بریف</span>
                    </>
                  )}
                </button>
                {sourcesList.length > 0 && (
                  <button
                    type="button"
                    className="button button--secondary"
                    onClick={handleAutoExtractRequirements}
                    disabled={extractingReqs}
                  >
                    <ListChecks className="icon-xs" aria-hidden="true" />
                    <span>{extractingReqs ? "در حال استخراج نیازمندی‌ها…" : "استخراج خودکار نیازمندی‌ها"}</span>
                  </button>
                )}
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
            <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 id="req-panel-heading">نیازمندی‌های استخراج شده</h3>
                <p className="panel-subtitle">
                  تفکیک نیازمندی‌های کاربردی و مشخصات فنی بر مبنای قرارداد معماری Aria AI.
                </p>
              </div>
              <div style={{ display: "flex", gap: "var(--primitive-space-2)" }}>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setShowAddReq(!showAddReq)}
                >
                  <Plus className="icon-xs" aria-hidden="true" />
                  <span>{showAddReq ? "بستن فرم" : "افزودن نیازمندی"}</span>
                </button>
              </div>
            </div>

            {showAddReq && (
              <form onSubmit={handleAddRequirement} className="auth-card" style={{ maxWidth: "100%", marginBlockEnd: "var(--primitive-space-4)", padding: "var(--primitive-space-4)" }}>
                <h4 style={{ marginBlockEnd: "var(--primitive-space-3)" }}>افزودن نیازمندی جدید</h4>
                <div style={{ display: "grid", gap: "var(--primitive-space-3)" }}>
                  <div>
                    <label className="field-label" htmlFor="new-req-title">عنوان نیازمندی:</label>
                    <input
                      id="new-req-title"
                      type="text"
                      className="input"
                      value={newReqTitle}
                      onChange={(e) => setNewReqTitle(e.target.value)}
                      placeholder="مثال: احراز هویت دوعاملی با پیامک OTP"
                      required
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="new-req-note">شرح و معیار پذیرش:</label>
                    <input
                      id="new-req-note"
                      type="text"
                      className="input"
                      value={newReqNote}
                      onChange={(e) => setNewReqNote(e.target.value)}
                      placeholder="توضیح عملکرد و رفتار مورد انتظار"
                    />
                  </div>
                  <div style={{ display: "flex", gap: "var(--primitive-space-4)", flexWrap: "wrap" }}>
                    <div>
                      <label className="field-label" htmlFor="new-req-type">نوع نیازمندی:</label>
                      <select
                        id="new-req-type"
                        className="input"
                        value={newReqType}
                        onChange={(e) => setNewReqType(e.target.value as "functional" | "non-functional")}
                      >
                        <option value="functional">کاربردی (Functional)</option>
                        <option value="non-functional">کیفی و فنی (Non-Functional)</option>
                      </select>
                    </div>
                    <div>
                      <label className="field-label" htmlFor="new-req-priority">اولویت:</label>
                      <select
                        id="new-req-priority"
                        className="input"
                        value={newReqPriority}
                        onChange={(e) => setNewReqPriority(e.target.value as "p1" | "p2" | "tech")}
                      >
                        <option value="p1">اولویت اصلی (P1)</option>
                        <option value="p2">اولویت متوسط (P2)</option>
                        <option value="tech">استاندارد فنی (Tech)</option>
                      </select>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "var(--primitive-space-2)", marginBlockStart: "var(--primitive-space-2)" }}>
                    <button type="submit" className="button button--primary">
                      <span>ثبت نیازمندی</span>
                    </button>
                    <button type="button" className="button button--secondary" onClick={() => setShowAddReq(false)}>
                      <span>انصراف</span>
                    </button>
                  </div>
                </div>
              </form>
            )}

            <div className="req-columns-grid">
              <div className="req-column">
                <div className="req-column-title">
                  <Layers className="icon-xs text-primary" aria-hidden="true" />
                  <h4>نیازمندی‌های کاربردی (Functional)</h4>
                </div>
                <div className="req-cards">
                  {functionalReqs.map((req) => (
                    <div key={req.id} className="req-card">
                      <div className="req-card__top">
                        <span className={`req-tag req-tag--${req.priority}`}>{req.priorityLabel}</span>
                        <span className="req-id">{req.id}</span>
                      </div>
                      <p className="req-title">{req.title}</p>
                      <p className="req-note">{req.note}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="req-column">
                <div className="req-column-title">
                  <Layers className="icon-xs text-secondary" aria-hidden="true" />
                  <h4>الزامات کیفی و امنیتی (Non-Functional)</h4>
                </div>
                <div className="req-cards">
                  {nonFunctionalReqs.map((req) => (
                    <div key={req.id} className="req-card">
                      <div className="req-card__top">
                        <span className="req-tag req-tag--tech">{req.priorityLabel}</span>
                        <span className="req-id">{req.id}</span>
                      </div>
                      <p className="req-title">{req.title}</p>
                      <p className="req-note">{req.note}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {activeTab === "gaps" && (
          <section className="workspace-panel" aria-labelledby="gaps-panel-heading">
            <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 id="gaps-panel-heading">نقاط مبهم و سوالات شفاف‌سازی</h3>
                <p className="panel-subtitle">
                  این ابهامات باید قبل از قفل کردن محدوده نهایی کار با کارفرما شفاف شوند.
                </p>
              </div>
              <div>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => setShowAddGap(!showAddGap)}
                >
                  <Plus className="icon-xs" aria-hidden="true" />
                  <span>{showAddGap ? "بستن فرم" : "ثبت ابهام جدید"}</span>
                </button>
              </div>
            </div>

            {showAddGap && (
              <form onSubmit={handleAddGap} className="auth-card" style={{ maxWidth: "100%", marginBlockEnd: "var(--primitive-space-4)", padding: "var(--primitive-space-4)" }}>
                <h4 style={{ marginBlockEnd: "var(--primitive-space-3)" }}>افزودن سوال شفاف‌سازی جدید</h4>
                <div style={{ display: "grid", gap: "var(--primitive-space-3)" }}>
                  <div>
                    <label className="field-label" htmlFor="new-gap-title">موضوع یا نقطه مبهم:</label>
                    <input
                      id="new-gap-title"
                      type="text"
                      className="input"
                      value={newGapTitle}
                      onChange={(e) => setNewGapTitle(e.target.value)}
                      placeholder="مثال: نحوه تسویه حساب و اتصال به سیستم انبارداری"
                      required
                    />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="new-gap-desc">شرح سوال برای کارفرما:</label>
                    <input
                      id="new-gap-desc"
                      type="text"
                      className="input"
                      value={newGapDesc}
                      onChange={(e) => setNewGapDesc(e.target.value)}
                      placeholder="توضیح گزینه‌ها و پرسش مربوطه"
                    />
                  </div>
                  <div style={{ display: "flex", gap: "var(--primitive-space-2)" }}>
                    <button type="submit" className="button button--primary">
                      <span>ثبت سوال</span>
                    </button>
                    <button type="button" className="button button--secondary" onClick={() => setShowAddGap(false)}>
                      <span>انصراف</span>
                    </button>
                  </div>
                </div>
              </form>
            )}

            <div className="gap-items-list">
              {gaps.map((gap) => (
                <div key={gap.id} className="gap-item">
                  <div className="gap-item__badge">
                    {gap.status === "resolved" ? (
                      <CheckCircle2 className="icon-sm text-primary" aria-hidden="true" />
                    ) : (
                      <AlertCircle className="icon-sm text-warning" aria-hidden="true" />
                    )}
                  </div>
                  <div className="gap-item__body" style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <h4 className="gap-item__title">{gap.title}</h4>
                      <span className={`badge ${gap.status === "resolved" ? "badge--success" : "badge--warning"}`} style={{ fontSize: "0.75rem" }}>
                        {gap.status === "resolved" ? "شفاف‌سازی شد" : "در انتظار تصمیم"}
                      </span>
                    </div>
                    <p className="gap-item__desc">{gap.description}</p>

                    {gap.decision ? (
                      <div className="gap-item__clarification">
                        <span className="clarification-label">تصمیم ثبت شده:</span>
                        <span className="clarification-val">{gap.decision}</span>
                        <button
                          type="button"
                          className="button button--secondary"
                          style={{ padding: "0.2rem 0.6rem", fontSize: "0.75rem", marginInlineStart: "auto" }}
                          onClick={() => {
                            setActiveEditingGap(gap.id)
                            setGapDecisionInput(gap.decision || "")
                          }}
                        >
                          تغییر تصمیم
                        </button>
                      </div>
                    ) : null}

                    {(activeEditingGap === gap.id || !gap.decision) && (
                      <div style={{ display: "flex", gap: "var(--primitive-space-2)", marginBlockStart: "var(--primitive-space-2)" }}>
                        <input
                          type="text"
                          className="input"
                          style={{ flex: 1, padding: "var(--primitive-space-2)" }}
                          placeholder="تصمیم یا پاسخ توافق‌شده را وارد کنید…"
                          value={activeEditingGap === gap.id ? gapDecisionInput : ""}
                          onChange={(e) => {
                            setActiveEditingGap(gap.id)
                            setGapDecisionInput(e.target.value)
                          }}
                        />
                        <button
                          type="button"
                          className="button button--primary"
                          onClick={() => handleResolveGap(gap.id)}
                        >
                          <Check className="icon-xs" aria-hidden="true" />
                          <span>ثبت تصمیم</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
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
                    <span>محدوده داخل پروژه (In-Scope Deliverables)</span>
                  </h4>
                  <ul>
                    {functionalReqs.map((r) => (
                      <li key={r.id}>
                        <strong>{r.title}:</strong> {r.note}
                      </li>
                    ))}
                    {nonFunctionalReqs.map((r) => (
                      <li key={r.id}>
                        <strong>{r.title}:</strong> {r.note}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="scope-box scope-box--out">
                  <h4 className="scope-box-heading">
                    <AlertCircle className="icon-xs text-muted" aria-hidden="true" />
                    <span>خارج از تعهد فاز جاری (Out-of-Scope)</span>
                  </h4>
                  <ul>
                    <li>اپلیکیشن موبایل بومی (iOS / Android) خارج از فاز جاری</li>
                    <li>سیستم چندزبانه و تسویه‌حساب ارزی بین‌المللی</li>
                    <li>ارسال پیامک انبوه تبلیغاتی و کمپین‌های مارکتینگ</li>
                    <li>یکپارچه‌سازی با نرم‌افزارهای حسابداری متفرقه</li>
                  </ul>
                </div>
              </div>

              <div style={{ marginBlock: "var(--primitive-space-4)", padding: "var(--primitive-space-4)", borderRadius: "var(--button-radius)", background: "hsl(var(--card-background))", border: "var(--border-width-default) solid hsl(var(--card-border))" }}>
                <h5 style={{ marginBlockEnd: "var(--primitive-space-2)", color: "hsl(var(--color-primary))" }}>تصمیمات توافق‌شده برای رفع ابهام:</h5>
                <ul style={{ paddingInlineStart: "var(--primitive-space-4)", margin: 0 }}>
                  {gaps.filter((g) => g.decision).map((g) => (
                    <li key={g.id} style={{ fontSize: "var(--font-size-caption)", color: "hsl(var(--color-text-default))", marginBlockEnd: "var(--primitive-space-1)" }}>
                      <strong>{g.title}:</strong> {g.decision}
                    </li>
                  ))}
                </ul>
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
