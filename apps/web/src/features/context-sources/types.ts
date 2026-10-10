export type ParserJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled"

export type ContextSourceVersionSummary = Readonly<{
  id: string
  version_no: number
  parse_status: string
  created_at: string
}>

export type ContextSourceJobSummary = Readonly<{
  id: string
  status: ParserJobStatus
  retryable: boolean
  error_code: string | null
  status_url: string
  created_at: string
}>

export type ContextSource = Readonly<{
  id: string
  source_type: "text" | "file" | "message" | "url_reference"
  status: string
  original_name: string | null
  mime_type: string | null
  created_at: string
  updated_at: string
  can_archive: boolean
  latest_version: ContextSourceVersionSummary | null
  latest_job: ContextSourceJobSummary | null
}>

export type ContextSourcePage = Readonly<{
  data: readonly ContextSource[]
  meta: Readonly<{ request_id: string; next_cursor: string | null; has_more: boolean }>
}>

export type ContextSourceActionState = Readonly<{
  status: "idle" | "success" | "error"
  message: string
  requestId?: string
  idempotencyKey?: string
  submissionFingerprint?: string | null
}>

export type ContextSourcePageResult =
  | Readonly<{ status: "success"; page: ContextSourcePage }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>

export type ContextSourceRefreshResult =
  | Readonly<{ status: "success"; sources: readonly ContextSource[] }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>
