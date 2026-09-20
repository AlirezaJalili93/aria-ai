import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import type { ContextSource, ContextSourcePage, ParserJobStatus } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const sourceTypes = new Set(["text", "file", "message", "url_reference"])
const jobStatuses = new Set<ParserJobStatus>(["queued", "running", "succeeded", "failed", "cancelled"])

export async function fetchContextSources(accessToken: string, accountId: string, projectId: string, cursor?: string): Promise<ContextSourcePage> {
  const search = new URLSearchParams({ limit: "20" })
  if (cursor) search.set("cursor", cursor)
  return parsePage(await requestJson(`projects/${encodeURIComponent(projectId)}/context-sources?${search}`, accessToken, { accountId }))
}

export async function fetchContextSource(accessToken: string, accountId: string, projectId: string, sourceId: string): Promise<ContextSource> {
  const payload = await requestJson(`projects/${encodeURIComponent(projectId)}/context-sources/${encodeURIComponent(sourceId)}`, accessToken, { accountId })
  if (!isObject(payload)) throw invalidResponse()
  return parseSource(payload.data)
}

export async function createTextSource(accessToken: string, accountId: string, projectId: string, rawText: string, idempotencyKey: string): Promise<void> {
  await requestJson(`projects/${encodeURIComponent(projectId)}/context-sources`, accessToken, {
    accountId, method: "POST", idempotencyKey, body: JSON.stringify({ source_type: "text", raw_text: rawText }), contentType: "application/json"
  })
}

export async function uploadTxtSource(accessToken: string, accountId: string, projectId: string, file: File, idempotencyKey: string): Promise<void> {
  const body = new FormData()
  body.set("source_type", "file")
  body.set("file", file)
  await requestJson(`projects/${encodeURIComponent(projectId)}/context-sources`, accessToken, { accountId, method: "POST", idempotencyKey, body })
}

export async function archiveContextSource(accessToken: string, accountId: string, projectId: string, sourceId: string): Promise<void> {
  await requestNoContent(`projects/${encodeURIComponent(projectId)}/context-sources/${encodeURIComponent(sourceId)}`, accessToken, { accountId, method: "DELETE" })
}

export async function retryParserJob(accessToken: string, accountId: string, jobId: string, idempotencyKey: string): Promise<void> {
  await requestJson(`jobs/${encodeURIComponent(jobId)}/retry`, accessToken, { accountId, method: "POST", idempotencyKey })
}

type RequestOptions = Readonly<{ accountId: string; method?: "GET" | "POST" | "DELETE"; idempotencyKey?: string; body?: BodyInit; contentType?: string }>

async function requestJson(path: string, accessToken: string, options: RequestOptions): Promise<unknown> {
  const response = await request(path, accessToken, options)
  let payload: unknown
  try { payload = await response.json() } catch { throw apiError(response.status, "INVALID_API_RESPONSE", response.headers.get("X-Request-ID")) }
  if (response.ok) return payload
  throw responseError(response, payload)
}

async function requestNoContent(path: string, accessToken: string, options: RequestOptions): Promise<void> {
  const response = await request(path, accessToken, options)
  if (response.ok) return
  let payload: unknown = null
  try { payload = await response.json() } catch { /* response code remains authoritative */ }
  throw responseError(response, payload)
}

async function request(path: string, accessToken: string, options: RequestOptions): Promise<Response> {
  const requestId = randomUUID()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "X-Account-ID": options.accountId,
    "X-Request-ID": requestId,
    "X-Correlation-ID": randomUUID()
  }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey
  if (options.contentType) headers["Content-Type"] = options.contentType
  try {
    return await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), { method: options.method ?? "GET", headers, body: options.body, cache: "no-store" })
  } catch { throw apiError(null, "CONTEXT_SOURCE_API_UNAVAILABLE", requestId) }
}

function responseError(response: Response, payload: unknown): ProjectApiError {
  const code = readStringAt(payload, "error", "code") ?? "CONTEXT_SOURCE_API_REQUEST_FAILED"
  const requestId = readStringAt(payload, "meta", "request_id") ?? response.headers.get("X-Request-ID") ?? randomUUID()
  return apiError(response.status, code, requestId)
}

function parsePage(value: unknown): ContextSourcePage {
  if (!isObject(value) || !Array.isArray(value.data) || !isObject(value.meta) || !isUuid(value.meta.request_id) || typeof value.meta.has_more !== "boolean" || (value.meta.next_cursor !== null && typeof value.meta.next_cursor !== "string")) throw invalidResponse()
  return { data: value.data.map(parseSource), meta: { request_id: value.meta.request_id, next_cursor: value.meta.next_cursor as string | null, has_more: value.meta.has_more } }
}

function parseSource(value: unknown): ContextSource {
  if (!isObject(value) || !isUuid(value.id) || !sourceTypes.has(String(value.source_type)) || typeof value.status !== "string" || (value.original_name !== null && typeof value.original_name !== "string") || (value.mime_type !== null && typeof value.mime_type !== "string") || !isDateTime(value.created_at) || !isDateTime(value.updated_at) || typeof value.can_archive !== "boolean") throw invalidResponse()
  return {
    id: value.id, source_type: value.source_type as ContextSource["source_type"], status: value.status,
    original_name: value.original_name as string | null, mime_type: value.mime_type as string | null,
    created_at: value.created_at, updated_at: value.updated_at, can_archive: value.can_archive,
    latest_version: parseVersion(value.latest_version), latest_job: parseJob(value.latest_job)
  }
}

function parseVersion(value: unknown): ContextSource["latest_version"] {
  if (value === null) return null
  if (!isObject(value) || !isUuid(value.id) || !Number.isInteger(value.version_no) || (value.version_no as number) < 1 || typeof value.parse_status !== "string" || !isDateTime(value.created_at)) throw invalidResponse()
  return { id: value.id, version_no: value.version_no as number, parse_status: value.parse_status, created_at: value.created_at }
}

function parseJob(value: unknown): ContextSource["latest_job"] {
  if (value === null) return null
  if (!isObject(value) || !isUuid(value.id) || !jobStatuses.has(value.status as ParserJobStatus) || typeof value.retryable !== "boolean" || (value.error_code !== null && typeof value.error_code !== "string") || typeof value.status_url !== "string" || !isDateTime(value.created_at)) throw invalidResponse()
  return { id: value.id, status: value.status as ParserJobStatus, retryable: value.retryable, error_code: value.error_code as string | null, status_url: value.status_url, created_at: value.created_at }
}

function invalidResponse() { return apiError(null, "INVALID_API_RESPONSE", randomUUID()) }
function apiError(status: number | null, code: string, requestId: string | null) { return new ProjectApiError({ status, code, requestId: requestId && isUuid(requestId) ? requestId : randomUUID() }) }
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string) { return value.endsWith("/") ? value : `${value}/` }
