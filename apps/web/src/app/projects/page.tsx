import { redirect } from "next/navigation"

import { fetchProjects, ProjectApiError, resolveProjectAccess } from "../../features/projects/api"
import { ProjectList } from "../../features/projects/project-list"
import { AccountBlockedState, ProjectRequestFailure } from "../../features/projects/project-state"

export default async function ProjectsPage() {
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
          message="یک خطای موقت رخ داد. دوباره تلاش کنید."
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
  let page
  let pageFailure: unknown
  try {
    page = await fetchProjects(access.accessToken, access.account.id)
  } catch (error) {
    pageFailure = error
  }
  if (pageFailure || !page) {
    return (
      <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
        <ProjectRequestFailure
          message="یک خطای موقت رخ داد. دوباره تلاش کنید."
          {...(pageFailure instanceof ProjectApiError ? { requestId: pageFailure.requestId } : {})}
        />
      </main>
    )
  }
  return (
    <main id="main-content" className="projects-main" tabIndex={-1}>
      <ProjectList
        initialProjects={page.data.map((project) => ({
          id: project.id,
          title: project.title,
          project_type: project.project_type,
          status: project.status,
          updated_at: project.updated_at
        }))}
        initialNextCursor={page.meta.next_cursor}
        initialHasMore={page.meta.has_more}
      />
    </main>
  )
}
