import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import type {
  Requirement,
  RequirementCategory,
  RequirementFilters,
  RequirementPage,
  RequirementPriority,
  RequirementSourceReference,
  RequirementStatus
} from "./types"

const categories = new Set<RequirementCategory>([
  "functional",
  "content",
  "visual",
  "technical",
  "constraint",
  "business"
])
const priorities = new Set<RequirementPriority>(["must", "should", "could"])
const statuses = new Set<RequirementStatus>(["draft", "confirmed", "superseded", "removed"])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function fetchRequirements(
  accessToken: string,
  accountId: string,
  projectId: string,
  options: RequirementFilters & Readonly<{ cursor?: string }> = {}
): Promise<RequirementPage> {
  const search = new URLSearchParams({ limit: "20" })
  if (options.category) search.set("category", options.category)
  if (options.status) search.set("status", options.status)
  if (options.cursor) search.set("cursor", options.cursor)
  const payload = await request(
    `projects/${encodeURIComponent(projectId)}/requirements?${search.toString()}`,
    accessToken,
    accountId
  )
  return parseRequirementPage(payload)
}

export async function createManualRequirement(
  accessToken: string,
  accountId: string,
  projectId: string,
  input: Readonly<{
    title: string
    description: string
    category: RequirementCategory
    priority: RequirementPriority
    idempotencyKey: string
  }>
): Promise<Requirement> {
  return parseRequirementEnvelope(
    await request(`projects/${encodeURIComponent(projectId)}/requirements`, accessToken, accountId, {
      method: "POST",
      idempotencyKey: input.idempotencyKey,
      body: {
        title: input.title,
        description: input.description,
        category: input.category,
        priority: input.priority
      }
    })
  )
}

export async function updateRequirement(
  accessToken: string,
  accountId: string,
  projectId: string,
  requirementId: string,
  body: Readonly<Record<string, string | null>>
): Promise<Requirement> {
  return parseRequirementEnvelope(
    await request(
      `projects/${encodeURIComponent(projectId)}/requirements/${encodeURIComponent(requirementId)}`,
      accessToken,
      accountId,
      { method: "PATCH", body }
    )
  )
}

export async function deactivateRequirement(
  accessToken: string,
  accountId: string,
  projectId: string,
  requirementId: string
): Promise<void> {
  await request(
    `projects/${encodeURIComponent(projectId)}/requirements/${encodeURIComponent(requirementId)}`,
    accessToken,
    accountId,
    { method: "DELETE" }
  )
}

async function request(
  path: string,
  accessToken: string,
  accountId: string,
  options: Readonly<{
    method?: "GET" | "POST" | "PATCH" | "DELETE"
    idempotencyKey?: string
    body?: Readonly<Record<string, string | null>>
  }> = {}
): Promise<unknown> {
  const requestId = randomUUID()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "X-Account-ID": accountId,
    "X-Request-ID": requestId,
    "X-Correlation-ID": randomUUID()
  }
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
    throw new ProjectApiError({ status: null, code: "REQUIREMENT_API_UNAVAILABLE", requestId })
  }

  if (response.status === 204) return null
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ProjectApiError({ status: response.status, code: "INVALID_API_RESPONSE", requestId })
  }
  if (response.ok) return payload
  const responseRequestId = readStringAt(payload, "meta", "request_id")
  throw new ProjectApiError({
    status: response.status,
    code: readStringAt(payload, "error", "code") ?? "REQUIREMENT_API_REQUEST_FAILED",
    requestId: responseRequestId && isUuid(responseRequestId) ? responseRequestId : requestId
  })
}

function parseRequirementPage(value: unknown): RequirementPage {
  if (!isObject(value) || !Array.isArray(value.data) || !isObject(value.meta)) throw invalidResponse()
  if (!isUuid(value.meta.request_id) || (value.meta.next_cursor !== null && typeof value.meta.next_cursor !== "string") || typeof value.meta.has_more !== "boolean") throw invalidResponse()
  return {
    data: value.data.map(parseRequirement),
    meta: {
      request_id: value.meta.request_id,
      next_cursor: value.meta.next_cursor,
      has_more: value.meta.has_more
    }
  }
}

function parseRequirementEnvelope(value: unknown): Requirement {
  if (!isObject(value) || !isObject(value.data)) throw invalidResponse()
  return parseRequirement(value.data)
}

function parseRequirement(value: unknown): Requirement {
  if (
    !isObject(value) ||
    !isUuid(value.id) ||
    !Number.isInteger(value.context_version) ||
    (value.context_version as number) < 1 ||
    !isCategory(value.category) ||
    typeof value.title !== "string" ||
    typeof value.description !== "string" ||
    !isPriority(value.priority) ||
    !isStatus(value.status) ||
    !Array.isArray(value.source_refs) ||
    (value.confidence !== null &&
      (typeof value.confidence !== "number" ||
        !Number.isFinite(value.confidence) ||
        value.confidence < 0 ||
        value.confidence > 1)) ||
    typeof value.is_unsupported !== "boolean" ||
    (value.created_by_type !== "ai" && value.created_by_type !== "user") ||
    (value.acceptance_note !== null && typeof value.acceptance_note !== "string") ||
    !isDateTime(value.created_at) ||
    !isDateTime(value.updated_at)
  ) throw invalidResponse()
  return {
    id: value.id,
    context_version: value.context_version as number,
    category: value.category,
    title: value.title,
    description: value.description,
    priority: value.priority,
    status: value.status,
    source_refs: value.source_refs.map(parseSourceReference),
    confidence: value.confidence as number | null,
    is_unsupported: value.is_unsupported,
    created_by_type: value.created_by_type,
    acceptance_note: value.acceptance_note,
    created_at: value.created_at,
    updated_at: value.updated_at
  }
}

function parseSourceReference(value: unknown): RequirementSourceReference {
  if (!isObject(value) || !isUuid(value.source_id) || !isUuid(value.source_version_id)) throw invalidResponse()
  const start = value.start_offset
  const end = value.end_offset
  const hasStart = start !== undefined && start !== null
  const hasEnd = end !== undefined && end !== null
  if (
    hasStart !== hasEnd ||
    (hasStart && (!Number.isInteger(start) || (start as number) < 0)) ||
    (hasEnd && (!Number.isInteger(end) || (end as number) <= (start as number)))
  ) throw invalidResponse()
  return {
    source_id: value.source_id,
    source_version_id: value.source_version_id,
    ...(typeof start === "number" ? { start_offset: start } : {}),
    ...(typeof end === "number" ? { end_offset: end } : {})
  }
}

function invalidResponse(): ProjectApiError {
  return new ProjectApiError({ status: null, code: "INVALID_API_RESPONSE", requestId: randomUUID() })
}
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isCategory(value: unknown): value is RequirementCategory { return typeof value === "string" && categories.has(value as RequirementCategory) }
function isPriority(value: unknown): value is RequirementPriority { return typeof value === "string" && priorities.has(value as RequirementPriority) }
function isStatus(value: unknown): value is RequirementStatus { return typeof value === "string" && statuses.has(value as RequirementStatus) }
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
