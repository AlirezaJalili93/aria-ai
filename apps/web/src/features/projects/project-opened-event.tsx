"use client"

import { useEffect } from "react"

import { emitProductEvent } from "../analytics/product-events"
import type { AccountRole, ProjectType } from "./types"

export function ProjectOpenedEvent({
  accountId,
  projectId,
  projectType,
  role
}: Readonly<{
  accountId: string
  projectId: string
  projectType: ProjectType
  role: AccountRole
}>) {
  useEffect(() => {
    emitProductEvent({
      eventName: "project_opened",
      accountId,
      projectId,
      projectType,
      role
    })
  }, [accountId, projectId, projectType, role])
  return null
}
