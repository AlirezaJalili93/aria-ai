import { notFound, redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../../../../../../../features/projects/api"
import { AccountBlockedState, ProjectRequestFailure } from "../../../../../../../features/projects/project-state"
import { fetchScopeDecision, fetchScopeShares, fetchScopeVersionForSharing } from "../../../../../../../features/scope-sharing/api"
import { ScopeShareSettings } from "../../../../../../../features/scope-sharing/scope-share-settings"
import type { ScopeDecisionProjection, ScopeShareProjection, ScopeVersionForSharing } from "../../../../../../../features/scope-sharing/types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export default async function ScopeSharePage({ params }: Readonly<{ params: Promise<{ projectId: string; versionNo: string }> }>) {
  const { projectId, versionNo: versionRaw } = await params
  const versionNo = Number(versionRaw)
  if (!uuidPattern.test(projectId) || !Number.isInteger(versionNo) || versionNo < 1) notFound()
  let access
  try { access = await resolveProjectAccess() } catch (error) { return <Failure error={error} /> }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><AccountBlockedState reason={access.status} /></main>
  let loaded: readonly [ScopeVersionForSharing, readonly ScopeShareProjection[], ScopeDecisionProjection]
  try {
    loaded = await Promise.all([
      fetchScopeVersionForSharing(access.accessToken, access.account.id, projectId, versionNo),
      fetchScopeShares(access.accessToken, access.account.id, projectId, versionNo),
      fetchScopeDecision(access.accessToken, access.account.id, projectId, versionNo)
    ])
  } catch (error) {
    if (error instanceof ProjectApiError && error.status === 404) notFound()
    return <Failure error={error} />
  }
  const [version, shares, decision] = loaded
  return <main id="main-content" className="projects-main" tabIndex={-1}><ScopeShareSettings projectId={projectId} version={version} shares={shares} decision={decision} /></main>
}

function Failure({ error }: Readonly<{ error: unknown }>) { return <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}><ProjectRequestFailure message="تنظیمات اشتراک بارگذاری نشد. دوباره تلاش کنید." {...(error instanceof ProjectApiError ? { requestId: error.requestId } : {})} /></main> }
