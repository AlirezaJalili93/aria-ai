export const scopeSectionIds = [
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

export type ScopeSectionId = (typeof scopeSectionIds)[number]
export type ScopeTrace = Readonly<{
  context_item_ids: readonly string[]
  requirement_ids: readonly string[]
  gap_ids: readonly string[]
}>
export type ScopeItem = Readonly<Record<string, unknown> & { item_id?: string }>
export type ScopeSectionValue = string | readonly string[] | readonly ScopeItem[]
export type ScopeSection = Readonly<{
  section_id: ScopeSectionId
  value: ScopeSectionValue
  trace: ScopeTrace
}>
export type ScopeContent = Readonly<{
  schema_version: "scope_content_schema_v1"
  sections: readonly ScopeSection[]
}>
export type ScopeDraft = Readonly<{
  id: string
  context_version: number
  content: ScopeContent
  updated_at: string
}>
export type ScopeMutationState = Readonly<{
  status: "idle" | "success" | "error"
  message: string
  updatedAt?: string
  completionId?: string
  requestId?: string
  event?: Readonly<{
    eventId: string
    sectionId: ScopeSectionId
    contextVersion: number
  }>
  reason?: "conflict" | "stale"
}>
