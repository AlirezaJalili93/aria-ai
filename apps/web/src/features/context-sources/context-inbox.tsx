"use client"

import { startTransition, useActionState, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useFormStatus } from "react-dom"
import { useRouter } from "next/navigation"

import { archiveSourceAction, createTextSourceAction, loadMoreSourcesAction, refreshSourcesAction, retrySourceJobAction, uploadTxtSourceAction } from "./actions"
import type { ContextSource, ContextSourceActionState, ContextSourcePage } from "./types"

const idleTextState: ContextSourceActionState = { status: "idle", message: "", idempotencyKey: "", submissionFingerprint: null }
const idleState: ContextSourceActionState = { status: "idle", message: "" }
const activeStatuses = new Set(["queued", "running"])

export function ContextInbox({ projectId, initialPage, uploadEnabled, textIdempotencyKey, uploadIdempotencyKey }: Readonly<{ projectId: string; initialPage: ContextSourcePage; uploadEnabled: boolean; textIdempotencyKey: string; uploadIdempotencyKey: string }>) {
  const router = useRouter()
  const [sources, setSources] = useState<readonly ContextSource[]>(initialPage.data)
  const [pagination, setPagination] = useState(initialPage.meta)
  const [requestState, setRequestState] = useState<ContextSourceActionState>(idleState)
  const [refreshing, setRefreshing] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [pendingSourceId, setPendingSourceId] = useState<string | null>(null)
  const pollInFlightRef = useRef(false)
  const sourceIdsRef = useRef<readonly string[]>(sources.map((source) => source.id))
  const retryKeysRef = useRef(new Map<string, string>())

  useEffect(() => { sourceIdsRef.current = sources.map((source) => source.id) }, [sources])
  const sourceCreated = useCallback(() => router.refresh(), [router])

  const hasActiveJob = useMemo(() => sources.some((source) => source.latest_job && activeStatuses.has(source.latest_job.status)), [sources])

  const refresh = useCallback(async (manual: boolean) => {
    if (pollInFlightRef.current || (!manual && document.hidden)) return
    pollInFlightRef.current = true
    if (manual) setRefreshing(true)
    try {
      const result = await refreshSourcesAction(projectId, sourceIdsRef.current)
      if (result.status === "success") {
        const fresh = new Map(result.sources.map((source) => [source.id, source]))
        setSources((current) => current.map((source) => fresh.get(source.id) ?? source))
        if (manual) setRequestState({ status: "success", message: "وضعیت منابع تازه شد." })
      } else if (manual) setRequestState(result)
    } finally {
      pollInFlightRef.current = false
      if (manual) setRefreshing(false)
    }
  }, [projectId])

  useEffect(() => {
    if (!hasActiveJob) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const schedule = () => {
      if (!document.hidden) timer = setTimeout(async () => { await refresh(false); schedule() }, 5_000)
    }
    const visibility = () => {
      if (timer) clearTimeout(timer)
      if (!document.hidden) { void refresh(false); schedule() }
    }
    document.addEventListener("visibilitychange", visibility)
    schedule()
    return () => { if (timer) clearTimeout(timer); document.removeEventListener("visibilitychange", visibility) }
  }, [hasActiveJob, refresh])

  async function loadMore() {
    if (!pagination.next_cursor || loadingMore) return
    setLoadingMore(true)
    const result = await loadMoreSourcesAction(projectId, pagination.next_cursor)
    if (result.status === "success") {
      setSources((current) => {
        const known = new Set(current.map((source) => source.id))
        return [...current, ...result.page.data.filter((source) => !known.has(source.id))]
      })
      setPagination(result.page.meta)
    } else setRequestState(result)
    setLoadingMore(false)
  }

  async function archive(source: ContextSource) {
    if (!source.can_archive || !window.confirm("این منبع بایگانی شود؟ تاریخچه و داده ذخیره‌شده حذف فیزیکی نمی‌شود.")) return
    setPendingSourceId(source.id)
    const result = await archiveSourceAction(projectId, source.id)
    setRequestState(result)
    if (result.status === "success") setSources((current) => current.filter((item) => item.id !== source.id))
    setPendingSourceId(null)
  }

  async function retry(source: ContextSource) {
    if (!source.latest_job?.retryable) return
    const jobId = source.latest_job.id
    const key = retryKeysRef.current.get(jobId) ?? crypto.randomUUID()
    retryKeysRef.current.set(jobId, key)
    setPendingSourceId(source.id)
    const result = await retrySourceJobAction(projectId, jobId, key)
    setRequestState(result)
    if (result.status === "success") { retryKeysRef.current.delete(jobId); await refresh(true) }
    setPendingSourceId(null)
  }

  return (
    <section className="context-inbox" aria-labelledby="context-inbox-title">
      <header className="context-inbox__heading">
        <div><p className="eyebrow">ورودی‌های پروژه</p><h1 id="context-inbox-title">منابع زمینه</h1><p>متن‌های اولیه را ثبت کنید و وضعیت پردازش آن‌ها را پیگیری کنید.</p></div>
        <button className="button button--secondary" type="button" onClick={() => void refresh(true)} disabled={refreshing}>{refreshing ? "در حال تازه‌سازی…" : "تازه‌سازی"}</button>
      </header>

      <div className="context-source-create-grid">
        <TextSourceForm projectId={projectId} idempotencyKey={textIdempotencyKey} onCompleted={sourceCreated} />
        {uploadEnabled ? <UploadSourceForm projectId={projectId} idempotencyKey={uploadIdempotencyKey} onCompleted={sourceCreated} /> : null}
      </div>

      <ActionFeedback state={requestState} />
      {sources.length === 0 ? <div className="empty-state context-source-empty"><h2>هنوز منبعی ثبت نشده است</h2><p>برای شروع، متن Brief را در فرم بالا وارد کنید.</p></div> : (
        <ul className="context-source-list" aria-label="فهرست منابع">
          {sources.map((source) => <SourceCard key={source.id} source={source} pending={pendingSourceId === source.id} onArchive={() => void archive(source)} onRetry={() => void retry(source)} />)}
        </ul>
      )}
      {pagination.has_more && pagination.next_cursor ? <div className="pagination-region"><button className="button button--secondary" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? "در حال بارگذاری…" : "نمایش منابع بیشتر"}</button></div> : null}
    </section>
  )
}

function TextSourceForm({ projectId, idempotencyKey, onCompleted }: Readonly<{ projectId: string; idempotencyKey: string; onCompleted: () => void }>) {
  const formRef = useRef<HTMLFormElement>(null)
  const [state, action] = useActionState(createTextSourceAction, { ...idleTextState, idempotencyKey })
  useEffect(() => { if (state.status === "success") { formRef.current?.reset(); startTransition(onCompleted) } }, [state, onCompleted])
  return <form ref={formRef} className="context-source-create-card" action={action}><div><h2>چسباندن متن</h2><p>متن Brief یا پیام مشتری را بدون تغییر معنایی وارد کنید.</p></div><input type="hidden" name="project_id" value={projectId} /><label htmlFor="context-raw-text">متن منبع</label><textarea className="text-field context-source-textarea" id="context-raw-text" name="raw_text" maxLength={50_000} required dir="auto" /><SourceSubmitButton label="افزودن متن" pendingLabel="در حال ثبت…" primary /><ActionFeedback state={state} /></form>
}

function UploadSourceForm({ projectId, idempotencyKey, onCompleted }: Readonly<{ projectId: string; idempotencyKey: string; onCompleted: () => void }>) {
  const formRef = useRef<HTMLFormElement>(null)
  const [state, action] = useActionState(uploadTxtSourceAction, idleState)
  useEffect(() => { if (state.status === "success") { formRef.current?.reset(); startTransition(onCompleted) } }, [state, onCompleted])
  return <form ref={formRef} className="context-source-create-card" action={action}><div><h2>فایل TXT</h2><p>فایل متنی UTF-8 با حجم حداکثر ۲۰۰ کیلوبایت.</p></div><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="idempotency_key" value={idempotencyKey} /><label htmlFor="context-file">انتخاب فایل TXT</label><input className="text-field context-source-file" id="context-file" name="file" type="file" accept=".txt,text/plain" required /><SourceSubmitButton label="بارگذاری فایل" pendingLabel="در حال بارگذاری…" /><ActionFeedback state={state} /></form>
}

function SourceCard({ source, pending, onArchive, onRetry }: Readonly<{ source: ContextSource; pending: boolean; onArchive: () => void; onRetry: () => void }>) {
  const job = source.latest_job
  const retryable = source.latest_job && source.latest_job.retryable
  const displayStatus = job?.status ?? source.status
  return <li className="context-source-card"><div className="context-source-card__heading"><div className="context-source-title"><StatusIcon status={displayStatus} /><div><h2 dir="auto">{source.original_name ?? (source.source_type === "text" ? "متن چسبانده‌شده" : "منبع زمینه")}</h2><p>{source.source_type === "file" ? "فایل TXT" : "متن"}</p></div></div><span className="status-badge">{statusLabel(displayStatus)}</span></div><dl className="context-source-meta"><div><dt>ثبت‌شده</dt><dd><time dateTime={source.created_at}>{new Date(source.created_at).toLocaleString("fa-IR")}</time></dd></div>{source.latest_version ? <div><dt>نسخه</dt><dd>{source.latest_version.version_no.toLocaleString("fa-IR")}</dd></div> : null}</dl>{job?.error_code ? <p className="context-source-error" role="status">{safeErrorLabel(job.error_code)}</p> : null}<div className="context-source-actions">{retryable ? <button className="button button--secondary" type="button" disabled={pending} onClick={onRetry}>{pending ? "در حال ثبت…" : "تلاش دوباره"}</button> : null}{source.can_archive ? <button className="button button--danger" type="button" disabled={pending} onClick={onArchive}>{pending ? "در حال انجام…" : "بایگانی"}</button> : null}</div></li>
}

function StatusIcon({ status }: Readonly<{ status: string }>) {
  const complete = status === "succeeded" || status === "ready"
  const failed = status === "failed"
  return <svg className="context-source-status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-label={statusLabel(status)} role="img"><circle cx="12" cy="12" r="9" />{complete ? <path d="m8 12 3 3 5-6" /> : failed ? <path d="m9 9 6 6m0-6-6 6" /> : <path d="M12 7v5l3 2" />}</svg>
}

function SourceSubmitButton({ label, pendingLabel, primary = false }: Readonly<{ label: string; pendingLabel: string; primary?: boolean }>) { const { pending } = useFormStatus(); return <button className={`button ${primary ? "button--primary" : "button--secondary"}`} type="submit" disabled={pending}>{pending ? pendingLabel : label}</button> }
function ActionFeedback({ state }: Readonly<{ state: ContextSourceActionState }>) { return state.status === "idle" ? null : <div className={state.status === "error" ? "inline-alert" : "form-success"} role={state.status === "error" ? "alert" : "status"}><p>{state.message}</p>{state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}</div> }
function statusLabel(status: string) { return ({ uploaded: "ثبت‌شده", queued: "در صف پردازش", running: "در حال پردازش", parsing: "در حال پردازش", ready: "آماده", succeeded: "تکمیل‌شده", failed: "پردازش ناموفق", cancelled: "لغوشده" } as Record<string, string>)[status] ?? "وضعیت نامشخص" }
function safeErrorLabel(code: string) { return ({ PARSER_STORAGE_UNAVAILABLE: "دسترسی موقت به فایل ممکن نیست؛ می‌توانید دوباره تلاش کنید.", PARSER_STORAGE_REJECTED: "فایل ذخیره‌شده قابل پردازش نیست.", PARSER_EMPTY_CONTENT: "فایل محتوای متنی قابل استفاده ندارد.", PARSER_INVALID_INPUT: "محتوای فایل معتبر نیست.", PARSER_PERSISTENCE_UNAVAILABLE: "ثبت نتیجه پردازش موقتاً ممکن نیست." } as Record<string, string>)[code] ?? "پردازش منبع کامل نشد." }
