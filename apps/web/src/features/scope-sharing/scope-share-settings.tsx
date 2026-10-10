"use client"

import { useActionState, useMemo, useState } from "react"

import { createScopeShareAction, revokeScopeShareAction } from "./actions"
import type { ScopeDecisionProjection, ScopeShareProjection, ScopeVersionForSharing, ShareMutationState } from "./types"

const initialState: ShareMutationState = { status: "idle" }

export function ScopeShareSettings({ projectId, version, shares, decision }: Readonly<{
  projectId: string
  version: ScopeVersionForSharing
  shares: readonly ScopeShareProjection[]
  decision: ScopeDecisionProjection
}>) {
  const [expiresLocal, setExpiresLocal] = useState("")
  const [createKey, setCreateKey] = useState(() => crypto.randomUUID())
  const [createState, createAction, createPending] = useActionState(createScopeShareAction, initialState)
  const shareUrl = useMemo(() => {
    if (createState.status !== "success" || !createState.tokenAvailable || !createState.rawToken || typeof window === "undefined") return null
    return `${window.location.origin}/scope-review#token=${encodeURIComponent(createState.rawToken)}`
  }, [createState])

  async function copyShareUrl() {
    if (shareUrl) await navigator.clipboard.writeText(shareUrl)
  }

  return (
    <div className="scope-share-layout">
      <header className="page-heading">
        <div><p className="eyebrow">مدیریت اشتراک</p><h1>اشتراک نسخه {version.versionNo.toLocaleString("fa-IR")} محدوده</h1></div>
        <span className="status-badge">{versionStatusLabel(version.status)}</span>
      </header>

      <section className="panel" aria-labelledby="create-share-title">
        <h2 id="create-share-title">ایجاد لینک جدید</h2>
        {version.status === "superseded" ? <p className="decision-notice decision-notice--superseded">برای نسخه جایگزین‌شده لینک جدید ساخته نمی‌شود. لینک‌های قبلی فقط برای مرور تاریخی باقی می‌مانند.</p> : (
          <form action={createAction} className="stack-form">
            <input type="hidden" name="project_id" value={projectId} />
            <input type="hidden" name="version_no" value={version.versionNo} />
            <input type="hidden" name="idempotency_key" value={createKey} />
            <label htmlFor="share-expires-at">زمان انقضا</label>
            <input id="share-expires-at" type="datetime-local" value={expiresLocal} onChange={(event) => { setExpiresLocal(event.target.value); setCreateKey(crypto.randomUUID()) }} required />
            <input type="hidden" name="expires_at" value={expiresLocal ? new Date(expiresLocal).toISOString() : ""} />
            <p className="field-help">زمان را به وقت محلی وارد کنید؛ سرور آن را به‌صورت UTC ثبت می‌کند. مقدار پیش‌فرضی انتخاب نشده است.</p>
            <button className="button button--primary" type="submit" disabled={createPending || !expiresLocal}>{createPending ? "در حال ایجاد…" : "ایجاد لینک اشتراک"}</button>
          </form>
        )}
        {createState.status !== "idle" ? <p className={createState.status === "error" ? "form-error-summary" : "success-message"} role="status">{createState.message}</p> : null}
        {shareUrl ? <div className="one-time-token" role="status"><p><strong>این لینک فقط همین بار نمایش داده می‌شود.</strong></p><label htmlFor="created-share-url">لینک مرور</label><input id="created-share-url" dir="ltr" readOnly value={shareUrl} /><button className="button button--secondary" type="button" onClick={copyShareUrl}>کپی لینک</button></div> : null}
        {createState.status === "success" && createState.tokenAvailable === false ? <p className="form-error-summary">توکن قبلی قابل بازیابی نیست. لینک موجود را لغو کنید و با یک درخواست جدید لینک دیگری بسازید.</p> : null}
      </section>

      <section className="panel" aria-labelledby="shares-title"><h2 id="shares-title">لینک‌های این نسخه</h2>{shares.length === 0 ? <p className="muted-text">هنوز لینکی ایجاد نشده است.</p> : <ul className="share-list">{shares.map((share) => <ShareListItem key={share.id} projectId={projectId} share={share} />)}</ul>}</section>
      <DecisionPanel decision={decision} />
    </div>
  )
}

function ShareListItem({ projectId, share }: Readonly<{ projectId: string; share: ScopeShareProjection }>) {
  const [key] = useState(() => crypto.randomUUID())
  const [state, action, pending] = useActionState(revokeScopeShareAction, initialState)
  return <li className="share-list-item"><div><strong>{shareStatusLabel(share.status)}</strong><p>انقضا: {formatDate(share.expiresAt)}</p><p>ایجاد: {formatDate(share.createdAt)}</p></div>{share.canRevoke ? <form action={action} onSubmit={(event) => { if (!window.confirm("دسترسی این لینک لغو شود؟")) event.preventDefault() }}><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="version_no" value={share.scopeVersionNo} /><input type="hidden" name="share_link_id" value={share.id} /><input type="hidden" name="idempotency_key" value={key} /><button className="button button--danger" type="submit" disabled={pending}>{pending ? "در حال لغو…" : "لغو دسترسی"}</button></form> : null}{state.status !== "idle" ? <p className={state.status === "error" ? "form-error-summary" : "success-message"} role="status">{state.message}</p> : null}</li>
}

function DecisionPanel({ decision }: Readonly<{ decision: ScopeDecisionProjection }>) {
  return <section className="panel" aria-labelledby="decision-result-title"><h2 id="decision-result-title">نتیجه بازبینی</h2>{decision.decisionType === "none" ? <p className="muted-text">هنوز تصمیمی ثبت نشده است.</p> : decision.decisionType === "approval" ? <><p className="success-message">محدوده توسط {decision.guestName} تأیید شده است.</p><p>{formatDate(decision.decidedAt)}</p></> : <><p className="decision-notice decision-notice--changes_requested">{decision.guestName} درخواست تغییر ثبت کرده است.</p><p className="change-request-comment">{decision.comment}</p><p>{formatDate(decision.decidedAt)}</p></>}</section>
}

function formatDate(value: string): string { return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) }
function versionStatusLabel(status: ScopeVersionForSharing["status"]): string { return ({ awaiting_approval: "در انتظار تأیید", approved: "تأییدشده", changes_requested: "نیازمند تغییر", superseded: "جایگزین‌شده" })[status] }
function shareStatusLabel(status: ScopeShareProjection["status"]): string { return ({ active: "فعال", expired: "منقضی", revoked: "لغوشده" })[status] }
