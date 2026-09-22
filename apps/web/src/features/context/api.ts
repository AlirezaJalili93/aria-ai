import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import type {
  ContextItem,
  ContextItemStatus,
  ContextItemType,
  ContextItemsPage,
  SourceReference
} from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const itemTypes = new Set<ContextItemType>(["fact", "assumption", "decision", "constraint", "reference", "unknown"])
const statuses = new Set<ContextItemStatus>(["proposed", "confirmed", "rejected", "superseded"])

export async function fetchContextItems(
  accessToken: string,
  accountId: string,
  projectId: string,
  options: Readonly<{
    itemType?: ContextItemType
    status?: ContextItemStatus
    sourceId?: string
    cursor?: string
  }> = {}
): Promise<ContextItemsPage> {
  const search = new URLSearchParams({ limit: "20" })
  if (options.itemType) search.set("item_type", options.itemType)
  if (options.status) search.set("status", options.status)
  if (options.sourceId) search.set("source_id", options.sourceId)
  if (options.cursor) search.set("cursor", options.cursor)
  const payload = await requestJson(
    `projects/${encodeURIComponent(projectId)}/context-items?${search.toString()}`,
    accessToken,
    accountId
  )
  return parsePage(payload)
}

export async function reviewContextItem(
  accessToken: string,
  accountId: string,
  projectId: string,
  itemId: string,
  input: Readonly<{ command: "confirm" | "reject" | "edit"; expectedUpdatedAt: string; content?: string }>
): Promise<ContextItem> {
  const payload = await requestJson(
    `projects/${encodeURIComponent(projectId)}/context-items/${encodeURIComponent(itemId)}`,
    accessToken,
    accountId,
    {
      method: "PATCH",
      body: {
        command: input.command,
        expected_updated_at: input.expectedUpdatedAt,
        ...(input.command === "edit" ? { content: input.content ?? "" } : {})
      }
    }
  )
  if (!isObject(payload) || !isObject(payload.data)) throw invalidResponse()
  return parseItem(payload.data)
}

async function requestJson(
  path: string,
  accessToken: string,
  accountId: string,
  options: Readonly<{ method?: "GET" | "PATCH"; body?: Readonly<Record<string, string>> }> = {}
): Promise<unknown> {
  const requestId = randomUUID()
  const correlationId = randomUUID()
  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Account-ID": accountId,
        "X-Request-ID": requestId,
        "X-Correlation-ID": correlationId,
        ...(options.body ? { "Content-Type": "application/json" } : {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store"
    })
  } catch {
    throw new ProjectApiError({ status: null, code: "CONTEXT_API_UNAVAILABLE", requestId })
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ProjectApiError({ status: response.status, code: "INVALID_API_RESPONSE", requestId })
  }
  if (response.ok) return payload
  const error = readStringAt(payload, "error", "code") ?? "CONTEXT_API_REQUEST_FAILED"
  const responseRequestId = readStringAt(payload, "meta", "request_id")
  throw new ProjectApiError({
    status: response.status,
    code: error,
    requestId: responseRequestId && isUuid(responseRequestId) ? responseRequestId : requestId
  })
}

function parsePage(value: unknown): ContextItemsPage {
  if (!isObject(value) || !Array.isArray(value.data) || !isObject(value.meta)) throw invalidResponse()
  const requestId = value.meta.request_id
  const nextCursor = value.meta.next_cursor
  const hasMore = value.meta.has_more
  if (!isUuid(requestId) || (nextCursor !== null && typeof nextCursor !== "string") || typeof hasMore !== "boolean") {
    throw invalidResponse()
  }
  return {
    data: value.data.map(parseItem),
    meta: { request_id: requestId, next_cursor: nextCursor, has_more: hasMore }
  }
}

function parseItem(value: unknown): ContextItem {
  if (!isObject(value) || !isUuid(value.id) || !Number.isInteger(value.context_version) || !isItemType(value.item_type) || typeof value.content !== "string" || !Array.isArray(value.source_refs) || (value.confidence !== null && typeof value.confidence !== "number") || !isStatus(value.status) || !isCreatorType(value.created_by_type) || !isDateTime(value.created_at) || !isDateTime(value.updated_at)) throw invalidResponse()
  return {
    id: value.id,
    context_version: value.context_version as number,
    item_type: value.item_type,
    content: value.content,
    source_refs: value.source_refs.map(parseSourceRef),
    confidence: value.confidence as number | null,
    status: value.status,
    created_by_type: value.created_by_type,
    created_at: value.created_at,
    updated_at: value.updated_at
  }
}

function parseSourceRef(value: unknown): SourceReference {
  if (!isObject(value) || !isUuid(value.source_id) || !isUuid(value.source_version_id) || (value.start_offset !== undefined && value.start_offset !== null && !Number.isInteger(value.start_offset)) || (value.end_offset !== undefined && value.end_offset !== null && !Number.isInteger(value.end_offset))) throw invalidResponse()
  return {
    source_id: value.source_id,
    source_version_id: value.source_version_id,
    ...(typeof value.start_offset === "number" ? { start_offset: value.start_offset } : {}),
    ...(typeof value.end_offset === "number" ? { end_offset: value.end_offset } : {})
  }
}

function invalidResponse(): ProjectApiError {
  return new ProjectApiError({ status: null, code: "INVALID_API_RESPONSE", requestId: randomUUID() })
}
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isItemType(value: unknown): value is ContextItemType { return typeof value === "string" && itemTypes.has(value as ContextItemType) }
function isStatus(value: unknown): value is ContextItemStatus { return typeof value === "string" && statuses.has(value as ContextItemStatus) }
function isCreatorType(value: unknown): value is ContextItem["created_by_type"] { return value === "ai" || value === "user" || value === "system" }
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
