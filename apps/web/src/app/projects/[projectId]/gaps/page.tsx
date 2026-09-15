import { notFound, redirect } from "next/navigation"

import { fetchGaps } from "../../../../features/gaps/api"
import { GapReview } from "../../../../features/gaps/gap-review"
import { ProjectApiError, resolveProjectAccess } from "../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../features/projects/project-state"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function GapsPage({ params }: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const { projectId } = await params
  if (!uuidPattern.test(projectId)) notFound()
  let access
  try { access = await resolveProjectAccess() } catch (error) { return <Failure error={error} /> }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><AccountBlockedState reason={access.status} /></main>
  let page
  try { page = await fetchGaps(access.accessToken, access.account.id, projectId) }
  catch (error) { if (error instanceof ProjectApiError && error.status === 404) notFound(); return <Failure error={error} /> }
  return <main id="main-content" className="projects-main" tabIndex={-1}><GapReview key={page.meta.request_id} projectId={projectId} initialPage={page} /></main>
}

function Failure({ error }: Readonly<{ error: unknown }>) { return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message="ابهام‌های پروژه بارگذاری نشد. دوباره تلاش کنید." {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main> }
