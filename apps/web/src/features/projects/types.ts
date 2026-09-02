export type AccountRole = "owner" | "admin" | "member"
export type ProjectType = "landing" | "corporate" | "portfolio"
export type ProjectStatus =
  | "draft"
  | "active"
  | "awaiting_approval"
  | "approved"
  | "generating"
  | "delivered"
  | "archived"

export type AccountSelection = Readonly<{
  id: string
  role: AccountRole
}>

export type Project = Readonly<{
  id: string
  account_id: string
  owner_id: string
  title: string
  project_type: ProjectType
  status: ProjectStatus
  current_context_version: number
  created_at: string
  updated_at: string
}>

export type ProjectSummary = Pick<
  Project,
  "id" | "title" | "project_type" | "status" | "updated_at"
>

export type ProjectPage = Readonly<{
  data: readonly Project[]
  meta: Readonly<{
    request_id: string
    next_cursor: string | null
    has_more: boolean
  }>
}>

export type ProjectAccess =
  | Readonly<{ status: "auth_required" }>
  | Readonly<{ status: "none" }>
  | Readonly<{ status: "multiple" }>
  | Readonly<{
      status: "selected"
      accessToken: string
      account: AccountSelection
    }>

export type CreateProjectState = Readonly<{
  status: "idle" | "error"
  message: string
  idempotencyKey: string
  submissionFingerprint: string | null
  fieldErrors: Readonly<{
    title?: string
    projectType?: string
  }>
  requestId?: string
}>

export type LoadMoreProjectsResult =
  | Readonly<{
      status: "success"
      page: Readonly<{
        data: readonly ProjectSummary[]
        meta: ProjectPage["meta"]
      }>
    }>
  | Readonly<{ status: "error"; message: string; requestId?: string }>
