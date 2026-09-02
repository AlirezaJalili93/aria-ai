"use client"

import type { AccountRole, ProjectType } from "../projects/types"

type ProductEventName = "project_opened" | "project_type_selected"
type ProductEvent = Readonly<{
  eventName: ProductEventName
  accountId: string
  role: AccountRole
  projectId?: string
  projectType?: ProjectType
}>

export function emitProductEvent(event: ProductEvent): void {
  const record = {
    timestamp: new Date().toISOString(),
    event_category: "product_analytics",
    schema_version: "1",
    event_name: event.eventName,
    account_id: event.accountId,
    project_id: event.projectId ?? null,
    project_type: event.projectType ?? null,
    role: event.role
  }
  console.info(JSON.stringify(record))
}
