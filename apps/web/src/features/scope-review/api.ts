import { getApiBaseUrl } from "../auth/config"
import { publicScopeSectionIds } from "./types"
import type {
  PublicScopeApproval,
  PublicScopeChangeRequest,
  PublicScopeDecisionStatus,
  PublicScopeSection,
  PublicScopeSectionId,
  PublicScopeSectionValue,
  ResolvedPublicScope
} from "./types"

const decisionStatuses = new Set<PublicScopeDecisionStatus>([
  "awaiting_approval",
  "approved",
  "changes_requested",
  "superseded"
])
const sectionIds = new Set<PublicScopeSectionId>(publicScopeSectionIds)
const priorities = new Set(["must", "should", "could"])
const severities = new Set(["critical", "high", "medium", "low"])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function resolvePublicScope(token: string): Promise<ResolvedPublicScope> {
  const payload = await publicRequest("public/scope-shares/resolve", { token })
  return parseResolvedScope(payload)
}

export async function approvePublicScope(input: Readonly<{
  token: string
  guestName: string
  idempotencyKey: string
}>): Promise<PublicScopeApproval> {
  const payload = await publicRequest(
    "public/scope-shares/approve",
    { token: input.token, guest_name: input.guestName, explicit_consent: true },
    input.idempotencyKey
  )
  if (!isObject(payload) || !hasExactKeys(payload, ["data", "meta"]) || !isObject(payload.data)) {
    throw invalidResponse()
  }
  const data = payload.data
  if (
    !hasExactKeys(data, ["approval_id", "scope_version_no", "status", "guest_name", "approved_at"]) ||
    !isUuid(data.approval_id) ||
    !isPositiveInteger(data.scope_version_no) ||
    data.status !== "approved" ||
    typeof data.guest_name !== "string" ||
    !isDateTime(data.approved_at)
  ) throw invalidResponse()
  return {
    approvalId: data.approval_id,
    scopeVersionNo: data.scope_version_no,
    guestName: data.guest_name,
    approvedAt: data.approved_at
  }
}

export async function requestPublicScopeChanges(input: Readonly<{
  token: string
  guestName: string
  comment: string
  idempotencyKey: string
}>): Promise<PublicScopeChangeRequest> {
  const payload = await publicRequest(
    "public/scope-shares/request-changes",
    { token: input.token, guest_name: input.guestName, comment: input.comment },
    input.idempotencyKey
  )
  if (!isObject(payload) || !hasExactKeys(payload, ["data", "meta"]) || !isObject(payload.data)) {
    throw invalidResponse()
  }
  const data = payload.data
  if (
    !hasExactKeys(data, ["change_request_id", "scope_version_no", "status", "guest_name", "requested_at"]) ||
    !isUuid(data.change_request_id) ||
    !isPositiveInteger(data.scope_version_no) ||
    data.status !== "changes_requested" ||
    typeof data.guest_name !== "string" ||
    !isDateTime(data.requested_at)
  ) throw invalidResponse()
  return {
    changeRequestId: data.change_request_id,
    scopeVersionNo: data.scope_version_no,
    guestName: data.guest_name,
    requestedAt: data.requested_at
  }
}

export class PublicScopeResolutionError extends Error {
  constructor(readonly code: string, readonly status: number | null = null) {
    super("Public Scope request failed")
    this.name = "PublicScopeResolutionError"
  }
}

async function publicRequest(
  path: string,
  body: Readonly<Record<string, unknown>>,
  idempotencyKey?: string
): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": crypto.randomUUID(),
        "X-Correlation-ID": crypto.randomUUID(),
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {})
      },
      body: JSON.stringify(body),
      cache: "no-store"
    })
  } catch {
    throw new PublicScopeResolutionError("SCOPE_REVIEW_UNAVAILABLE")
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new PublicScopeResolutionError("INVALID_API_RESPONSE", response.status)
  }
  if (!response.ok) {
    throw new PublicScopeResolutionError(readErrorCode(payload), response.status)
  }
  return payload
}

function parseResolvedScope(value: unknown): ResolvedPublicScope {
  if (
    !isObject(value) ||
    !hasExactKeys(value, ["data", "meta"]) ||
    !isObject(value.data) ||
    !hasExactKeys(value.data, ["version_no", "decision_status", "snapshot_data"]) ||
    !isPositiveInteger(value.data.version_no) ||
    !isDecisionStatus(value.data.decision_status)
  ) throw invalidResponse()
  return {
    versionNo: value.data.version_no,
    decisionStatus: value.data.decision_status,
    snapshotData: parsePublicContent(value.data.snapshot_data)
  }
}

function parsePublicContent(value: unknown): ResolvedPublicScope["snapshotData"] {
  if (
    !isObject(value) ||
    !hasExactKeys(value, ["schema_version", "sections"]) ||
    value.schema_version !== "scope_content_schema_v1" ||
    !Array.isArray(value.sections) ||
    value.sections.length !== publicScopeSectionIds.length
  ) throw invalidResponse()
  const sections = value.sections.map(parsePublicSection)
  if (
    new Set(sections.map((section) => section.section_id)).size !== publicScopeSectionIds.length ||
    publicScopeSectionIds.some((sectionId) => !sections.some((section) => section.section_id === sectionId))
  ) throw invalidResponse()
  return { schema_version: "scope_content_schema_v1", sections }
}

function parsePublicSection(value: unknown): PublicScopeSection {
  if (
    !isObject(value) ||
    !hasExactKeys(value, ["section_id", "value"]) ||
    !isSectionId(value.section_id) ||
    !validPublicSectionValue(value.section_id, value.value)
  ) throw invalidResponse()
  return { section_id: value.section_id, value: value.value }
}

function validPublicSectionValue(sectionId: PublicScopeSectionId, value: unknown): value is PublicScopeSectionValue {
  if (sectionId === "summary" || sectionId === "visual_direction") return typeof value === "string"
  if (["goals", "constraints", "assumptions", "out_of_scope", "acceptance_notes"].includes(sectionId)) {
    return Array.isArray(value) && value.every((item) => typeof item === "string")
  }
  if (!Array.isArray(value)) return false
  if (sectionId === "pages_sections") {
    return value.every((page) => isObject(page) && hasExactKeys(page, ["page_name", "sections"]) && isNonEmptyString(page.page_name) && Array.isArray(page.sections) && page.sections.every((section) => isObject(section) && hasExactKeys(section, ["name"]) && isNonEmptyString(section.name)))
  }
  if (sectionId === "requirements") {
    return value.every((item) => isObject(item) && hasExactKeys(item, ["text", "priority"]) && isNonEmptyString(item.text) && priorities.has(String(item.priority)))
  }
  if (sectionId === "content") {
    return value.every((item) => isObject(item) && hasExactKeys(item, ["description"]) && isNonEmptyString(item.description))
  }
  if (sectionId === "resolved_gaps") {
    return value.every((item) => isObject(item) && hasExactKeys(item, ["text", "resolution_type"]) && isNonEmptyString(item.text) && isNonEmptyString(item.resolution_type))
  }
  return value.every((item) => isObject(item) && hasExactKeys(item, ["text", "severity"]) && isNonEmptyString(item.text) && severities.has(String(item.severity)))
}

function invalidResponse(): PublicScopeResolutionError {
  return new PublicScopeResolutionError("INVALID_API_RESPONSE")
}

function readErrorCode(value: unknown): string {
  return isObject(value) && isObject(value.error) && typeof value.error.code === "string"
    ? value.error.code
    : "SCOPE_REVIEW_REQUEST_FAILED"
}

function isDecisionStatus(value: unknown): value is PublicScopeDecisionStatus {
  return typeof value === "string" && decisionStatuses.has(value as PublicScopeDecisionStatus)
}
function isSectionId(value: unknown): value is PublicScopeSectionId {
  return typeof value === "string" && sectionIds.has(value as PublicScopeSectionId)
}
function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}
function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every((key) => key in value)
}
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isPositiveInteger(value: unknown): value is number { return Number.isInteger(value) && (value as number) > 0 }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isNonEmptyString(value: unknown): value is string { return typeof value === "string" && Boolean(value.trim()) }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
