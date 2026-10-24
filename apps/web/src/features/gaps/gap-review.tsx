"use client"

import { useActionState, useEffect, useRef, useState, useTransition } from "react"
import { useFormStatus } from "react-dom"
import { useRouter } from "next/navigation"

import {
  dismissGapAction,
  editClarificationAction,
  loadClarificationsAction,
  loadGapsAction,
  resolveClarificationAction
} from "./actions"
import type {
  ClarificationHistory,
  ClarificationHistoryItem,
  ClarificationResolutionType,
  Gap,
  GapFilters,
  GapMutationState,
  GapPage,
  GapSeverity,
  GapStatus,
  GapType
} from "./types"

const idle: GapMutationState = { status: "idle", message: "" }
const severityLabels: Readonly<Record<GapSeverity, string>> = { critical: "بحرانی", high: "زیاد", medium: "متوسط", low: "کم" }
const statusLabels: Readonly<Record<GapStatus, string>> = { open: "باز", resolved: "حل‌شده", dismissed: "کنار گذاشته‌شده" }
const typeLabels: Readonly<Record<GapType, string>> = { missing_information: "اطلاعات مفقود", ambiguity: "ابهام", conflict: "تعارض", decision_required: "نیازمند تصمیم", unsupported_assumption: "فرض بدون پشتوانه", scope_risk: "ریسک محدوده" }

export function GapReview({ projectId, initialPage }: Readonly<{ projectId: string; initialPage: GapPage }>) {
  const [items, setItems] = useState(initialPage.data)
  const [meta, setMeta] = useState(initialPage.meta)
  const [status, setStatus] = useState<GapStatus | "all">("all")
  const [severity, setSeverity] = useState<GapSeverity | "all">("all")
  const [gapType, setGapType] = useState<GapType | "all">("all")
  const [failure, setFailure] = useState<Readonly<{ message: string; requestId?: string }> | null>(null)
  const [pending, startTransition] = useTransition()
  const requestSequence = useRef(0)

  function filters(nextStatus = status, nextSeverity = severity, nextType = gapType): GapFilters {
    return { ...(nextStatus === "all" ? {} : { status: nextStatus }), ...(nextSeverity === "all" ? {} : { severity: nextSeverity }), ...(nextType === "all" ? {} : { gap_type: nextType }) }
  }
  function apply(nextStatus: GapStatus | "all", nextSeverity: GapSeverity | "all", nextType: GapType | "all") {
    setStatus(nextStatus); setSeverity(nextSeverity); setGapType(nextType); setFailure(null)
    const sequence = ++requestSequence.current
    startTransition(async () => {
      const result = await loadGapsAction(projectId, filters(nextStatus, nextSeverity, nextType))
      if (sequence !== requestSequence.current) return
      if (result.status === "error") { setFailure({ message: result.message, ...(result.requestId ? { requestId: result.requestId } : {}) }); return }
      setItems(result.page.data); setMeta(result.page.meta)
    })
  }
  function loadMore() {
    if (!meta.next_cursor) return
    setFailure(null)
    const sequence = ++requestSequence.current
    startTransition(async () => {
      const result = await loadGapsAction(projectId, filters(), meta.next_cursor ?? undefined)
      if (sequence !== requestSequence.current) return
      if (result.status === "error") { setFailure({ message: result.message, ...(result.requestId ? { requestId: result.requestId } : {}) }); return }
      setItems((current) => [...current, ...result.page.data]); setMeta(result.page.meta)
    })
  }
  const filtered = status !== "all" || severity !== "all" || gapType !== "all"
  return (
    <section className="gap-review" aria-labelledby="gap-review-title">
      <div className="section-heading"><div><p className="eyebrow">Gaps</p><h1 id="gap-review-title">ابهام‌ها و تصمیم‌های باز</h1><p className="section-intro">موارد نیازمند پاسخ یا تصمیم انسانی را مرور کنید.</p></div></div>
      <div className="gap-filters" aria-busy={pending}>
        <Filter id="gap-status" label="وضعیت" value={status} onChange={(value) => apply(value as GapStatus | "all", severity, gapType)} options={Object.entries(statusLabels)} disabled={pending} />
        <Filter id="gap-severity" label="شدت" value={severity} onChange={(value) => apply(status, value as GapSeverity | "all", gapType)} options={Object.entries(severityLabels)} disabled={pending} />
        <Filter id="gap-type" label="نوع" value={gapType} onChange={(value) => apply(status, severity, value as GapType | "all")} options={Object.entries(typeLabels)} disabled={pending} />
        <p className="filter-status" aria-live="polite">{pending ? "در حال اعمال فیلتر…" : ""}</p>
      </div>
      {failure ? <RequestFailure failure={failure} retry={() => apply(status, severity, gapType)} pending={pending} /> : null}
      {!pending && items.length === 0 ? <div className="empty-state" role="status"><h2>{filtered ? "نتیجه‌ای با این فیلترها پیدا نشد" : "ابهام بازی برای این نسخه زمینه وجود ندارد"}</h2><p>{filtered ? "فیلترها را تغییر دهید یا پاک کنید." : "پس از شناسایی Gap، موارد اینجا نمایش داده می‌شوند."}</p>{filtered ? <button className="button button--secondary" type="button" onClick={() => apply("all", "all", "all")}>پاک کردن فیلترها</button> : null}</div> : <div className="gap-list" aria-live="polite">{items.map((gap) => <GapCard gap={gap} projectId={projectId} key={gap.id} />)}</div>}
      {meta.has_more ? <button className="button button--secondary gap-load-more" type="button" onClick={loadMore} disabled={pending}>{pending ? "در حال بارگذاری…" : "نمایش موارد بیشتر"}</button> : null}
    </section>
  )
}

function Filter({ id, label, value, options, onChange, disabled }: Readonly<{ id: string; label: string; value: string; options: readonly (readonly string[])[]; onChange: (value: string) => void; disabled: boolean }>) {
  return <label htmlFor={id}>{label}<select className="text-field" id={id} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}><option value="all">همه</option>{options.map(([option, text]) => <option value={option} key={option}>{text}</option>)}</select></label>
}

function GapCard({ gap, projectId }: Readonly<{ gap: Gap; projectId: string }>) {
  const [history, setHistory] = useState<ClarificationHistory | null>(null)
  const [historyFailure, setHistoryFailure] = useState<Readonly<{ message: string; requestId?: string }> | null>(null)
  const [loading, startLoading] = useTransition()
  const [dismissState, dismissAction] = useActionState(dismissGapAction, idle)
  const router = useRouter()
  const completion = useRef<string | undefined>(undefined)
  useEffect(() => { if (dismissState.completionId && completion.current !== dismissState.completionId) { completion.current = dismissState.completionId; router.refresh() } }, [dismissState.completionId, router])
  function loadHistory() {
    setHistoryFailure(null)
    startLoading(async () => {
      const result = await loadClarificationsAction(projectId, gap.id)
      if (result.status === "error") { setHistoryFailure({ message: result.message, ...(result.requestId ? { requestId: result.requestId } : {}) }); return }
      setHistory(result.history)
    })
  }
  const assumptionEligible = gap.gap_type === "unsupported_assumption" && gap.suggested_resolution_type === "validate_assumption"
  return (
    <article className={`gap-card gap-card--${gap.severity}`} aria-labelledby={`gap-${gap.id}`}>
      <div className="gap-card__heading"><div><p className="gap-type">{typeLabels[gap.gap_type]}</p><h2 id={`gap-${gap.id}`}>{gap.explanation ?? "توضیحی برای این Gap ثبت نشده است."}</h2></div><span className={`severity-badge severity-badge--${gap.severity}`}><SeverityIcon />{severityLabels[gap.severity]}</span></div>
      <dl className="gap-meta"><div><dt>وضعیت</dt><dd>{statusLabels[gap.status]}</dd></div><div><dt>نسخه زمینه</dt><dd>{gap.context_version.toLocaleString("fa-IR")}</dd></div></dl>
      <button className="button button--secondary" type="button" onClick={loadHistory} disabled={loading}>{loading ? "در حال بارگذاری…" : history ? "به‌روزرسانی تاریخچه" : "مشاهده پرسش‌ها"}</button>
      {historyFailure ? <RequestFailure failure={historyFailure} retry={loadHistory} pending={loading} /> : null}
      {history ? <section className="clarification-history" aria-label="تاریخچه پرسش‌ها">{history.data.length === 0 ? <p className="gap-muted">پرسشی برای این Gap ثبت نشده است.</p> : history.data.map((item) => <ClarificationCard item={item} projectId={projectId} gapId={gap.id} assumptionEligible={assumptionEligible} gapOpen={gap.status === "open"} key={item.id} />)}</section> : null}
      {gap.status === "open" ? <form className="gap-dismiss" action={dismissAction} onSubmit={(event) => { if (!window.confirm("این Gap کنار گذاشته شود؟ این اقدام با نادیده‌گرفتن یک پرسش متفاوت است.")) event.preventDefault() }}><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="gap_id" value={gap.id} /><input type="hidden" name="idempotency_key" value={`j04-${gap.id}-dismiss`} /><Submit label="کنار گذاشتن Gap" pendingLabel="در حال ثبت…" danger /></form> : <p className="gap-muted">این Gap بسته است و فقط سابقه آن قابل مشاهده است.</p>}
      <Feedback state={dismissState} />
    </article>
  )
}

function ClarificationCard({ item, projectId, gapId, assumptionEligible, gapOpen }: Readonly<{ item: ClarificationHistoryItem; projectId: string; gapId: string; assumptionEligible: boolean; gapOpen: boolean }>) {
  const [editState, editAction] = useActionState(editClarificationAction, idle)
  const [resolutionState, resolutionAction] = useActionState(resolveClarificationAction, idle)
  const router = useRouter()
  const seen = useRef(new Set<string>())
  useEffect(() => { for (const id of [editState.completionId, resolutionState.completionId]) if (id && !seen.current.has(id)) { seen.current.add(id); router.refresh() } }, [editState.completionId, resolutionState.completionId, router])
  const mutable = gapOpen && item.status === "open"
  return (
    <article className="clarification-card" aria-labelledby={`clarification-${item.id}`}>
      <div className="clarification-card__heading"><h3 id={`clarification-${item.id}`} dir="auto">{item.question_text}</h3><span className="status-badge">{item.status === "open" ? "باز" : item.status === "answered" ? "پاسخ‌داده‌شده" : "نادیده‌گرفته‌شده"}</span></div>
      {item.resolution ? <div className="clarification-resolution"><p>{resolutionLabel(item.resolution.resolution_type)}</p>{item.resolution.answer_text ? <p dir="auto">{item.resolution.answer_text}</p> : null}</div> : null}
      {mutable ? <div className="clarification-actions">
        <details><summary>ویرایش پرسش</summary><form action={editAction}><Fields item={item} projectId={projectId} gapId={gapId} /><label htmlFor={`question-${item.id}`}>متن پرسش<textarea id={`question-${item.id}`} className="text-field gap-textarea" name="question_text" defaultValue={item.question_text} /></label><Submit label="ذخیره ویرایش" pendingLabel="در حال ذخیره…" /></form></details>
        <ResolutionForm item={item} projectId={projectId} gapId={gapId} action={resolutionAction} type="provided_information" author="client" label="ثبت پاسخ مشتری" />
        <ResolutionForm item={item} projectId={projectId} gapId={gapId} action={resolutionAction} type="internal_decision" author="user" label="ثبت تصمیم داخلی" />
        <div className="button-row">{assumptionEligible ? <ActionOnly item={item} projectId={projectId} gapId={gapId} action={resolutionAction} type="accepted_assumption" label="پذیرش فرض" /> : null}<ActionOnly item={item} projectId={projectId} gapId={gapId} action={resolutionAction} type="ignored" label="نادیده گرفتن پرسش" /></div>
      </div> : null}
      <Feedback state={editState} /><Feedback state={resolutionState} />
    </article>
  )
}

function ResolutionForm({ item, projectId, gapId, action, type, author, label }: Readonly<{ item: ClarificationHistoryItem; projectId: string; gapId: string; action: (payload: FormData) => void; type: "provided_information" | "internal_decision"; author: "client" | "user"; label: string }>) {
  return <details><summary>{label}</summary><form action={action}><Fields item={item} projectId={projectId} gapId={gapId} /><input type="hidden" name="resolution_type" value={type} /><input type="hidden" name="author_type" value={author} /><input type="hidden" name="idempotency_key" value={`j04-${item.id}-${type}`} /><label htmlFor={`${type}-${item.id}`}>متن پاسخ<textarea id={`${type}-${item.id}`} className="text-field gap-textarea" name="answer_text" required /></label><Submit label={label} pendingLabel="در حال ثبت…" /></form></details>
}
function ActionOnly({ item, projectId, gapId, action, type, label }: Readonly<{ item: ClarificationHistoryItem; projectId: string; gapId: string; action: (payload: FormData) => void; type: "accepted_assumption" | "ignored"; label: string }>) {
  return <form action={action}><Fields item={item} projectId={projectId} gapId={gapId} /><input type="hidden" name="resolution_type" value={type} /><input type="hidden" name="author_type" value="user" /><input type="hidden" name="idempotency_key" value={`j04-${item.id}-${type}`} /><Submit label={label} pendingLabel="در حال ثبت…" /></form>
}
function Fields({ item, projectId, gapId }: Readonly<{ item: ClarificationHistoryItem; projectId: string; gapId: string }>) { return <><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="gap_id" value={gapId} /><input type="hidden" name="clarification_id" value={item.id} /><input type="hidden" name="expected_updated_at" value={item.updated_at} /></> }
function Feedback({ state }: Readonly<{ state: GapMutationState }>) { return state.status === "idle" ? null : <div className={state.status === "error" ? "form-error-summary" : "form-success"} role={state.status === "error" ? "alert" : "status"}><p>{state.message}</p>{state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}</div> }
function Submit({ label, pendingLabel, danger = false }: Readonly<{ label: string; pendingLabel: string; danger?: boolean }>) { const { pending } = useFormStatus(); return <button className={`button ${danger ? "button--danger" : "button--secondary"}`} type="submit" disabled={pending}>{pending ? pendingLabel : label}</button> }
function RequestFailure({ failure, retry, pending }: Readonly<{ failure: Readonly<{ message: string; requestId?: string }>; retry: () => void; pending: boolean }>) { return <div className="inline-alert gap-request-error" role="alert"><p>{failure.message}</p>{failure.requestId ? <p className="request-reference">شناسه پیگیری: {failure.requestId}</p> : null}<button className="button button--secondary" type="button" onClick={retry} disabled={pending}>تلاش دوباره</button></div> }
function resolutionLabel(value: ClarificationResolutionType): string { return value === "provided_information" ? "پاسخ مشتری" : value === "internal_decision" ? "تصمیم داخلی" : value === "accepted_assumption" ? "فرض پذیرفته شد" : "پرسش نادیده گرفته شد" }
function SeverityIcon() { return <svg aria-hidden="true" className="severity-icon" viewBox="0 0 24 24" focusable="false"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M12 7v6m0 4h.01" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" /></svg> }
