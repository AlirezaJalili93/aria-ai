"use client"

import { useActionState, useEffect, useRef } from "react"
import { useFormStatus } from "react-dom"

import { emitProductEvent } from "../analytics/product-events"
import { createProjectAction } from "./actions"
import type { AccountRole, CreateProjectState, ProjectType } from "./types"

type CreateProjectFormProps = Readonly<{
  accountId: string
  role: AccountRole
  initialState: CreateProjectState
}>

const projectTypes: readonly Readonly<{ value: ProjectType; label: string }>[] = [
  { value: "landing", label: "لندینگ" },
  { value: "corporate", label: "شرکتی" },
  { value: "portfolio", label: "پورتفولیو" }
]

export function CreateProjectForm({ accountId, role, initialState }: CreateProjectFormProps) {
  const [state, formAction] = useActionState(createProjectAction, initialState)
  const titleRef = useRef<HTMLInputElement>(null)
  const firstProjectTypeRef = useRef<HTMLInputElement>(null)
  const errorSummaryRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (state.fieldErrors.title) titleRef.current?.focus()
    else if (state.fieldErrors.projectType) firstProjectTypeRef.current?.focus()
    else if (state.status === "error") errorSummaryRef.current?.focus()
  }, [state.status, state.message, state.fieldErrors])

  return (
    <form className="project-form" action={formAction}>
      <div className="field-group">
        <label htmlFor="project-title">عنوان پروژه</label>
        <input
          id="project-title"
          ref={titleRef}
          className="text-field"
          name="title"
          type="text"
          minLength={1}
          maxLength={255}
          required
          aria-invalid={state.fieldErrors.title ? true : undefined}
          aria-describedby={state.fieldErrors.title ? "project-title-error" : undefined}
        />
        {state.fieldErrors.title ? (
          <p id="project-title-error" className="inline-alert" role="alert">
            {state.fieldErrors.title}
          </p>
        ) : null}
      </div>
      <fieldset className="project-type-fieldset" aria-describedby={state.fieldErrors.projectType ? "project-type-error" : undefined}>
        <legend>نوع پروژه</legend>
        <div className="project-type-options">
          {projectTypes.map((type) => (
            <label className="project-type-option" key={type.value}>
              <input
                ref={type.value === "landing" ? firstProjectTypeRef : undefined}
                name="project_type"
                type="radio"
                value={type.value}
                required
                onChange={() =>
                  emitProductEvent({
                    eventName: "project_type_selected",
                    accountId,
                    role,
                    projectType: type.value
                  })
                }
              />
              <span>{type.label}</span>
            </label>
          ))}
        </div>
        {state.fieldErrors.projectType ? (
          <p id="project-type-error" className="inline-alert" role="alert">
            {state.fieldErrors.projectType}
          </p>
        ) : null}
      </fieldset>
      {state.status === "error" ? (
        <div className="form-error-summary" ref={errorSummaryRef} tabIndex={-1} role="alert">
          <p>{state.message}</p>
          {state.requestId ? <p className="request-reference">شناسه پیگیری: {state.requestId}</p> : null}
        </div>
      ) : (
        <p className="form-status" aria-live="polite" />
      )}
      <CreateSubmitButton />
    </form>
  )
}

function CreateSubmitButton() {
  const { pending } = useFormStatus()
  return (
    <button className="button button--primary" type="submit" disabled={pending}>
      {pending ? "در حال ساخت…" : "ساخت پروژه"}
    </button>
  )
}
