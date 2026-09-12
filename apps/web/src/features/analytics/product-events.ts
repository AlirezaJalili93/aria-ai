"use client"

import type { AccountRole, ProjectType } from "../projects/types"

type ProductEventName =
  | "project_opened"
  | "project_type_selected"
  | "requirement_edited"
  | "requirement_removed"
type AccountProductEvent = Readonly<{
  eventName: ProductEventName
  accountId: string
  role: AccountRole
  projectId?: string
  projectType?: ProjectType
  requirementId?: string
}>
type ScopeEditedEvent = Readonly<{
  eventName: "scope_edited"
  projectId: string
  sectionId: string
  contextVersion: number
}>
type ProductEvent = AccountProductEvent | ScopeEditedEvent

export function emitProductEvent(event: ProductEvent): void {
  if (event.eventName === "scope_edited") {
    console.info(JSON.stringify({
      timestamp: new Date().toISOString(),
      event_category: "product_analytics",
      schema_version: "1",
      event_name: event.eventName,
      project_id: event.projectId,
      section_id: event.sectionId,
      context_version: event.contextVersion
    }))
    return
  }
  const record = {
    timestamp: new Date().toISOString(),
    event_category: "product_analytics",
    schema_version: "1",
    event_name: event.eventName,
    account_id: event.accountId,
    project_id: event.projectId ?? null,
    project_type: event.projectType ?? null,
    ...(event.requirementId ? { requirement_id: event.requirementId } : {}),
    role: event.role
  }
  console.info(JSON.stringify(record))
}
