import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import type {
  ClarificationAuthorType,
  ClarificationCreatorType,
  ClarificationHistory,
  ClarificationHistoryItem,
  ClarificationResolution,
  ClarificationResolutionType,
  ClarificationStatus,
  Gap,
  GapFilters,
  GapPage,
  GapSeverity,
  GapStatus,
  GapType,
  SuggestedResolutionType
} from "./types"

const gapTypes = new Set<GapType>(["missing_information", "ambiguity", "conflict", "decision_required", "unsupported_assumption", "scope_risk"])
const severities = new Set<GapSeverity>(["critical", "high", "medium", "low"])
const gapStatuses = new Set<GapStatus>(["open", "resolved", "dismissed"])
const suggestedTypes = new Set<SuggestedResolutionType>(["provide_information", "clarify_ambiguity", "resolve_conflict", "make_decision", "validate_assumption", "mitigate_scope_risk"])
const clarificationStatuses = new Set<ClarificationStatus>(["open", "answered", "ignored"])
const creatorTypes = new Set<ClarificationCreatorType>(["ai", "user", "system"])
const resolutionTypes = new Set<ClarificationResolutionType>(["provided_information", "internal_decision", "accepted_assumption", "ignored"])
const authorTypes = new Set<ClarificationAuthorType>(["user", "client"])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function fetchGaps(accessToken: string, accountId: string, projectId: string, options: GapFilters & Readonly<{ cursor?: string }> = {}): Promise<GapPage> {
  const search = new URLSearchParams({ limit: "20" })
  if (options.status) search.set("status", options.status)
  if (options.severity) search.set("severity", options.severity)
  if (options.gap_type) search.set("gap_type", options.gap_type)
  if (options.cursor) search.set("cursor", options.cursor)
  return parseGapPage(await request(`projects/${encodeURIComponent(projectId)}/gaps?${search}`, accessToken, accountId))
}

export async function fetchClarifications(accessToken: string, accountId: string, projectId: string, gapId: string): Promise<ClarificationHistory> {
  return parseHistory(await request(`projects/${encodeURIComponent(projectId)}/gaps/${encodeURIComponent(gapId)}/clarifications`, accessToken, accountId))
}

export async function editClarification(accessToken: string, accountId: string, projectId: string, gapId: string, clarificationId: string, body: Readonly<{ question_text: string; expected_updated_at: string }>): Promise<void> {
  parseClarificationEnvelope(await request(`projects/${encodeURIComponent(projectId)}/gaps/${encodeURIComponent(gapId)}/clarifications/${encodeURIComponent(clarificationId)}`, accessToken, accountId, { method: "PATCH", body }))
}

export async function resolveClarification(accessToken: string, accountId: string, projectId: string, gapId: string, clarificationId: string, input: Readonly<{ resolution_type: ClarificationResolutionType; answer_text?: string; author_type: ClarificationAuthorType; idempotencyKey: string }>): Promise<void> {
  parseResolutionEnvelope(await request(`projects/${encodeURIComponent(projectId)}/gaps/${encodeURIComponent(gapId)}/clarifications/${encodeURIComponent(clarificationId)}/resolutions`, accessToken, accountId, {
    method: "POST",
    idempotencyKey: input.idempotencyKey,
    body: { resolution_type: input.resolution_type, author_type: input.author_type, ...(input.answer_text === undefined ? {} : { answer_text: input.answer_text }) }
  }))
}

export async function dismissGap(accessToken: string, accountId: string, projectId: string, gapId: string, idempotencyKey: string): Promise<void> {
  await request(`projects/${encodeURIComponent(projectId)}/gaps/${encodeURIComponent(gapId)}/dismiss`, accessToken, accountId, { method: "POST", idempotencyKey })
}

async function request(path: string, accessToken: string, accountId: string, options: Readonly<{ method?: "GET" | "POST" | "PATCH"; idempotencyKey?: string; body?: Readonly<Record<string, string>> }> = {}): Promise<unknown> {
  const requestId = randomUUID()
  const headers: Record<string, string> = { Authorization: `Bearer ${accessToken}`, "X-Account-ID": accountId, "X-Request-ID": requestId, "X-Correlation-ID": randomUUID() }
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey
  if (options.body) headers["Content-Type"] = "application/json"
  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), { method: options.method ?? "GET", headers, body: options.body ? JSON.stringify(options.body) : undefined, cache: "no-store" })
  } catch {
    throw new ProjectApiError({ status: null, code: "GAP_API_UNAVAILABLE", requestId })
  }
  if (response.status === 204) return null
  let payload: unknown
  try { payload = await response.json() } catch { throw new ProjectApiError({ status: response.status, code: "INVALID_API_RESPONSE", requestId }) }
  if (response.ok) return payload
  const responseRequestId = readStringAt(payload, "meta", "request_id")
  throw new ProjectApiError({ status: response.status, code: readStringAt(payload, "error", "code") ?? "GAP_API_REQUEST_FAILED", requestId: responseRequestId && isUuid(responseRequestId) ? responseRequestId : requestId })
}

function parseGapPage(value: unknown): GapPage {
  if (!isObject(value) || !Array.isArray(value.data) || !isCollectionMeta(value.meta)) throw invalidResponse()
  return { data: value.data.map(parseGap), meta: { request_id: value.meta.request_id, next_cursor: value.meta.next_cursor, has_more: value.meta.has_more } }
}
function parseGap(value: unknown): Gap {
  if (!isObject(value) || !isUuid(value.id) || !Number.isInteger(value.context_version) || (value.context_version as number) < 1 || !isGapType(value.gap_type) || !isSeverity(value.severity) || !isGapStatus(value.status) || (value.explanation !== null && typeof value.explanation !== "string") || (value.suggested_resolution_type !== null && !isSuggestedType(value.suggested_resolution_type)) || !isDateTime(value.created_at) || !isDateTime(value.updated_at) || (value.resolved_at !== null && !isDateTime(value.resolved_at))) throw invalidResponse()
  return value as Gap
}
function parseHistory(value: unknown): ClarificationHistory {
  if (!isObject(value) || !Array.isArray(value.data) || !isCollectionMeta(value.meta) || value.meta.next_cursor !== null || value.meta.has_more) throw invalidResponse()
  return { data: value.data.map(parseHistoryItem), meta: { request_id: value.meta.request_id, next_cursor: null, has_more: false } }
}
function parseHistoryItem(value: unknown): ClarificationHistoryItem {
  if (!isObject(value) || !isUuid(value.id) || !isUuid(value.gap_id) || typeof value.question_text !== "string" || !isClarificationStatus(value.status) || !isCreatorType(value.created_by_type) || !isDateTime(value.created_at) || !isDateTime(value.updated_at) || (value.resolution !== null && !isObject(value.resolution))) throw invalidResponse()
  return { id: value.id, gap_id: value.gap_id, question_text: value.question_text, status: value.status, created_by_type: value.created_by_type, created_at: value.created_at, updated_at: value.updated_at, resolution: value.resolution === null ? null : parseResolution(value.resolution) }
}
function parseClarificationEnvelope(value: unknown): void {
  if (!isObject(value) || !isObject(value.data) || !isObject(value.meta) || !isUuid(value.meta.request_id)) throw invalidResponse()
  parseHistoryItem({ ...value.data, resolution: null })
}
function parseResolutionEnvelope(value: unknown): void {
  if (!isObject(value) || !isObject(value.data) || !isObject(value.meta) || !isUuid(value.meta.request_id) || !isUuid(value.data.clarification_id)) throw invalidResponse()
  parseResolution(value.data)
}
function parseResolution(value: Record<string, unknown>): ClarificationResolution {
  if (!isUuid(value.id) || !isResolutionType(value.resolution_type) || (value.answer_text !== null && typeof value.answer_text !== "string") || !isAuthorType(value.author_type) || !isDateTime(value.created_at)) throw invalidResponse()
  return value as ClarificationResolution
}
function invalidResponse(): ProjectApiError { return new ProjectApiError({ status: null, code: "INVALID_API_RESPONSE", requestId: randomUUID() }) }
function isCollectionMeta(value: unknown): value is { request_id: string; next_cursor: string | null; has_more: boolean } { return isObject(value) && isUuid(value.request_id) && (value.next_cursor === null || typeof value.next_cursor === "string") && typeof value.has_more === "boolean" }
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isGapType(value: unknown): value is GapType { return typeof value === "string" && gapTypes.has(value as GapType) }
function isSeverity(value: unknown): value is GapSeverity { return typeof value === "string" && severities.has(value as GapSeverity) }
function isGapStatus(value: unknown): value is GapStatus { return typeof value === "string" && gapStatuses.has(value as GapStatus) }
function isSuggestedType(value: unknown): value is SuggestedResolutionType { return typeof value === "string" && suggestedTypes.has(value as SuggestedResolutionType) }
function isClarificationStatus(value: unknown): value is ClarificationStatus { return typeof value === "string" && clarificationStatuses.has(value as ClarificationStatus) }
function isCreatorType(value: unknown): value is ClarificationCreatorType { return typeof value === "string" && creatorTypes.has(value as ClarificationCreatorType) }
function isResolutionType(value: unknown): value is ClarificationResolutionType { return typeof value === "string" && resolutionTypes.has(value as ClarificationResolutionType) }
function isAuthorType(value: unknown): value is ClarificationAuthorType { return typeof value === "string" && authorTypes.has(value as ClarificationAuthorType) }
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
