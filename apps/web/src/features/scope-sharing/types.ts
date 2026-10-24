export type ScopeVersionStatus = "awaiting_approval" | "approved" | "changes_requested" | "superseded"

export type ScopeVersionForSharing = Readonly<{
  versionNo: number
  status: ScopeVersionStatus
  createdAt: string
}>

export type ScopeShareProjection = Readonly<{
  id: string
  scopeVersionNo: number
  status: "active" | "expired" | "revoked"
  expiresAt: string
  createdAt: string
  canRevoke: boolean
}>

export type ScopeDecisionProjection =
  | Readonly<{ decisionType: "none"; scopeVersionNo: number }>
  | Readonly<{ decisionType: "approval"; scopeVersionNo: number; decisionId: string; guestName: string; decidedAt: string }>
  | Readonly<{ decisionType: "change_request"; scopeVersionNo: number; decisionId: string; guestName: string; comment: string; decidedAt: string }>

export type ShareMutationState = Readonly<{
  status: "idle" | "success" | "error"
  message?: string
  requestId?: string
  shareLinkId?: string
  rawToken?: string | null
  tokenAvailable?: boolean
  completionId?: string
}>
