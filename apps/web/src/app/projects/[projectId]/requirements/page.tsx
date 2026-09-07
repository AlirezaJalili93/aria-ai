import { randomUUID } from "node:crypto"
import { notFound, redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../features/projects/project-state"
import { fetchRequirements } from "../../../../features/requirements/api"
import { RequirementReview } from "../../../../features/requirements/requirement-review"
import type { CreateRequirementState } from "../../../../features/requirements/types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function RequirementsPage({ params }: Readonly<{ params: Promise<{ projectId: string }> }>) {
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

  let requirementPage
  try {
    requirementPage = await fetchRequirements(access.accessToken, access.account.id, projectId)
  } catch (error) {
    if (error instanceof ProjectApiError && error.status === 404) notFound()
    return <Failure error={error} />
  }
  const initialCreateState: CreateRequirementState = {
    status: "idle",
    message: "",
    idempotencyKey: randomUUID(),
    submissionFingerprint: null,
    fieldErrors: {}
  }
  return (
    <main id="main-content" className="projects-main" tabIndex={-1}>
      <RequirementReview key={requirementPage.meta.request_id} accountId={access.account.id} role={access.account.role} projectId={projectId} initialPage={requirementPage} initialCreateState={initialCreateState} />
    </main>
  )
}

function Failure({ error }: Readonly<{ error: unknown }>) {
  return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message="نیازمندی‌های پروژه بارگذاری نشد. دوباره تلاش کنید." {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main>
}
