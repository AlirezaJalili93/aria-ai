import { notFound, redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../features/projects/project-state"
import { fetchCurrentScopeDraft } from "../../../../features/scope/api"
import { ScopeEditor } from "../../../../features/scope/scope-editor"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function ScopePage({ params }: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const { projectId } = await params
  if (!uuidPattern.test(projectId)) notFound()
  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return <Failure error={error} />
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") {
    return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><AccountBlockedState reason={access.status} /></main>
  }
  let draft
  try {
    draft = await fetchCurrentScopeDraft(access.accessToken, access.account.id, projectId)
  } catch (error) {
    if (error instanceof ProjectApiError && error.status === 404) {
      return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><section className="empty-state" role="status"><h1>پیش‌نویس محدوده هنوز ایجاد نشده است</h1><p>پس از آماده‌شدن پیش‌نویس، ویرایش بخش‌ها در این صفحه در دسترس خواهد بود.</p></section></main>
    }
    return <Failure error={error} />
  }
  return <main id="main-content" className="projects-main" tabIndex={-1}><ScopeEditor accountId={access.account.id} projectId={projectId} draft={draft} /></main>
}

function Failure({ error }: Readonly<{ error: unknown }>) {
  return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message="پیش‌نویس محدوده بارگذاری نشد. دوباره تلاش کنید." {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main>
}
