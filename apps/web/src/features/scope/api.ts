import { randomUUID } from "node:crypto"

import { getApiBaseUrl } from "../auth/config"
import { ProjectApiError } from "../projects/api"
import { scopeSectionIds } from "./types"
import type { ScopeDraft, ScopeSection, ScopeSectionId, ScopeTrace } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const sectionIds = new Set<ScopeSectionId>(scopeSectionIds)

export async function fetchCurrentScopeDraft(
  accessToken: string,
  accountId: string,
  projectId: string
): Promise<ScopeDraft> {
  return requestScope(`projects/${encodeURIComponent(projectId)}/scope/draft`, accessToken, accountId)
}

export async function replaceScopeSection(
  accessToken: string,
  accountId: string,
  projectId: string,
  sectionId: ScopeSectionId,
  value: unknown,
  expectedUpdatedAt: string
): Promise<ScopeDraft> {
  return requestScope(
    `projects/${encodeURIComponent(projectId)}/scope/draft/sections/${sectionId}`,
    accessToken,
    accountId,
    { value, expected_updated_at: expectedUpdatedAt }
  )
}

async function requestScope(
  path: string,
  accessToken: string,
  accountId: string,
  body?: Readonly<{ value: unknown; expected_updated_at: string }>
): Promise<ScopeDraft> {
  const requestId = randomUUID()
  let response: Response
  try {
    response = await fetch(new URL(path, ensureTrailingSlash(getApiBaseUrl())), {
      method: body ? "PATCH" : "GET",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Account-ID": accountId,
        "X-Request-ID": requestId,
        "X-Correlation-ID": randomUUID(),
        ...(body ? { "Content-Type": "application/json" } : {})
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store"
    })
  } catch {
    throw new ProjectApiError({ status: null, code: "SCOPE_API_UNAVAILABLE", requestId })
  }
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new ProjectApiError({ status: response.status, code: "INVALID_API_RESPONSE", requestId })
  }
  if (!response.ok) {
    throw new ProjectApiError({
      status: response.status,
      code: readStringAt(payload, "error", "code") ?? "SCOPE_API_REQUEST_FAILED",
      requestId: readStringAt(payload, "meta", "request_id") ?? requestId
    })
  }
  if (!isObject(payload) || !hasExactKeys(payload, ["data", "meta"]) || !isObject(payload.data) || !isObject(payload.meta) || !hasExactKeys(payload.meta, ["request_id"]) || !isUuid(payload.meta.request_id)) throw invalidResponse()
  return parseDraft(payload.data)
}

function parseDraft(value: Record<string, unknown>): ScopeDraft {
  if (!hasExactKeys(value, ["id", "context_version", "content", "updated_at"]) || !isUuid(value.id) || !Number.isInteger(value.context_version) || (value.context_version as number) < 1 || !isDateTime(value.updated_at) || !isObject(value.content) || !hasExactKeys(value.content, ["schema_version", "sections"]) || value.content.schema_version !== "scope_content_schema_v1" || !Array.isArray(value.content.sections) || value.content.sections.length !== scopeSectionIds.length) throw invalidResponse()
  const sections = value.content.sections.map(parseSection)
  if (new Set(sections.map((section) => section.section_id)).size !== scopeSectionIds.length) throw invalidResponse()
  return {
    id: value.id,
    context_version: value.context_version as number,
    content: { schema_version: "scope_content_schema_v1", sections },
    updated_at: value.updated_at
  }
}

function parseSection(value: unknown): ScopeSection {
  if (!isObject(value) || !hasExactKeys(value, ["section_id", "value", "trace"]) || !isSectionId(value.section_id) || !isObject(value.trace)) throw invalidResponse()
  const trace = parseTrace(value.trace)
  if (!validSectionValue(value.section_id, value.value)) throw invalidResponse()
  return { section_id: value.section_id, value: value.value, trace }
}

function parseTrace(value: Record<string, unknown>): ScopeTrace {
  if (Object.keys(value).length !== 3 || !isOrderedUuidArray(value.context_item_ids) || !isOrderedUuidArray(value.requirement_ids) || !isOrderedUuidArray(value.gap_ids)) throw invalidResponse()
  return {
    context_item_ids: value.context_item_ids,
    requirement_ids: value.requirement_ids,
    gap_ids: value.gap_ids
  }
}

function validSectionValue(sectionId: ScopeSectionId, value: unknown): value is ScopeSection["value"] {
  if (sectionId === "summary" || sectionId === "visual_direction") return typeof value === "string"
  if (["goals", "constraints", "assumptions", "out_of_scope", "acceptance_notes"].includes(sectionId)) return Array.isArray(value) && value.every((item) => typeof item === "string")
  if (!Array.isArray(value)) return false
  if (sectionId === "pages_sections") {
    return uniqueItemIds(value) && value.every((page) =>
      isObject(page) && hasExactKeys(page, ["item_id", "page_name", "sections"]) && isNonEmptyString(page.item_id) && isNonEmptyString(page.page_name) && Array.isArray(page.sections) && uniqueItemIds(page.sections) && page.sections.every((section) => isObject(section) && hasExactKeys(section, ["item_id", "name"]) && isNonEmptyString(section.item_id) && isNonEmptyString(section.name))
    )
  }
  if (sectionId === "requirements") {
    return uniqueItemIds(value) && value.every((item) => isObject(item) && hasExactKeys(item, ["item_id", "text", "priority"]) && isNonEmptyString(item.item_id) && isNonEmptyString(item.text) && ["must", "should", "could"].includes(String(item.priority)))
  }
  if (sectionId === "content") {
    return uniqueItemIds(value) && value.every((item) => isObject(item) && hasExactKeys(item, ["item_id", "description"]) && isNonEmptyString(item.item_id) && isNonEmptyString(item.description))
  }
  if (sectionId === "resolved_gaps") {
    return uniqueItemIds(value) && value.every((item) => isObject(item) && hasExactKeys(item, ["item_id", "text", "resolution_type"]) && isNonEmptyString(item.item_id) && isNonEmptyString(item.text) && isNonEmptyString(item.resolution_type))
  }
  return uniqueItemIds(value) && value.every((item) => isObject(item) && hasExactKeys(item, ["item_id", "text", "severity"]) && isNonEmptyString(item.item_id) && isNonEmptyString(item.text) && ["critical", "high", "medium", "low"].includes(String(item.severity)))
}

function invalidResponse(): ProjectApiError { return new ProjectApiError({ status: null, code: "INVALID_API_RESPONSE", requestId: randomUUID() }) }
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value) }
function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value) }
function isOrderedUuidArray(value: unknown): value is string[] { return Array.isArray(value) && value.every(isUuid) && new Set(value).size === value.length && value.every((item, index) => index === 0 || value[index - 1] <= item) }
function isDateTime(value: unknown): value is string { return typeof value === "string" && !Number.isNaN(Date.parse(value)) }
function isSectionId(value: unknown): value is ScopeSectionId { return typeof value === "string" && sectionIds.has(value as ScopeSectionId) }
function isNonEmptyString(value: unknown): value is string { return typeof value === "string" && Boolean(value.trim()) }
function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean { return Object.keys(value).length === keys.length && keys.every((key) => key in value) }
function uniqueItemIds(value: readonly unknown[]): boolean {
  const ids = value.map((item) => isObject(item) ? item.item_id : null)
  return ids.every(isNonEmptyString) && new Set(ids).size === ids.length
}
function readStringAt(value: unknown, parent: string, child: string): string | null { return isObject(value) && isObject(value[parent]) && typeof value[parent][child] === "string" ? value[parent][child] as string : null }
function ensureTrailingSlash(value: string): string { return value.endsWith("/") ? value : `${value}/` }
