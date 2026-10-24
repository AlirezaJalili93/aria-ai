import { randomUUID } from "node:crypto"
import { notFound, redirect } from "next/navigation"

import { ContextInbox } from "../../../../../features/context-sources/context-inbox"
import { fetchContextSources } from "../../../../../features/context-sources/api"
import { ContextNavigation } from "../../../../../features/context/context-navigation"
import { ProjectApiError, resolveProjectAccess } from "../../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../../features/projects/project-state"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function ContextSourcesPage({ params }: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const { projectId } = await params
  if (!uuidPattern.test(projectId)) notFound()
  let access
  try { access = await resolveProjectAccess() }
  catch (error) { return <Failure error={error} /> }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><AccountBlockedState reason={access.status} /></main>
  let page
  try { page = await fetchContextSources(access.accessToken, access.account.id, projectId) }
  catch (error) {
    if (error instanceof ProjectApiError && error.status === 404) notFound()
    return <Failure error={error} />
  }
  const uploadEnabled = process.env.NEXT_PUBLIC_TXT_UPLOAD_ENABLED === "true"
  return <main id="main-content" className="projects-main" tabIndex={-1}><ContextNavigation projectId={projectId} current="sources" /><ContextInbox key={page.meta.request_id} projectId={projectId} initialPage={page} uploadEnabled={uploadEnabled} textIdempotencyKey={randomUUID()} uploadIdempotencyKey={randomUUID()} /></main>
}

function Failure({ error }: Readonly<{ error: unknown }>) { return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message="منابع زمینه بارگذاری نشدند. دوباره تلاش کنید." {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main> }
