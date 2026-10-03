"use client"

import { useActionState, useMemo, useState } from "react"
import { useFormStatus } from "react-dom"

import {
  confirmContextItemAction,
  editContextItemAction,
  rejectContextItemAction
} from "./actions"
import type { ContextItem, ContextItemStatus, ContextItemType, ContextReviewActionState } from "./types"

const initialActionState: ContextReviewActionState = { status: "idle", message: "" }
const tabs: readonly Readonly<{ type: ContextItemType; label: string }>[]= [
  { type: "fact", label: "واقعیت‌ها" },
  { type: "assumption", label: "فرضیات" },
  { type: "constraint", label: "محدودیت‌ها" },
  { type: "decision", label: "تصمیم‌ها" },
  { type: "reference", label: "مراجع" },
  { type: "unknown", label: "اطلاعات ناقص" }
]
const statusLabels: Readonly<Record<ContextItemStatus, string>> = {
  proposed: "نیازمند بازبینی",
  confirmed: "تأییدشده",
  rejected: "ردشده",
  superseded: "منسوخ‌شده"
}

export function ContextReview({ projectId, items }: Readonly<{ projectId: string; items: readonly ContextItem[] }>) {
  const [selectedType, setSelectedType] = useState<ContextItemType | "all">("all")
  const [selectedStatus, setSelectedStatus] = useState<ContextItemStatus | "all">("all")
  const filteredItems = useMemo(
    () => items.filter((item) => (selectedType === "all" || item.item_type === selectedType) && (selectedStatus === "all" || item.status === selectedStatus)),
    [items, selectedStatus, selectedType]
  )
  return (
    <section className="context-review" aria-labelledby="context-review-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Structured Context</p>
          <h1 id="context-review-title">مرور زمینه ساختاریافته</h1>
          <p className="section-intro">هر مورد را بررسی کنید؛ فرضیات از واقعیت‌های تأییدشده جدا نگه داشته می‌شوند.</p>
        </div>
      </div>
      <div className="context-filters">
        <div className="context-tabs" role="tablist" aria-label="فیلتر نوع آیتم">
          <button className={`context-tab${selectedType === "all" ? " context-tab--active" : ""}`} type="button" role="tab" aria-selected={selectedType === "all"} onClick={() => setSelectedType("all")}>همه</button>
          {tabs.map((tab) => (
            <button className={`context-tab${selectedType === tab.type ? " context-tab--active" : ""}`} type="button" role="tab" aria-selected={selectedType === tab.type} key={tab.type} onClick={() => setSelectedType(tab.type)}>
              {tab.label}
            </button>
          ))}
        </div>
        <label className="context-status-filter" htmlFor="context-status-filter">
          فیلتر وضعیت
          <select id="context-status-filter" className="text-field" value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value as ContextItemStatus | "all")}>
            <option value="all">همه وضعیت‌ها</option>
            <option value="proposed">نیازمند بازبینی</option>
            <option value="confirmed">تأییدشده</option>
            <option value="rejected">ردشده</option>
            <option value="superseded">منسوخ‌شده</option>
          </select>
        </label>
      </div>
      {filteredItems.length === 0 ? (
        <div className="empty-state" role="status">
          <h2>موردی برای نمایش وجود ندارد</h2>
          <p>با تغییر فیلترها دوباره بررسی کنید.</p>
        </div>
      ) : (
        <div className="context-item-list">
          {filteredItems.map((item) => <ContextItemCard key={item.id} item={item} projectId={projectId} />)}
        </div>
      )}
    </section>
  )
}

function ContextItemCard({ item, projectId }: Readonly<{ item: ContextItem; projectId: string }>) {
  const [confirmState, confirmAction] = useActionState(async (_: ContextReviewActionState, formData: FormData) => confirmContextItemAction(formData), initialActionState)
  const [rejectState, rejectAction] = useActionState(async (_: ContextReviewActionState, formData: FormData) => rejectContextItemAction(formData), initialActionState)
  const [editState, editAction] = useActionState(async (_: ContextReviewActionState, formData: FormData) => editContextItemAction(formData), initialActionState)
  const actionState = confirmState.status === "error" ? confirmState : rejectState.status === "error" ? rejectState : editState
  const typeLabel = tabs.find((tab) => tab.type === item.item_type)?.label ?? item.item_type
  return (
    <article className={`context-item-card context-item-card--${item.item_type}`} aria-labelledby={`context-item-${item.id}`}>
      <div className="context-item-card__heading">
        <div>
          <span className="context-item-type">{typeLabel}</span>
          <h2 id={`context-item-${item.id}`}>آیتم زمینه</h2>
        </div>
        <span className="status-badge">{statusLabels[item.status]}</span>
      </div>
      <p className="context-item-content" dir="auto">{item.content}</p>
      <dl className="context-item-meta">
        <div><dt>اعتماد</dt><dd>{item.confidence === null ? "ثبت نشده" : `${Math.round(item.confidence * 100)}٪`}</dd></div>
        <div><dt>منبع</dt><dd>{item.source_refs.length ? `${item.source_refs.length} مرجع ساختاری` : "بدون مرجع"}</dd></div>
      </dl>
      {item.source_refs.length ? (
        <details className="context-source-trace">
          <summary>نمایش ردپای منبع</summary>
          <ul>
            {item.source_refs.map((reference) => <li dir="ltr" key={`${reference.source_id}-${reference.source_version_id}-${reference.start_offset ?? "full"}`}>{reference.source_id}{reference.start_offset === undefined ? " · کل نسخه" : ` · ${reference.start_offset}–${reference.end_offset}`}</li>)}
          </ul>
        </details>
      ) : null}
      {item.status === "proposed" ? (
        <div className="context-item-actions">
          <div className="button-row">
            <form action={confirmAction}>
              <ReviewFields projectId={projectId} item={item} />
              <ReviewSubmitButton label="تأیید" pendingLabel="در حال تأیید…" />
            </form>
            <form action={rejectAction}>
              <ReviewFields projectId={projectId} item={item} />
              <ReviewSubmitButton label="رد کردن" pendingLabel="در حال ثبت…" secondary />
            </form>
          </div>
          <details className="context-edit">
            <summary>ویرایش محتوا</summary>
            <form action={editAction}>
              <ReviewFields projectId={projectId} item={item} />
              <label htmlFor={`context-edit-${item.id}`}>محتوای اصلاح‌شده</label>
              <textarea id={`context-edit-${item.id}`} className="text-field context-edit__field" name="content" defaultValue={item.content} required />
              <ReviewSubmitButton label="ثبت ویرایش" pendingLabel="در حال ذخیره…" />
            </form>
          </details>
          {actionState.status === "error" ? <p className="inline-alert" role="alert">{actionState.message}</p> : null}
        </div>
      ) : null}
    </article>
  )
}

function ReviewFields({ projectId, item }: Readonly<{ projectId: string; item: ContextItem }>) {
  return <><input type="hidden" name="project_id" value={projectId} /><input type="hidden" name="item_id" value={item.id} /><input type="hidden" name="expected_updated_at" value={item.updated_at} /></>
}

function ReviewSubmitButton({ label, pendingLabel, secondary = false }: Readonly<{ label: string; pendingLabel: string; secondary?: boolean }>) {
  const { pending } = useFormStatus()
  return <button className={`button ${secondary ? "button--secondary" : "button--primary"}`} type="submit" disabled={pending}>{pending ? pendingLabel : label}</button>
}
