"use client"

import type { AccountRole, ProjectType } from "../projects/types"

type ClientProductEventName =
  | "project_opened"
  | "project_type_selected"
  | "requirement_edited"
  | "requirement_removed"
  | "scope_edited"

type ProductEvent = Readonly<{
  eventName: ClientProductEventName
  accountId: string
  projectId?: string
  eventId?: string
  actorId?: string
  projectType?: ProjectType
  role?: AccountRole
  requirementId?: string
  sectionId?: string
  contextVersion?: number
  dedupeKey?: string
}>

const emittedInteractionKeys = new Set<string>()
const PROJECT_TYPES = new Set<ProjectType>(["landing", "corporate", "portfolio"])
const ROLES = new Set<AccountRole>(["owner", "admin", "member"])

export function emitProductEvent(event: ProductEvent): void {
  if (event.projectType && !PROJECT_TYPES.has(event.projectType)) throw new Error("Invalid project type")
  if (event.role && !ROLES.has(event.role)) throw new Error("Invalid account role")
  const dedupeKey = event.dedupeKey ?? `${event.eventName}:${event.projectId ?? "new"}:${event.requirementId ?? ""}:${event.sectionId ?? ""}:${event.contextVersion ?? ""}`
  if (event.eventName === "project_opened" && emittedInteractionKeys.has(dedupeKey)) return
  if (event.eventName === "project_opened") emittedInteractionKeys.add(dedupeKey)

  const properties: Record<string, string | number> = {}
  if (event.projectType) properties.project_type = event.projectType
  if (event.role) properties.role = event.role
  if (event.requirementId) properties.requirement_id = event.requirementId
  if (event.sectionId) properties.section_id = event.sectionId
  if (event.contextVersion !== undefined) properties.context_version = event.contextVersion

  console.info(JSON.stringify({
    event_id: event.eventId ?? crypto.randomUUID(),
    event_name: event.eventName,
    event_category: "product_analytics",
    schema_version: "1",
    occurred_at: new Date().toISOString(),
    account_id: event.accountId,
    project_id: event.projectId ?? null,
    actor_id: event.actorId ?? null,
    properties
  }))
}
