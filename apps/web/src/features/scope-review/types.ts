export type PublicScopeDecisionStatus =
  | "awaiting_approval"
  | "approved"
  | "changes_requested"
  | "superseded"

export const publicScopeSectionIds = [
  "summary",
  "goals",
  "pages_sections",
  "requirements",
  "content",
  "visual_direction",
  "constraints",
  "assumptions",
  "resolved_gaps",
  "remaining_non_blocking_gaps",
  "out_of_scope",
  "acceptance_notes"
] as const

export type PublicScopeSectionId = (typeof publicScopeSectionIds)[number]
export type PublicScopePage = Readonly<{
  page_name: string
  sections: readonly Readonly<{ name: string }>[]
}>
export type PublicScopeRequirement = Readonly<{ text: string; priority: "must" | "should" | "could" }>
export type PublicScopeContentRequirement = Readonly<{ description: string }>
export type PublicScopeResolvedGap = Readonly<{ text: string; resolution_type: string }>
export type PublicScopeRemainingGap = Readonly<{ text: string; severity: "critical" | "high" | "medium" | "low" }>
export type PublicScopeSectionValue =
  | string
  | readonly string[]
  | readonly PublicScopePage[]
  | readonly PublicScopeRequirement[]
  | readonly PublicScopeContentRequirement[]
  | readonly PublicScopeResolvedGap[]
  | readonly PublicScopeRemainingGap[]
export type PublicScopeSection = Readonly<{
  section_id: PublicScopeSectionId
  value: PublicScopeSectionValue
}>
export type PublicScopeContent = Readonly<{
  schema_version: "scope_content_schema_v1"
  sections: readonly PublicScopeSection[]
}>

export type ResolvedPublicScope = Readonly<{
  versionNo: number
  decisionStatus: PublicScopeDecisionStatus
  snapshotData: PublicScopeContent
}>

export type PublicScopeApproval = Readonly<{
  approvalId: string
  scopeVersionNo: number
  guestName: string
  approvedAt: string
}>

export type PublicScopeChangeRequest = Readonly<{
  changeRequestId: string
  scopeVersionNo: number
  guestName: string
  requestedAt: string
}>
