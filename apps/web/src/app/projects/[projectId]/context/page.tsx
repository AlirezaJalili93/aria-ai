import { notFound, redirect } from "next/navigation"

import { fetchContextItems } from "../../../../features/context/api"
import { ContextReview } from "../../../../features/context/context-review"
import { ContextNavigation } from "../../../../features/context/context-navigation"
import { ProjectApiError, resolveProjectAccess } from "../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../features/projects/project-state"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function ContextPage({ params }: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const { projectId } = await params
  if (!uuidPattern.test(projectId)) notFound()
  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return <Failure message="زمینه پروژه بارگذاری نشد. دوباره تلاش کنید." error={error} />
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") {
    return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><AccountBlockedState reason={access.status} /></main>
  }
  let contextPage
  try {
    contextPage = await fetchContextItems(access.accessToken, access.account.id, projectId)
  } catch (error) {
    if (error instanceof ProjectApiError && error.status === 404) notFound()
    return <Failure message="زمینه پروژه بارگذاری نشد. دوباره تلاش کنید." error={error} />
  }
  return <main id="main-content" className="projects-main" tabIndex={-1}><ContextNavigation projectId={projectId} current="structured" /><ContextReview projectId={projectId} items={contextPage.data} /></main>
}

function Failure({ message, error }: Readonly<{ message: string; error: unknown }>) {
  return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message={message} {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main>
}
