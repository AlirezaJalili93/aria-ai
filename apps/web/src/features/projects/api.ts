import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { createClient } from "../auth/supabase/server"
import type {
  AccountRole,
  AccountSelection,
  Project,
  ProjectAccess,
  ProjectPage,
  ProjectStatus,
  ProjectType
} from "./types"

const accountRoles = new Set<AccountRole>(["owner", "admin", "member"])
const projectTypes = new Set<ProjectType>(["landing", "corporate", "portfolio"])
const projectStatuses = new Set<ProjectStatus>([
  "draft",
  "active",
  "awaiting_approval",
  "approved",
  "generating",
  "delivered",
  "archived"
])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export class ProjectApiError extends Error {
  readonly status: number | null
  readonly code: string
  readonly requestId: string

  constructor(options: Readonly<{ status: number | null; code: string; requestId: string }>) {
    super("Project API request failed")
    this.name = "ProjectApiError"
    this.status = options.status
    this.code = options.code
    this.requestId = options.requestId
  }
}

export async function resolveProjectAccess(): Promise<ProjectAccess> {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  if (!claimsData?.claims) return { status: "auth_required" }

  // Claims establish trust here; the API independently verifies this forwarded token again.
  const { data: sessionData } = await supabase.auth.getSession()
  const accessToken = sessionData.session?.access_token
  if (!accessToken) return { status: "auth_required" }

  let accounts: readonly AccountSelection[]
  try {
    accounts = await fetchAccounts(accessToken)
  } catch (error) {
    if (error instanceof ProjectApiError && error.status === 401) return { status: "auth_required" }
    throw error
  }
  if (accounts.length === 0) return { status: "none" }
  if (accounts.length > 1) return { status: "multiple" }
  return { status: "selected", accessToken, account: accounts[0] }
}

export async function fetchProjects(
  accessToken: string,
  accountId: string,
  cursor?: string
): Promise<ProjectPage> {
  const search = new URLSearchParams({ limit: "20" })
  if (cursor) search.set("cursor", cursor)
  const payload = await requestJson(`projects?${search.toString()}`, accessToken, {
    accountId
  })
  return parseProjectPage(payload)
}

export async function fetchProject(
  accessToken: string,
  accountId: string,
  projectId: string
): Promise<Project> {
  const payload = await requestJson(`projects/${encodeURIComponent(projectId)}`, accessToken, {
    accountId
  })
  return parseProject(payload)
}

export async function createProject(
  accessToken: string,
  accountId: string,
  input: Readonly<{ title: string; projectType: ProjectType; idempotencyKey: string }>
): Promise<Project> {
  const payload = await requestJson("projects", accessToken, {
    accountId,
    method: "POST",
    idempotencyKey: input.idempotencyKey,
    body: { title: input.title, project_type: input.projectType }
  })
  return parseProject(payload)
}

async function fetchAccounts(accessToken: string): Promise<readonly AccountSelection[]> {
  const payload = await requestJson("accounts", accessToken)
  if (!isObject(payload) || !Array.isArray(payload.data) || !isCollectionMeta(payload.meta)) {
    throw invalidResponse()
  }
  return payload.data.map((item) => {
    if (!isObject(item) || !isUuid(item.id) || !isAccountRole(item.role)) throw invalidResponse()
    return { id: item.id, role: item.role }
  })
}

async function requestJson(
  path: string,
  accessToken: string,
  options: Readonly<{
    accountId?: string
    method?: "GET" | "POST"
    idempotencyKey?: string
    body?: Readonly<Record<string, string>>
  }> = {}
): Promise<unknown> {
  const requestId = randomUUID()
  const correlationId = randomUUID()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "X-Request-ID": requestId,
    "X-Correlation-ID": correlationId
  }
  if (options.accountId) headers["X-Account-ID"] = options.accountId
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey
  if (options.body) headers["Content-Type"] = "application/json"

  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), {
      method: options.method ?? "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store"
    })
  } catch {
    throw new ProjectApiError({
      status: null,
      code: "PROJECT_API_UNAVAILABLE",
      requestId
    })
  }

  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ProjectApiError({
      status: response.status,
      code: "INVALID_API_RESPONSE",
      requestId
    })
  }
  if (response.ok) return payload

  const errorCode = readStringAt(payload, "error", "code") ?? "PROJECT_API_REQUEST_FAILED"
  const responseRequestId = readStringAt(payload, "meta", "request_id")
  throw new ProjectApiError({
    status: response.status,
    code: errorCode,
    requestId: responseRequestId && isUuid(responseRequestId) ? responseRequestId : requestId
  })
}

function parseProjectPage(value: unknown): ProjectPage {
  if (!isObject(value) || !Array.isArray(value.data) || !isCollectionMeta(value.meta)) {
    throw invalidResponse()
  }
  const nextCursor = value.meta.next_cursor
  if (nextCursor !== null && typeof nextCursor !== "string") throw invalidResponse()
  if (typeof value.meta.has_more !== "boolean") throw invalidResponse()
  return {
    data: value.data.map(parseProject),
    meta: {
      request_id: value.meta.request_id,
      next_cursor: nextCursor,
      has_more: value.meta.has_more
    }
  }
}

function parseProject(value: unknown): Project {
  if (
    !isObject(value) ||
    !isUuid(value.id) ||
    !isUuid(value.account_id) ||
    !isUuid(value.owner_id) ||
    typeof value.title !== "string" ||
    !isProjectType(value.project_type) ||
    !isProjectStatus(value.status) ||
    !Number.isInteger(value.current_context_version) ||
    (value.current_context_version as number) < 0 ||
    !isDateTime(value.created_at) ||
    !isDateTime(value.updated_at)
  ) {
    throw invalidResponse()
  }
  return {
    id: value.id,
    account_id: value.account_id,
    owner_id: value.owner_id,
    title: value.title,
    project_type: value.project_type,
    status: value.status,
    current_context_version: value.current_context_version as number,
    created_at: value.created_at,
    updated_at: value.updated_at
  }
}

function invalidResponse(): ProjectApiError {
  return new ProjectApiError({
    status: null,
    code: "INVALID_API_RESPONSE",
    requestId: randomUUID()
  })
}

function isCollectionMeta(value: unknown): value is Record<string, unknown> & { request_id: string } {
  return isObject(value) && isUuid(value.request_id)
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value)
}

function isDateTime(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(Date.parse(value))
}

function isAccountRole(value: unknown): value is AccountRole {
  return typeof value === "string" && accountRoles.has(value as AccountRole)
}

function isProjectType(value: unknown): value is ProjectType {
  return typeof value === "string" && projectTypes.has(value as ProjectType)
}

function isProjectStatus(value: unknown): value is ProjectStatus {
  return typeof value === "string" && projectStatuses.has(value as ProjectStatus)
}

function readStringAt(value: unknown, parent: string, child: string): string | null {
  if (!isObject(value) || !isObject(value[parent])) return null
  const nested = value[parent][child]
  return typeof nested === "string" ? nested : null
}

function ensureTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`
}
