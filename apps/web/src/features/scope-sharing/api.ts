import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import type { ScopeDecisionProjection, ScopeShareProjection, ScopeVersionForSharing, ScopeVersionStatus } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const versionStatuses = new Set<ScopeVersionStatus>(["awaiting_approval", "approved", "changes_requested", "superseded"])

export async function fetchScopeVersionForSharing(accessToken: string, accountId: string, projectId: string, versionNo: number): Promise<ScopeVersionForSharing> {
  const payload = await authenticatedRequest(`projects/${encodeURIComponent(projectId)}/scope/versions/${versionNo}`, accessToken, accountId)
  if (!isEnvelope(payload) || !hasExactKeys(payload.data, ["version_no", "context_version", "status", "snapshot_hash", "schema_version", "created_at", "snapshot_data"]) || !isPositiveInteger(payload.data.version_no) || !isVersionStatus(payload.data.status) || !isDateTime(payload.data.created_at)) throw invalidResponse()
  return { versionNo: payload.data.version_no, status: payload.data.status, createdAt: payload.data.created_at }
}

export async function fetchScopeShares(accessToken: string, accountId: string, projectId: string, versionNo: number): Promise<readonly ScopeShareProjection[]> {
  const payload = await authenticatedRequest(`projects/${encodeURIComponent(projectId)}/scope/versions/${versionNo}/shares`, accessToken, accountId)
  if (!isEnvelope(payload) || !Array.isArray(payload.data)) throw invalidResponse()
  return payload.data.map((row) => {
    if (!isObject(row) || !hasExactKeys(row, ["id", "scope_version_no", "status", "expires_at", "created_at", "can_revoke"]) || !isUuid(row.id) || !isPositiveInteger(row.scope_version_no) || !["active", "expired", "revoked"].includes(String(row.status)) || !isDateTime(row.expires_at) || !isDateTime(row.created_at) || typeof row.can_revoke !== "boolean") throw invalidResponse()
    return { id: row.id, scopeVersionNo: row.scope_version_no, status: row.status as ScopeShareProjection["status"], expiresAt: row.expires_at, createdAt: row.created_at, canRevoke: row.can_revoke }
  })
}

export async function fetchScopeDecision(accessToken: string, accountId: string, projectId: string, versionNo: number): Promise<ScopeDecisionProjection> {
  const payload = await authenticatedRequest(`projects/${encodeURIComponent(projectId)}/scope/versions/${versionNo}/decision`, accessToken, accountId)
  if (!isEnvelope(payload)) throw invalidResponse()
  const row = payload.data
  if (!isPositiveInteger(row.scope_version_no)) throw invalidResponse()
  const scopeVersionNo = row.scope_version_no
  if (row.decision_type === "none" && hasExactKeys(row, ["decision_type", "scope_version_no"])) return { decisionType: "none", scopeVersionNo }
  if (row.decision_type === "approval" && hasExactKeys(row, ["decision_type", "scope_version_no", "approval_id", "guest_name", "approved_at"]) && isUuid(row.approval_id) && typeof row.guest_name === "string" && isDateTime(row.approved_at)) return { decisionType: "approval", scopeVersionNo, decisionId: row.approval_id, guestName: row.guest_name, decidedAt: row.approved_at }
  if (row.decision_type === "change_request" && hasExactKeys(row, ["decision_type", "scope_version_no", "change_request_id", "guest_name", "comment", "requested_at"]) && isUuid(row.change_request_id) && typeof row.guest_name === "string" && typeof row.comment === "string" && isDateTime(row.requested_at)) return { decisionType: "change_request", scopeVersionNo, decisionId: row.change_request_id, guestName: row.guest_name, comment: row.comment, decidedAt: row.requested_at }
  throw invalidResponse()
}

export async function createScopeShare(accessToken: string, accountId: string, projectId: string, versionNo: number, expiresAt: string, idempotencyKey: string): Promise<Readonly<{ id: string; rawToken: string | null; tokenAvailable: boolean }>> {
  const payload = await authenticatedRequest(`projects/${encodeURIComponent(projectId)}/scope/versions/${versionNo}/share`, accessToken, accountId, { method: "POST", idempotencyKey, body: { expires_at: expiresAt } })
  if (!isEnvelope(payload) || !hasExactKeys(payload.data, ["id", "scope_version_no", "expires_at", "token", "token_available"]) || !isUuid(payload.data.id) || (payload.data.token !== null && typeof payload.data.token !== "string") || typeof payload.data.token_available !== "boolean") throw invalidResponse()
  return { id: payload.data.id, rawToken: payload.data.token, tokenAvailable: payload.data.token_available }
}

export async function revokeScopeShare(accessToken: string, accountId: string, projectId: string, shareLinkId: string, idempotencyKey: string): Promise<void> {
  await authenticatedRequest(`projects/${encodeURIComponent(projectId)}/scope-shares/${encodeURIComponent(shareLinkId)}/revoke`, accessToken, accountId, { method: "POST", idempotencyKey, emptyResponse: true })
}

async function authenticatedRequest(path: string, accessToken: string, accountId: string, options: Readonly<{ method?: "POST"; idempotencyKey?: string; body?: Record<string, unknown>; emptyResponse?: boolean }> = {}): Promise<unknown> {
  const requestId = randomUUID()
  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), {
      method: options.method ?? "GET",
      headers: { Authorization: `Bearer ${accessToken}`, "X-Account-ID": accountId, "X-Request-ID": requestId, "X-Correlation-ID": randomUUID(), ...(options.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}), ...(options.body ? { "Content-Type": "application/json" } : {}) },
      body: options.body ? JSON.stringify(options.body) : undefined,
      cache: "no-store"
    })
  } catch { throw new ProjectApiError({ status: null, code: "SCOPE_SHARE_API_UNAVAILABLE", requestId }) }
  if (options.emptyResponse && response.ok) return null
  let payload: unknown
  try { payload = await response.json() } catch { throw new ProjectApiError({ status: response.status, code: "INVALID_API_RESPONSE", requestId }) }
  if (!response.ok) throw new ProjectApiError({ status: response.status, code: readStringAt(payload, "error", "code") ?? "SCOPE_SHARE_API_REQUEST_FAILED", requestId: readStringAt(payload, "meta", "request_id") ?? requestId })
  return payload
}

function isEnvelope(value: unknown): value is { data: Record<string, unknown>; meta: Record<string, unknown> } { return isObject(value) && hasExactKeys(value, ["data", "meta"]) && isObject(value.data) && isObject(value.meta) }
function invalidResponse(): ProjectApiError { return new ProjectApiError({ status: null, code: "INVALID_API_RESPONSE", requestId: randomUUID() }) }
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value) }
function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean { return Object.keys(value).length === keys.length && keys.every((key) => key in value) }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isPositiveInteger(value: unknown): value is number { return Number.isInteger(value) && (value as number) > 0 }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isVersionStatus(value: unknown): value is ScopeVersionStatus { return typeof value === "string" && versionStatuses.has(value as ScopeVersionStatus) }
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
