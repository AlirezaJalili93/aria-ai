"use server"

import { randomUUID } from "node:crypto"
import { redirect } from "next/navigation"

import {
  createProject,
  fetchProjects,
  ProjectApiError,
  resolveProjectAccess
} from "./api"
import type {
  CreateProjectState,
  LoadMoreProjectsResult,
  ProjectType
} from "./types"

const validProjectTypes = new Set<ProjectType>(["landing", "corporate", "portfolio"])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function loadMoreProjectsAction(cursor: string): Promise<LoadMoreProjectsResult> {
  if (!cursor) return { status: "error", message: "ادامه فهرست در دسترس نیست." }
  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return projectRequestError(error, "بارگذاری ادامه فهرست انجام نشد.")
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") {
    return { status: "error", message: "فضای کاری قابل استفاده نیست." }
  }
  try {
    const page = await fetchProjects(access.accessToken, access.account.id, cursor)
    return {
      status: "success",
      page: {
        data: page.data.map((project) => ({
          id: project.id,
          title: project.title,
          project_type: project.project_type,
          status: project.status,
          updated_at: project.updated_at
        })),
        meta: page.meta
      }
    }
  } catch (error) {
    return projectRequestError(error, "بارگذاری ادامه فهرست انجام نشد.")
  }
}

export async function createProjectAction(
  previousState: CreateProjectState,
  formData: FormData
): Promise<CreateProjectState> {
  const titleValue = formData.get("title")
  const typeValue = formData.get("project_type")
  const title = typeof titleValue === "string" ? titleValue.trim() : ""
  const projectType = typeof typeValue === "string" ? typeValue : ""
  const fieldErrors: { title?: string; projectType?: string } = {}
  if (!title || title.length > 255) {
    fieldErrors.title = title ? "عنوان پروژه نباید بیشتر از ۲۵۵ نویسه باشد." : "عنوان پروژه الزامی است."
  }
  if (!validProjectTypes.has(projectType as ProjectType)) {
    fieldErrors.projectType = "یکی از نوع‌های پروژه را انتخاب کنید."
  }
  if (fieldErrors.title || fieldErrors.projectType) {
    return {
      ...previousState,
      status: "error",
      message: "فیلدهای مشخص‌شده را بررسی کنید.",
      fieldErrors
    }
  }

  const fingerprint = `${title}\u0000${projectType}`
  const previousIdempotencyKey = uuidPattern.test(previousState.idempotencyKey)
    ? previousState.idempotencyKey
    : randomUUID()
  const idempotencyKey =
    previousState.submissionFingerprint && previousState.submissionFingerprint !== fingerprint
      ? randomUUID()
      : previousIdempotencyKey

  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    const failure = projectRequestError(error, "ساخت پروژه انجام نشد. دوباره تلاش کنید.")
    return {
      status: "error",
      message: failure.message,
      idempotencyKey,
      submissionFingerprint: fingerprint,
      fieldErrors: {},
      ...(failure.requestId ? { requestId: failure.requestId } : {})
    }
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") {
    return {
      ...previousState,
      status: "error",
      message: "فضای کاری قابل استفاده نیست.",
      idempotencyKey,
      submissionFingerprint: fingerprint,
      fieldErrors: {}
    }
  }

  let projectId: string
  try {
    const project = await createProject(access.accessToken, access.account.id, {
      title,
      projectType: projectType as ProjectType,
      idempotencyKey
    })
    projectId = project.id
  } catch (error) {
    const failure = projectRequestError(error, "ساخت پروژه انجام نشد. دوباره تلاش کنید.")
    return {
      status: "error",
      message: failure.message,
      idempotencyKey,
      submissionFingerprint: fingerprint,
      fieldErrors: {},
      ...(failure.requestId ? { requestId: failure.requestId } : {})
    }
  }
  redirect(`/projects/${projectId}`)
}

function projectRequestError(
  error: unknown,
  message: string
): Extract<LoadMoreProjectsResult, { status: "error" }> {
  if (error instanceof ProjectApiError) {
    return { status: "error", message, requestId: error.requestId }
  }
  return { status: "error", message }
}
