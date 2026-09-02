import { randomUUID } from "node:crypto"
import Link from "next/link"
import { redirect } from "next/navigation"

import { resolveProjectAccess, ProjectApiError } from "../../../features/projects/api"
import { CreateProjectForm } from "../../../features/projects/create-project-form"
import { AccountBlockedState, ProjectRequestFailure } from "../../../features/projects/project-state"

export default async function NewProjectPage() {
  let access
  let accessFailure: unknown
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    accessFailure = error
  }
  if (accessFailure || !access) {
    return (
      <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
        <ProjectRequestFailure
          message="فرم ساخت پروژه بارگذاری نشد. دوباره تلاش کنید."
          {...(accessFailure instanceof ProjectApiError ? { requestId: accessFailure.requestId } : {})}
        />
      </main>
    )
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") {
    return (
      <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
        <AccountBlockedState reason={access.status} />
      </main>
    )
  }
  return (
    <main id="main-content" className="projects-main" tabIndex={-1}>
      <section className="project-form-shell" aria-labelledby="create-project-title">
        <Link className="back-link" href="/projects">
          بازگشت به پروژه‌ها
        </Link>
        <p className="eyebrow">پروژه جدید</p>
        <h1 id="create-project-title">ساخت پروژه</h1>
        <p className="section-intro">عنوان و نوع پروژه را مشخص کنید.</p>
        <CreateProjectForm
          accountId={access.account.id}
          role={access.account.role}
          initialState={{
            status: "idle",
            message: "",
            idempotencyKey: randomUUID(),
            submissionFingerprint: null,
            fieldErrors: {}
          }}
        />
      </section>
    </main>
  )
}
