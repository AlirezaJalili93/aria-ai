"use client"

import { useActionState, useEffect, useState } from "react"
import { useFormStatus } from "react-dom"

import { emitProductEvent } from "../analytics/product-events"
import { saveScopeSectionAction } from "./actions"
import type {
  ScopeDraft,
  ScopeItem,
  ScopeMutationState,
  ScopeSection,
  ScopeSectionId,
  ScopeSectionValue
} from "./types"

const labels: Readonly<Record<ScopeSectionId, string>> = {
  summary: "خلاصه پروژه",
  goals: "اهداف",
  pages_sections: "صفحه‌ها و بخش‌ها",
  requirements: "نیازمندی‌ها",
  content: "نیازهای محتوایی",
  visual_direction: "جهت بصری",
  constraints: "محدودیت‌ها",
  assumptions: "فرض‌ها",
  resolved_gaps: "ابهام‌های رفع‌شده",
  remaining_non_blocking_gaps: "ابهام‌های غیربازدارنده",
  out_of_scope: "خارج از محدوده",
  acceptance_notes: "یادداشت‌های پذیرش"
}
const stringArraySections = new Set<ScopeSectionId>([
  "goals", "constraints", "assumptions", "out_of_scope", "acceptance_notes"
])
const idleState: ScopeMutationState = { status: "idle", message: "" }

export function ScopeEditor({ projectId, draft }: Readonly<{ projectId: string; draft: ScopeDraft }>) {
  const initialValues = Object.fromEntries(
    draft.content.sections.map((section) => [section.section_id, clone(section.value)])
  ) as Record<ScopeSectionId, ScopeSectionValue>
  const [activeId, setActiveId] = useState<ScopeSectionId>("summary")
  const [values, setValues] = useState<Record<ScopeSectionId, ScopeSectionValue>>(initialValues)
  const [savedValues, setSavedValues] = useState<Record<ScopeSectionId, ScopeSectionValue>>(initialValues)
  const [draftUpdatedAt, setDraftUpdatedAt] = useState(draft.updated_at)
  const [dirty, setDirty] = useState(false)
  const active = draft.content.sections.find((section) => section.section_id === activeId)
  if (!active) throw new Error("Canonical Scope section is missing")

  useUnsavedScopeGuard(dirty)
  function selectSection(sectionId: ScopeSectionId) {
    if (dirty && !window.confirm("تغییرات ذخیره‌نشده این بخش کنار گذاشته شود؟")) return
    if (dirty) {
      setValues((current) => ({ ...current, [activeId]: clone(savedValues[activeId]) }))
    }
    setDirty(false)
    setActiveId(sectionId)
  }
  function update(value: ScopeSectionValue) {
    setValues((current) => ({ ...current, [activeId]: value }))
    setDirty(true)
  }

  return (
    <section className="scope-editor" aria-labelledby="scope-editor-title">
      <header className="section-heading scope-heading">
        <div>
          <p className="eyebrow">Scope Draft</p>
          <h1 id="scope-editor-title">پیش‌نویس محدوده پروژه</h1>
          <p className="section-intro">هر بخش را جداگانه مرور و با ذخیره صریح ثبت کنید.</p>
        </div>
        <p className="scope-version">نسخه زمینه: {draft.context_version.toLocaleString("fa-IR")}</p>
      </header>
      <div className="scope-layout">
        <nav className="scope-section-nav" aria-label="بخش‌های پیش‌نویس">
          {draft.content.sections.map((section) => (
            <button
              className={section.section_id === activeId ? "scope-nav-button scope-nav-button--active" : "scope-nav-button"}
              type="button"
              aria-current={section.section_id === activeId ? "page" : undefined}
              onClick={() => selectSection(section.section_id)}
              key={section.section_id}
            >
              {labels[section.section_id]}
            </button>
          ))}
        </nav>
        <ScopeSectionForm
          key={activeId}
          projectId={projectId}
          section={active}
          initialUpdatedAt={draftUpdatedAt}
          value={values[activeId]}
          dirty={dirty}
          onChange={update}
          onSaved={(updatedAt) => {
            setSavedValues((current) => ({ ...current, [activeId]: clone(values[activeId]) }))
            setDraftUpdatedAt(updatedAt)
            setDirty(false)
          }}
        />
      </div>
    </section>
  )
}

function ScopeSectionForm({ projectId, section, initialUpdatedAt, value, dirty, onChange, onSaved }: Readonly<{
  projectId: string
  section: ScopeSection
  initialUpdatedAt: string
  value: ScopeSectionValue
  dirty: boolean
  onChange: (value: ScopeSectionValue) => void
  onSaved: (updatedAt: string) => void
}>) {
  const [state, action] = useActionState(async (previousState: ScopeMutationState, formData: FormData) => {
    const result = await saveScopeSectionAction(previousState, formData)
    if (result.status === "success") {
      if (result.updatedAt) onSaved(result.updatedAt)
      if (result.event) emitProductEvent({
        eventName: "scope_edited",
        projectId,
        sectionId: result.event.sectionId,
        contextVersion: result.event.contextVersion
      })
    }
    return result
  }, idleState)
  const expectedUpdatedAt = state.updatedAt ?? initialUpdatedAt
  return (
    <article className="scope-section-card" aria-labelledby={`scope-${section.section_id}`}>
      <div className="scope-section-heading">
        <h2 id={`scope-${section.section_id}`}>{labels[section.section_id]}</h2>
        {dirty ? <span className="status-badge">ذخیره‌نشده</span> : null}
      </div>
      <TraceSummary section={section} />
      <form action={action} className="scope-section-form">
        <input type="hidden" name="project_id" value={projectId} />
        <input type="hidden" name="section_id" value={section.section_id} />
        <input type="hidden" name="expected_updated_at" value={expectedUpdatedAt} />
        <input type="hidden" name="value" value={JSON.stringify(value)} />
        <SectionValueEditor sectionId={section.section_id} value={value} onChange={onChange} />
        <SaveButton disabled={!dirty || state.reason === "stale"} />
      </form>
      {state.status !== "idle" ? (
        <div className={state.status === "error" ? "inline-alert scope-save-feedback" : "form-success scope-save-feedback"} role={state.status === "error" ? "alert" : "status"} aria-live="polite">
          <p>{state.message}</p>
          {state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}
        </div>
      ) : null}
    </article>
  )
}

function SectionValueEditor({ sectionId, value, onChange }: Readonly<{ sectionId: ScopeSectionId; value: ScopeSectionValue; onChange: (value: ScopeSectionValue) => void }>) {
  if (sectionId === "summary" || sectionId === "visual_direction") {
    return <label htmlFor={`scope-value-${sectionId}`}>متن بخش<textarea id={`scope-value-${sectionId}`} className="text-field scope-textarea" value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)} /></label>
  }
  if (stringArraySections.has(sectionId)) {
    const items = isStringArray(value) ? value : []
    return <StringListEditor sectionId={sectionId} items={items} onChange={onChange} />
  }
  const items = isObjectArray(value) ? value : []
  return <StructuredListEditor sectionId={sectionId} items={items} onChange={onChange} />
}

function StringListEditor({ sectionId, items, onChange }: Readonly<{ sectionId: ScopeSectionId; items: readonly string[]; onChange: (value: ScopeSectionValue) => void }>) {
  return <div className="scope-item-list">
    {items.map((item, index) => <div className="scope-list-row" key={`${sectionId}-${index}`}><label>مورد {index + 1}<input className="text-field" value={item} onChange={(event) => onChange(items.map((current, itemIndex) => itemIndex === index ? event.target.value : current))} /></label><button className="button button--secondary" type="button" onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>حذف مورد</button></div>)}
    <button className="button button--secondary" type="button" onClick={() => onChange([...items, ""])}>افزودن مورد</button>
  </div>
}

function StructuredListEditor({ sectionId, items, onChange }: Readonly<{ sectionId: ScopeSectionId; items: readonly ScopeItem[]; onChange: (value: ScopeSectionValue) => void }>) {
  if (sectionId === "pages_sections") return <PagesEditor items={items} onChange={onChange} />
  const fields = structuredFields(sectionId)
  return <div className="scope-item-list">
    {items.map((item, index) => <fieldset className="scope-structured-item" key={typeof item.item_id === "string" ? item.item_id : `${sectionId}-new-${index}`}><legend>مورد {index + 1}</legend>{fields.map((field) => <FieldEditor key={field.key} field={field} value={item[field.key]} onChange={(next) => onChange(items.map((current, itemIndex) => itemIndex === index ? { ...current, [field.key]: next } : current))} />)}<button className="button button--secondary" type="button" onClick={() => onChange(items.filter((_, itemIndex) => itemIndex !== index))}>حذف مورد</button></fieldset>)}
    <button className="button button--secondary" type="button" onClick={() => onChange([...items, emptyStructuredItem(sectionId)])}>افزودن مورد</button>
  </div>
}

type FieldDefinition = Readonly<{ key: string; label: string; options?: readonly string[] }>
function structuredFields(sectionId: ScopeSectionId): readonly FieldDefinition[] {
  if (sectionId === "requirements") return [{ key: "text", label: "نیازمندی" }, { key: "priority", label: "اولویت", options: ["must", "should", "could"] }]
  if (sectionId === "content") return [{ key: "description", label: "نیاز محتوایی" }]
  if (sectionId === "resolved_gaps") return [{ key: "text", label: "ابهام رفع‌شده" }, { key: "resolution_type", label: "نوع راه‌حل" }]
  return [{ key: "text", label: "ابهام غیربازدارنده" }, { key: "severity", label: "شدت", options: ["critical", "high", "medium", "low"] }]
}
function emptyStructuredItem(sectionId: ScopeSectionId): ScopeItem {
  return Object.fromEntries(structuredFields(sectionId).map((field) => [field.key, field.options?.[0] ?? ""]))
}
function FieldEditor({ field, value, onChange }: Readonly<{ field: FieldDefinition; value: unknown; onChange: (value: string) => void }>) {
  return <label>{field.label}{field.options ? <select className="text-field" value={typeof value === "string" ? value : field.options[0]} onChange={(event) => onChange(event.target.value)}>{field.options.map((option) => <option value={option} key={option}>{option}</option>)}</select> : <input className="text-field" value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)} />}</label>
}

function PagesEditor({ items, onChange }: Readonly<{ items: readonly ScopeItem[]; onChange: (value: ScopeSectionValue) => void }>) {
  return <div className="scope-item-list">{items.map((page, pageIndex) => {
    const sections = isObjectArray(page.sections) ? page.sections : []
    return <fieldset className="scope-structured-item" key={typeof page.item_id === "string" ? page.item_id : `new-page-${pageIndex}`}><legend>صفحه {pageIndex + 1}</legend><label>نام صفحه<input className="text-field" value={typeof page.page_name === "string" ? page.page_name : ""} onChange={(event) => onChange(items.map((current, index) => index === pageIndex ? { ...current, page_name: event.target.value } : current))} /></label>{sections.map((section, sectionIndex) => <div className="scope-list-row" key={typeof section.item_id === "string" ? section.item_id : `new-section-${sectionIndex}`}><label>نام بخش<input className="text-field" value={typeof section.name === "string" ? section.name : ""} onChange={(event) => onChange(items.map((current, index) => index === pageIndex ? { ...current, sections: sections.map((candidate, nestedIndex) => nestedIndex === sectionIndex ? { ...candidate, name: event.target.value } : candidate) } : current))} /></label><button className="button button--secondary" type="button" onClick={() => onChange(items.map((current, index) => index === pageIndex ? { ...current, sections: sections.filter((_, nestedIndex) => nestedIndex !== sectionIndex) } : current))}>حذف بخش</button></div>)}<button className="button button--secondary" type="button" onClick={() => onChange(items.map((current, index) => index === pageIndex ? { ...current, sections: [...sections, { name: "" }] } : current))}>افزودن بخش</button><button className="button button--secondary" type="button" onClick={() => onChange(items.filter((_, index) => index !== pageIndex))}>حذف صفحه</button></fieldset>
  })}<button className="button button--secondary" type="button" onClick={() => onChange([...items, { page_name: "", sections: [] }])}>افزودن صفحه</button></div>
}

function TraceSummary({ section }: Readonly<{ section: ScopeSection }>) {
  const total = section.trace.context_item_ids.length + section.trace.requirement_ids.length + section.trace.gap_ids.length
  return <details className="scope-trace"><summary>ردپای اولیه استخراج ({total.toLocaleString("fa-IR")})</summary><p>این پیوندها منشأ اولیه تولید بخش را نشان می‌دهند و پس از ویرایش، اثبات معنایی محتوای فعلی نیستند.</p></details>
}
function SaveButton({ disabled }: Readonly<{ disabled: boolean }>) {
  const { pending } = useFormStatus()
  return <button className="button button--primary" type="submit" disabled={disabled || pending}>{pending ? "در حال ذخیره…" : "ذخیره بخش"}</button>
}
function useUnsavedScopeGuard(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return
    const unload = (event: BeforeUnloadEvent) => event.preventDefault()
    const navigate = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a") : null
      if (target && !window.confirm("بدون ذخیره تغییرات از صفحه خارج شوید؟")) event.preventDefault()
    }
    window.addEventListener("beforeunload", unload)
    document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [dirty])
}
function clone(value: ScopeSectionValue): ScopeSectionValue { return JSON.parse(JSON.stringify(value)) as ScopeSectionValue }
function isStringArray(value: ScopeSectionValue): value is readonly string[] { return Array.isArray(value) && value.every((item) => typeof item === "string") }
function isObjectArray(value: unknown): value is readonly ScopeItem[] { return Array.isArray(value) && value.every((item) => typeof item === "object" && item !== null && !Array.isArray(item)) }
