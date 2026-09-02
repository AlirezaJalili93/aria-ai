import { notFound, redirect } from "next/navigation"

import { fetchProject, ProjectApiError, resolveProjectAccess } from "../../../features/projects/api"
import { ProjectOverview } from "../../../features/projects/project-overview"
import { AccountBlockedState, ProjectRequestFailure } from "../../../features/projects/project-state"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function ProjectOverviewPage({
  params
}: Readonly<{ params: Promise<{ projectId: string }> }>) {
  const { projectId } = await params
  if (!uuidPattern.test(projectId)) notFound()

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
          message="پروژه بارگذاری نشد. دوباره تلاش کنید."
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

  let project
  let projectFailure: unknown
  try {
    project = await fetchProject(access.accessToken, access.account.id, projectId)
  } catch (error) {
    projectFailure = error
  }
  if (projectFailure instanceof ProjectApiError && projectFailure.status === 404) notFound()
  if (projectFailure || !project) {
    return (
      <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
        <ProjectRequestFailure
          message="پروژه بارگذاری نشد. دوباره تلاش کنید."
          {...(projectFailure instanceof ProjectApiError ? { requestId: projectFailure.requestId } : {})}
        />
      </main>
    )
  }

  return (
    <main id="main-content" className="projects-main" tabIndex={-1}>
      <ProjectOverview account={access.account} project={project} />
    </main>
  )
}
