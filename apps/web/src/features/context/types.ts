export type ContextItemType = "fact" | "assumption" | "decision" | "constraint" | "reference" | "unknown"
export type ContextItemStatus = "proposed" | "confirmed" | "rejected" | "superseded"
export type ContextItemCreatorType = "ai" | "user" | "system"

export type SourceReference = Readonly<{
  source_id: string
  source_version_id: string
  start_offset?: number
  end_offset?: number
}>

export type ContextItem = Readonly<{
  id: string
  context_version: number
  item_type: ContextItemType
  content: string
  source_refs: readonly SourceReference[]
  confidence: number | null
  status: ContextItemStatus
  created_by_type: ContextItemCreatorType
  created_at: string
  updated_at: string
}>

export type ContextItemsPage = Readonly<{
  data: readonly ContextItem[]
  meta: Readonly<{
    request_id: string
    next_cursor: string | null
    has_more: boolean
  }>
}>

export type ContextReviewActionState = Readonly<{
  status: "idle" | "error" | "success"
  message: string
  requestId?: string
}>
