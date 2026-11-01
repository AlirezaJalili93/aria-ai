"use client"

import { FormEvent, useEffect, useRef, useState } from "react"

import {
  approvePublicScope,
  PublicScopeResolutionError,
  requestPublicScopeChanges,
  resolvePublicScope
} from "./api"
import { consumeScopeReviewToken } from "./bootstrap"
import type { PublicScopeSection, ResolvedPublicScope } from "./types"

type BootstrapState =
  | Readonly<{ status: "bootstrapping" }>
  | Readonly<{ status: "unavailable"; retryable: boolean }>
  | Readonly<{ status: "ready"; scope: ResolvedPublicScope }>

const sectionLabels: Readonly<Record<PublicScopeSection["section_id"], string>> = {
  summary: "خلاصه پروژه",
  goals: "اهداف",
  pages_sections: "صفحه‌ها و بخش‌ها",
  requirements: "نیازمندی‌های عملکردی",
  content: "نیازمندی‌های محتوا",
  visual_direction: "جهت بصری",
  constraints: "محدودیت‌ها",
  assumptions: "فرض‌ها",
  resolved_gaps: "شکاف‌های حل‌شده",
  remaining_non_blocking_gaps: "شکاف‌های باقی‌مانده غیرمسدودکننده",
  out_of_scope: "خارج از محدوده",
  acceptance_notes: "یادداشت‌های پذیرش"
}

export function ScopeReviewBootstrap() {
  const [state, setState] = useState<BootstrapState>({ status: "bootstrapping" })
  const tokenRef = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    tokenRef.current = consumeScopeReviewToken(window.location, window.history)
    if (tokenRef.current === null) {
      void Promise.resolve().then(() => {
        if (active) setState({ status: "unavailable", retryable: false })
      })
      return () => { active = false }
    }
    void resolvePublicScope(tokenRef.current)
      .then((scope) => {
        if (active) setState({ status: "ready", scope })
      })
      .catch((error) => {
        if (active) setState({ status: "unavailable", retryable: !(error instanceof PublicScopeResolutionError && error.status === 404) })
      })
    return () => {
      active = false
      tokenRef.current = null
    }
  }, [])

  if (state.status !== "ready") {
    return (
      <main id="main-content" className="scope-review-bootstrap" aria-busy={state.status === "bootstrapping"}>
        <div className="status-card status-card--centered" role="status" aria-live="polite">
          <p className="eyebrow">نسخه امن و تغییرناپذیر</p>
          <h1>مرور محدوده پروژه</h1>
          {state.status === "bootstrapping" ? <p>در حال آماده‌سازی محدوده برای مرور…</p> : null}
          {state.status === "unavailable" ? <><p>{state.retryable ? "دریافت محدوده انجام نشد. دوباره تلاش کنید." : "این لینک در دسترس نیست. لطفاً لینک اصلی را دوباره باز کنید."}</p>{state.retryable ? <button className="button button--primary" type="button" onClick={() => { const token = tokenRef.current; if (!token) return; setState({ status: "bootstrapping" }); void resolvePublicScope(token).then((scope) => setState({ status: "ready", scope })).catch((error) => setState({ status: "unavailable", retryable: !(error instanceof PublicScopeResolutionError && error.status === 404) })) }}>تلاش دوباره</button> : null}</> : null}
        </div>
      </main>
    )
  }

  return (
    <ScopeReview
      scope={state.scope}
      getToken={() => tokenRef.current}
      clearToken={() => { tokenRef.current = null }}
      onTerminal={(decisionStatus) => {
        setState({ status: "ready", scope: { ...state.scope, decisionStatus } })
      }}
    />
  )
}

function ScopeReview({
  scope,
  getToken,
  clearToken,
  onTerminal
}: Readonly<{
  scope: ResolvedPublicScope
  getToken: () => string | null
  clearToken: () => void
  onTerminal: (status: "approved" | "changes_requested") => void
}>) {
  const [mode, setMode] = useState<"none" | "approve" | "changes">("none")
  const [guestName, setGuestName] = useState("")
  const [comment, setComment] = useState("")
  const [consent, setConsent] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Readonly<{ guestName?: string; consent?: string; comment?: string }>>({})
  const approvalKey = useRef(crypto.randomUUID())
  const changeKey = useRef(crypto.randomUUID())

  function updateGuestName(value: string) {
    setGuestName(value)
    approvalKey.current = crypto.randomUUID()
    changeKey.current = crypto.randomUUID()
  }

  async function submitApproval(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = getToken()
    const normalizedName = guestName.normalize("NFC").trim()
    const nextErrors = {
      ...(normalizedName.length < 2 || normalizedName.length > 100 ? { guestName: "نام باید بین ۲ تا ۱۰۰ نویسه باشد." } : {}),
      ...(!consent ? { consent: "برای ثبت تأیید، رضایت صریح لازم است." } : {})
    }
    if (!token || Object.keys(nextErrors).length > 0) {
      setFieldErrors(nextErrors)
      setError("نام و تأیید صریح را بررسی کنید.")
      return
    }
    if (!window.confirm("تأیید می‌کنید که این نسخه نهایی محدوده پروژه است؟")) return
    setPending(true)
    setError(null)
    setFieldErrors({})
    try {
      await approvePublicScope({ token, guestName: normalizedName, idempotencyKey: approvalKey.current })
      clearToken()
      onTerminal("approved")
      setMode("none")
    } catch (caught) {
      setError(publicErrorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  async function submitChanges(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const token = getToken()
    const normalizedName = guestName.normalize("NFC").trim()
    const normalizedComment = comment.normalize("NFC").replace(/\r\n?/g, "\n").trim()
    const nextErrors = {
      ...(normalizedName.length < 2 || normalizedName.length > 100 ? { guestName: "نام باید بین ۲ تا ۱۰۰ نویسه باشد." } : {}),
      ...(normalizedComment.length < 1 || normalizedComment.length > 4000 ? { comment: "توضیح تغییرات باید بین ۱ تا ۴۰۰۰ نویسه باشد." } : {})
    }
    if (!token || Object.keys(nextErrors).length > 0) {
      setFieldErrors(nextErrors)
      setError("نام و توضیح تغییرات را بررسی کنید.")
      return
    }
    setPending(true)
    setError(null)
    setFieldErrors({})
    try {
      await requestPublicScopeChanges({
        token,
        guestName: normalizedName,
        comment: normalizedComment,
        idempotencyKey: changeKey.current
      })
      clearToken()
      onTerminal("changes_requested")
      setMode("none")
    } catch (caught) {
      setError(publicErrorMessage(caught))
    } finally {
      setPending(false)
    }
  }

  return (
    <main id="main-content" className="scope-review-page" tabIndex={-1}>
      <header className="scope-review-header">
        <p className="eyebrow">نسخه امن و تغییرناپذیر</p>
        <h1>مرور محدوده پروژه</h1>
        <p>نسخه {scope.versionNo.toLocaleString("fa-IR")}</p>
        <DecisionNotice status={scope.decisionStatus} />
      </header>

      <div className="scope-review-sections">
        {scope.snapshotData.sections.map((section) => <PublicScopeSectionView key={section.section_id} section={section} />)}
      </div>

      {scope.decisionStatus === "awaiting_approval" ? (
        <section className="scope-review-decision" aria-labelledby="scope-decision-title">
          <h2 id="scope-decision-title">تصمیم نهایی</h2>
          <p>پس از مرور همه بخش‌ها، یکی از دو مسیر را انتخاب کنید.</p>
          {mode === "none" ? (
            <div className="scope-review-actions">
              <button className="button button--primary" type="button" onClick={() => setMode("approve")}>تأیید محدوده</button>
              <button className="button button--secondary" type="button" onClick={() => setMode("changes")}>درخواست تغییر</button>
            </div>
          ) : null}
          {error ? <div className="form-error-summary" role="alert">{error}</div> : null}
          {mode === "approve" ? (
            <form className="scope-review-form" onSubmit={submitApproval} noValidate>
              <GuestNameField value={guestName} onChange={updateGuestName} error={fieldErrors.guestName} />
              <label className="checkbox-field"><input type="checkbox" checked={consent} onChange={(event) => { setConsent(event.target.checked); approvalKey.current = crypto.randomUUID() }} required aria-invalid={Boolean(fieldErrors.consent)} aria-describedby={fieldErrors.consent ? "consent-error" : undefined} /><span>این نسخه را پس از مرور صریحاً تأیید می‌کنم.</span></label>
              {fieldErrors.consent ? <p id="consent-error" className="field-error">{fieldErrors.consent}</p> : null}
              <div className="scope-review-actions"><button className="button button--primary" type="submit" disabled={pending}>{pending ? "در حال ثبت…" : "ثبت تأیید"}</button><button className="button button--secondary" type="button" disabled={pending} onClick={() => { setMode("none"); setError(null) }}>انصراف</button></div>
            </form>
          ) : null}
          {mode === "changes" ? (
            <form className="scope-review-form" onSubmit={submitChanges} noValidate>
              <GuestNameField value={guestName} onChange={updateGuestName} error={fieldErrors.guestName} />
              <label htmlFor="change-comment">توضیح تغییرات</label>
              <textarea id="change-comment" value={comment} onChange={(event) => { setComment(event.target.value); changeKey.current = crypto.randomUUID() }} maxLength={4000} required rows={8} aria-invalid={Boolean(fieldErrors.comment)} aria-describedby={fieldErrors.comment ? "change-comment-help change-comment-error" : "change-comment-help"} />
              <p id="change-comment-help" className="field-help">حداکثر ۴۰۰۰ نویسه. متن شما تا زمان ارسال فقط در حافظه این صفحه می‌ماند.</p>
              {fieldErrors.comment ? <p id="change-comment-error" className="field-error">{fieldErrors.comment}</p> : null}
              <div className="scope-review-actions"><button className="button button--primary" type="submit" disabled={pending}>{pending ? "در حال ثبت…" : "ثبت درخواست تغییر"}</button><button className="button button--secondary" type="button" disabled={pending} onClick={() => { setMode("none"); setError(null) }}>انصراف</button></div>
            </form>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}

function GuestNameField({ value, onChange, error }: Readonly<{ value: string; onChange: (value: string) => void; error?: string }>) {
  return <><label htmlFor="guest-name">نام شما</label><input id="guest-name" value={value} onChange={(event) => onChange(event.target.value)} minLength={2} maxLength={100} required autoComplete="name" aria-invalid={Boolean(error)} aria-describedby={error ? "guest-name-error" : undefined} />{error ? <p id="guest-name-error" className="field-error">{error}</p> : null}</>
}

function DecisionNotice({ status }: Readonly<{ status: ResolvedPublicScope["decisionStatus"] }>) {
  const text = {
    awaiting_approval: "این نسخه منتظر تصمیم شماست.",
    approved: "این نسخه تأیید شده و فقط برای مطالعه در دسترس است.",
    changes_requested: "برای این نسخه درخواست تغییر ثبت شده و تصمیم آن نهایی است.",
    superseded: "این نسخه تاریخی است و نسخه جدیدتری جایگزین آن شده است. امکان تصمیم‌گیری ندارد."
  }[status]
  return <p className={`decision-notice decision-notice--${status}`} role="status">{text}</p>
}

function PublicScopeSectionView({ section }: Readonly<{ section: PublicScopeSection }>) {
  return <section className="scope-review-section"><h2>{sectionLabels[section.section_id]}</h2><SectionValue section={section} /></section>
}

function SectionValue({ section }: Readonly<{ section: PublicScopeSection }>) {
  if (typeof section.value === "string") return <p>{section.value || "—"}</p>
  if (section.value.length === 0) return <p className="muted-text">موردی ثبت نشده است.</p>
  if (section.section_id === "pages_sections") {
    return <div className="scope-page-grid">{section.value.map((page, index) => typeof page === "object" && "page_name" in page ? <article key={`${page.page_name}-${index}`} className="scope-page-card"><h3>{page.page_name}</h3><ul>{page.sections.map((item, itemIndex) => <li key={`${item.name}-${itemIndex}`}>{item.name}</li>)}</ul></article> : null)}</div>
  }
  return <ul>{section.value.map((item, index) => <li key={index}>{typeof item === "string" ? item : describeStructuredItem(item)}</li>)}</ul>
}

function describeStructuredItem(item: Exclude<PublicScopeSection["value"], string | readonly string[]>[number]): string {
  if ("text" in item && "priority" in item) return `${item.text} — ${item.priority}`
  if ("description" in item) return item.description
  if ("resolution_type" in item) return `${item.text} — ${item.resolution_type}`
  if ("severity" in item) return `${item.text} — ${item.severity}`
  return ""
}

function publicErrorMessage(error: unknown): string {
  if (error instanceof PublicScopeResolutionError && error.status === 404) return "این لینک دیگر در دسترس نیست."
  if (error instanceof PublicScopeResolutionError && error.code === "VALIDATION_FAILED") return "مقادیر واردشده معتبر نیستند."
  if (error instanceof PublicScopeResolutionError && error.code === "SCOPE_ALREADY_APPROVED") return "این نسخه قبلاً تأیید شده است."
  if (error instanceof PublicScopeResolutionError && error.code === "SCOPE_CHANGES_ALREADY_REQUESTED") return "برای این نسخه قبلاً درخواست تغییر ثبت شده است."
  return "ثبت تصمیم انجام نشد. اطلاعات شما در این صفحه حفظ شده است؛ دوباره تلاش کنید."
}
