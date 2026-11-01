export type GapType =
  | "missing_information"
  | "ambiguity"
  | "conflict"
  | "decision_required"
  | "unsupported_assumption"
  | "scope_risk"
export type GapSeverity = "critical" | "high" | "medium" | "low"
export type GapStatus = "open" | "resolved" | "dismissed"
export type SuggestedResolutionType =
  | "provide_information"
  | "clarify_ambiguity"
  | "resolve_conflict"
  | "make_decision"
  | "validate_assumption"
  | "mitigate_scope_risk"
export type ClarificationStatus = "open" | "answered" | "ignored"
export type ClarificationCreatorType = "ai" | "user" | "system"
export type ClarificationResolutionType =
  | "provided_information"
  | "internal_decision"
  | "accepted_assumption"
  | "ignored"
export type ClarificationAuthorType = "user" | "client"

export type Gap = Readonly<{
  id: string
  context_version: number
  gap_type: GapType
  severity: GapSeverity
  status: GapStatus
  explanation: string | null
  suggested_resolution_type: SuggestedResolutionType | null
  created_at: string
  updated_at: string
  resolved_at: string | null
}>

export type GapPage = Readonly<{
  data: readonly Gap[]
  meta: Readonly<{ request_id: string; next_cursor: string | null; has_more: boolean }>
}>

export type GapFilters = Readonly<{
  status?: GapStatus
  severity?: GapSeverity
  gap_type?: GapType
}>

export type ClarificationResolution = Readonly<{
  id: string
  resolution_type: ClarificationResolutionType
  answer_text: string | null
  author_type: ClarificationAuthorType
  created_at: string
}>

export type ClarificationHistoryItem = Readonly<{
  id: string
  gap_id: string
  question_text: string
  status: ClarificationStatus
  created_by_type: ClarificationCreatorType
  created_at: string
  updated_at: string
  resolution: ClarificationResolution | null
}>

export type ClarificationHistory = Readonly<{
  data: readonly ClarificationHistoryItem[]
  meta: Readonly<{ request_id: string; next_cursor: null; has_more: false }>
}>

export type GapMutationState = Readonly<{
  status: "idle" | "success" | "error"
  message: string
  requestId?: string
  completionId?: string
}>

export type LoadGapsResult =
  | Readonly<{ status: "success"; page: GapPage }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>

export type LoadClarificationsResult =
  | Readonly<{ status: "success"; history: ClarificationHistory }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>
