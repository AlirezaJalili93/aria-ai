"use client"

import { useActionState, useEffect, useRef, useState, useTransition } from "react"
import { useFormStatus } from "react-dom"
import { useRouter } from "next/navigation"

import { emitProductEvent } from "../analytics/product-events"
import type { AccountRole } from "../projects/types"
import {
  confirmRequirementAction,
  createRequirementAction,
  deactivateRequirementAction,
  editRequirementAction,
  loadRequirementsAction
} from "./actions"
import type {
  CreateRequirementState,
  Requirement,
  RequirementCategory,
  RequirementFilters,
  RequirementMutationState,
  RequirementPage,
  RequirementPriority,
  RequirementStatus
} from "./types"

const categories: readonly Readonly<{ value: RequirementCategory; label: string }>[] = [
  { value: "functional", label: "عملکردی" },
  { value: "content", label: "محتوا" },
  { value: "visual", label: "بصری" },
  { value: "technical", label: "فنی" },
  { value: "constraint", label: "محدودیت" },
  { value: "business", label: "کسب‌وکار" }
]
const priorityLabels: Readonly<Record<RequirementPriority, string>> = {
  must: "ضروری",
  should: "مهم",
  could: "اختیاری"
}
const statusLabels: Readonly<Record<RequirementStatus, string>> = {
  draft: "پیش‌نویس",
  confirmed: "تأییدشده",
  superseded: "جایگزین‌شده",
  removed: "غیرفعال"
}
const idleMutation: RequirementMutationState = { status: "idle", message: "" }

type RequirementReviewProps = Readonly<{
  accountId: string
  role: AccountRole
  projectId: string
  initialPage: RequirementPage
  initialCreateState: CreateRequirementState
}>

export function RequirementReview({ accountId, role, projectId, initialPage, initialCreateState }: RequirementReviewProps) {
  const [items, setItems] = useState(initialPage.data)
  const [meta, setMeta] = useState(initialPage.meta)
  const [category, setCategory] = useState<RequirementCategory | "all">("all")
  const [status, setStatus] = useState<RequirementStatus | "all">("all")
  const [requestFailure, setRequestFailure] = useState<Readonly<{ message: string; requestId?: string }> | null>(null)
  const [isPending, startTransition] = useTransition()

  function applyFilters(nextCategory: RequirementCategory | "all", nextStatus: RequirementStatus | "all") {
    setCategory(nextCategory)
    setStatus(nextStatus)
    setRequestFailure(null)
    const filters: RequirementFilters = {
      ...(nextCategory === "all" ? {} : { category: nextCategory }),
      ...(nextStatus === "all" ? {} : { status: nextStatus })
    }
    startTransition(async () => {
      const result = await loadRequirementsAction(projectId, filters)
      if (result.status === "error") {
        setRequestFailure({ message: result.message, ...(result.requestId ? { requestId: result.requestId } : {}) })
        return
      }
      setItems(result.page.data)
      setMeta(result.page.meta)
    })
  }

  function loadMore() {
    if (!meta.next_cursor) return
    setRequestFailure(null)
    const filters: RequirementFilters = {
      ...(category === "all" ? {} : { category }),
      ...(status === "all" ? {} : { status })
    }
    startTransition(async () => {
      const result = await loadRequirementsAction(projectId, filters, meta.next_cursor ?? undefined)
      if (result.status === "error") {
        setRequestFailure({ message: result.message, ...(result.requestId ? { requestId: result.requestId } : {}) })
        return
      }
      setItems((current) => [...current, ...result.page.data])
      setMeta(result.page.meta)
    })
  }

  return (
    <section className="requirement-review" aria-labelledby="requirement-review-title">
      <div className="section-heading requirement-heading">
        <div>
          <p className="eyebrow">Requirements</p>
          <h1 id="requirement-review-title">نیازمندی‌های پروژه</h1>
          <p className="section-intro">نیازمندی‌های استخراج‌شده یا دستی را بررسی و کنترل کنید.</p>
        </div>
        <details className="requirement-create-panel">
          <summary className="button button--primary">افزودن نیازمندی</summary>
          <CreateRequirementForm projectId={projectId} initialState={initialCreateState} />
        </details>
      </div>

      <div className="requirement-filters" aria-busy={isPending}>
        <label htmlFor="requirement-category-filter">
          دسته
          <select id="requirement-category-filter" className="text-field" value={category} onChange={(event) => applyFilters(event.target.value as RequirementCategory | "all", status)} disabled={isPending}>
            <option value="all">همه دسته‌ها</option>
            {categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label htmlFor="requirement-status-filter">
          وضعیت
          <select id="requirement-status-filter" className="text-field" value={status} onChange={(event) => applyFilters(category, event.target.value as RequirementStatus | "all")} disabled={isPending}>
            <option value="all">فعال‌ها</option>
            <option value="draft">پیش‌نویس</option>
            <option value="confirmed">تأییدشده</option>
            <option value="superseded">جایگزین‌شده</option>
            <option value="removed">غیرفعال</option>
          </select>
        </label>
        <p className="filter-status" aria-live="polite">{isPending ? "در حال اعمال فیلتر…" : ""}</p>
      </div>

      {requestFailure ? (
        <div className="inline-alert requirement-request-error" role="alert">
          <p>{requestFailure.message}</p>
          {requestFailure.requestId ? <p className="request-reference">شناسه پیگیری: {requestFailure.requestId}</p> : null}
          <button className="button button--secondary" type="button" onClick={() => applyFilters(category, status)} disabled={isPending}>تلاش دوباره</button>
        </div>
      ) : null}

      {!isPending && items.length === 0 ? (
        <div className="empty-state" role="status">
          <h2>{category === "all" && status === "all" ? "هنوز نیازمندی فعالی ثبت نشده است" : "نتیجه‌ای با این فیلترها پیدا نشد"}</h2>
          <p>{category === "all" && status === "all" ? "می‌توانید نخستین نیازمندی را به‌صورت دستی اضافه کنید." : "فیلترها را تغییر دهید یا پاک کنید."}</p>
          {category !== "all" || status !== "all" ? <button className="button button--secondary" type="button" onClick={() => applyFilters("all", "all")}>پاک کردن فیلترها</button> : null}
        </div>
      ) : (
        <div className="requirement-list" aria-live="polite">
          {items.map((item) => <RequirementCard accountId={accountId} role={role} item={item} projectId={projectId} key={item.id} />)}
        </div>
      )}

      {meta.has_more ? <button className="button button--secondary requirement-load-more" type="button" onClick={loadMore} disabled={isPending}>{isPending ? "در حال بارگذاری…" : "نمایش موارد بیشتر"}</button> : null}
    </section>
  )
}

function CreateRequirementForm({ projectId, initialState }: Readonly<{ projectId: string; initialState: CreateRequirementState }>) {
  const [state, action] = useActionState(createRequirementAction, initialState)
  const formRef = useRef<HTMLFormElement>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const router = useRouter()
  useEffect(() => {
    if (state.status === "success") {
      formRef.current?.reset()
      router.refresh()
    } else if (state.status === "error") errorRef.current?.focus()
  }, [router, state])
  return (
    <form className="requirement-form" action={action} ref={formRef}>
      <input type="hidden" name="project_id" value={projectId} />
      <div className="field-group">
        <label htmlFor="requirement-create-title">عنوان</label>
        <input id="requirement-create-title" className="text-field" name="title" type="text" maxLength={255} aria-invalid={state.fieldErrors.title ? true : undefined} />
        {state.fieldErrors.title ? <p className="inline-alert" role="alert">{state.fieldErrors.title}</p> : null}
      </div>
      <div className="field-group">
        <label htmlFor="requirement-create-description">توضیح</label>
        <textarea id="requirement-create-description" className="text-field requirement-textarea" name="description" />
      </div>
      <div className="requirement-form-grid">
        <label htmlFor="requirement-create-category">دسته
          <select id="requirement-create-category" className="text-field" name="category" defaultValue="" aria-invalid={state.fieldErrors.category ? true : undefined}>
            <option value="" disabled>انتخاب کنید</option>
            {categories.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label htmlFor="requirement-create-priority">اولویت
          <select id="requirement-create-priority" className="text-field" name="priority" defaultValue="" aria-invalid={state.fieldErrors.priority ? true : undefined}>
            <option value="" disabled>انتخاب کنید</option>
            {(Object.entries(priorityLabels) as [RequirementPriority, string][]).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </label>
      </div>
      {state.status !== "idle" ? <div className={state.status === "error" ? "form-error-summary" : "form-success"} ref={errorRef} tabIndex={-1} role={state.status === "error" ? "alert" : "status"}><p>{state.message}</p>{state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}</div> : null}
      <SubmitButton label="ثبت نیازمندی" pendingLabel="در حال ثبت…" />
    </form>
  )
}

function RequirementCard({ accountId, role, item, projectId }: Readonly<{ accountId: string; role: AccountRole; item: Requirement; projectId: string }>) {
  const [editState, editAction] = useActionState(editRequirementAction, idleMutation)
  const [confirmState, confirmAction] = useActionState(confirmRequirementAction, idleMutation)
  const [removeState, removeAction] = useActionState(deactivateRequirementAction, idleMutation)
  const [dirty, setDirty] = useState(false)
  const router = useRouter()
  const handledEvents = useRef(new Set<string>())
  const handledCompletions = useRef(new Set<string>())
  useUnsavedRequirementGuard(dirty)
  useEffect(() => {
    const states = [editState, confirmState, removeState]
    for (const state of states) {
      if (state.event && !handledEvents.current.has(state.event.eventId)) {
        handledEvents.current.add(state.event.eventId)
        emitProductEvent({ eventName: state.event.name, accountId, role, projectId, requirementId: state.event.requirementId })
      }
      if (state.completionId && !handledCompletions.current.has(state.completionId)) {
        handledCompletions.current.add(state.completionId)
        router.refresh()
      }
    }
  }, [accountId, confirmState, editState, projectId, removeState, role, router])
  const categoryLabel = categories.find((entry) => entry.value === item.category)?.label ?? item.category
  const mutable = item.status === "draft" || item.status === "confirmed"
  return (
    <article className={`requirement-card requirement-card--${item.status}`} aria-labelledby={`requirement-${item.id}`}>
      <div className="requirement-card__heading">
        <div>
          <p className="requirement-origin">{item.created_by_type === "ai" ? "پیشنهاد هوش مصنوعی" : "ثبت‌شده توسط کاربر"}</p>
          <h2 id={`requirement-${item.id}`}>{item.title}</h2>
        </div>
        <span className="status-badge">{statusLabels[item.status]}</span>
      </div>
      <p className="requirement-description" dir="auto">{item.description}</p>
      {item.is_unsupported ? <p className="requirement-warning" role="status">این نیازمندی پشتوانه کافی در زمینه فعلی ندارد.</p> : null}
      <dl className="requirement-meta">
        <div><dt>دسته</dt><dd>{categoryLabel}</dd></div>
        <div><dt>اولویت</dt><dd>{priorityLabels[item.priority]}</dd></div>
        <div><dt>نسخه زمینه</dt><dd>{item.context_version.toLocaleString("fa-IR")}</dd></div>
        <div><dt>اعتماد</dt><dd>{item.confidence === null ? "ثبت نشده" : `${Math.round(item.confidence * 100).toLocaleString("fa-IR")}٪`}</dd></div>
      </dl>
      {item.acceptance_note !== null ? <section className="requirement-note" aria-label="یادداشت پذیرش"><h3>یادداشت پذیرش</h3><p dir="auto">{item.acceptance_note}</p></section> : null}
      {item.source_refs.length ? <details className="requirement-source-trace"><summary>مشاهده ردپای منبع</summary><ul>{item.source_refs.map((reference) => <li dir="ltr" key={`${reference.source_id}-${reference.source_version_id}-${reference.start_offset ?? "full"}`}><span>source: {reference.source_id}</span><span>version: {reference.source_version_id}</span><span>{reference.start_offset === undefined ? "full version" : `[${reference.start_offset}, ${reference.end_offset})`}</span></li>)}</ul></details> : <p className="requirement-no-source">منبع ساختاری برای این نیازمندی ثبت نشده است.</p>}
      {mutable ? (
        <div className="requirement-actions">
          {item.status === "draft" ? <><form action={confirmAction} onSubmit={(event) => { if (dirty && !window.confirm("تغییرات ویرایش ذخیره نشده‌اند. نیازمندی بدون این تغییرات تأیید شود؟")) event.preventDefault() }}><MutationFields item={item} projectId={projectId} /><SubmitButton label="تأیید نیازمندی" pendingLabel="در حال تأیید…" secondary /></form><MutationFeedback state={confirmState} /></> : null}
          <details className="requirement-edit-panel">
            <summary>ویرایش نیازمندی</summary>
            <form action={editAction} onChange={() => setDirty(true)}>
              <MutationFields item={item} projectId={projectId} />
              {item.status === "confirmed" ? <p className="requirement-warning">ذخیره ویرایش، وضعیت این نیازمندی را به پیش‌نویس برمی‌گرداند.</p> : null}
              <label htmlFor={`requirement-title-${item.id}`}>عنوان<input id={`requirement-title-${item.id}`} className="text-field" name="title" type="text" maxLength={255} defaultValue={item.title} /></label>
              <label htmlFor={`requirement-description-${item.id}`}>توضیح<textarea id={`requirement-description-${item.id}`} className="text-field requirement-textarea" name="description" defaultValue={item.description} /></label>
              <label htmlFor={`requirement-priority-${item.id}`}>اولویت<select id={`requirement-priority-${item.id}`} className="text-field" name="priority" defaultValue={item.priority}>{(Object.entries(priorityLabels) as [RequirementPriority, string][]).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
              <label htmlFor={`requirement-note-${item.id}`}>یادداشت پذیرش<textarea id={`requirement-note-${item.id}`} className="text-field requirement-textarea" name="acceptance_note" defaultValue={item.acceptance_note ?? ""} /></label>
              <SubmitButton label="ذخیره ویرایش" pendingLabel="در حال ذخیره…" secondary />
            </form>
          </details>
          <MutationFeedback state={editState} />
          {item.status === "draft" ? <><form action={removeAction} onSubmit={(event) => { if (!window.confirm("این نیازمندی غیرفعال شود؟")) event.preventDefault() }}><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="requirement_id" value={item.id} /><SubmitButton label="غیرفعال‌سازی" pendingLabel="در حال غیرفعال‌سازی…" danger /></form><MutationFeedback state={removeState} /></> : null}
        </div>
      ) : <p className="requirement-readonly" role="status">این نیازمندی فقط‌خواندنی است.</p>}
    </article>
  )
}

function MutationFeedback({ state }: Readonly<{ state: RequirementMutationState }>) {
  if (state.status === "idle") return null
  return <div className={state.status === "error" ? "inline-alert" : "form-success"} role={state.status === "error" ? "alert" : "status"}><p>{state.message}</p>{state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}</div>
}

function MutationFields({ item, projectId }: Readonly<{ item: Requirement; projectId: string }>) {
  return <><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="requirement_id" value={item.id} /><input type="hidden" name="expected_updated_at" value={item.updated_at} /></>
}

function SubmitButton({ label, pendingLabel, secondary = false, danger = false }: Readonly<{ label: string; pendingLabel: string; secondary?: boolean; danger?: boolean }>) {
  const { pending } = useFormStatus()
  return <button className={`button ${danger ? "button--danger" : secondary ? "button--secondary" : "button--primary"}`} type="submit" disabled={pending}>{pending ? pendingLabel : label}</button>
}

function useUnsavedRequirementGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return
    const beforeUnload = (event: BeforeUnloadEvent) => event.preventDefault()
    const linkNavigation = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null
      if (target && !window.confirm("تغییرات ذخیره‌نشده باقی مانده است. از صفحه خارج می‌شوید؟")) event.preventDefault()
    }
    window.addEventListener("beforeunload", beforeUnload)
    document.addEventListener("click", linkNavigation, true)
    return () => {
      window.removeEventListener("beforeunload", beforeUnload)
      document.removeEventListener("click", linkNavigation, true)
    }
  }, [dirty])
}
