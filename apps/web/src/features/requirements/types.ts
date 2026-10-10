export type RequirementCategory =
  | "functional"
  | "content"
  | "visual"
  | "technical"
  | "constraint"
  | "business"

export type RequirementPriority = "must" | "should" | "could"
export type RequirementStatus = "draft" | "confirmed" | "superseded" | "removed"
export type RequirementCreatorType = "ai" | "user"

export type RequirementSourceReference = Readonly<{
  source_id: string
  source_version_id: string
  start_offset?: number
  end_offset?: number
}>

export type Requirement = Readonly<{
  id: string
  context_version: number
  category: RequirementCategory
  title: string
  description: string
  priority: RequirementPriority
  status: RequirementStatus
  source_refs: readonly RequirementSourceReference[]
  confidence: number | null
  is_unsupported: boolean
  created_by_type: RequirementCreatorType
  acceptance_note: string | null
  created_at: string
  updated_at: string
}>

export type RequirementPage = Readonly<{
  data: readonly Requirement[]
  meta: Readonly<{
    request_id: string
    next_cursor: string | null
    has_more: boolean
  }>
}>

export type RequirementFilters = Readonly<{
  category?: RequirementCategory
  status?: RequirementStatus
}>

export type RequirementMutationState = Readonly<{
  status: "idle" | "success" | "error"
  message: string
  requestId?: string
  completionId?: string
  event?: Readonly<{
    name: "requirement_edited" | "requirement_removed"
    requirementId: string
    eventId: string
  }>
}>

export type CreateRequirementState = RequirementMutationState &
  Readonly<{
    idempotencyKey: string
    submissionFingerprint: string | null
    fieldErrors: Readonly<{
      category?: string
      priority?: string
      title?: string
    }>
  }>

export type LoadRequirementsResult =
  | Readonly<{ status: "success"; page: RequirementPage }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>
