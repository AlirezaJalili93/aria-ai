"use server"

import { randomUUID } from "node:crypto"
import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../projects/api"
import { replaceScopeSection } from "./api"
import { scopeSectionIds } from "./types"
import type { ScopeMutationState, ScopeSectionId } from "./types"

const sectionIds = new Set<ScopeSectionId>(scopeSectionIds)
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function saveScopeSectionAction(
  _previousState: ScopeMutationState,
  formData: FormData
): Promise<ScopeMutationState> {
  const projectId = textValue(formData, "project_id")
  const sectionId = textValue(formData, "section_id")
  const expectedUpdatedAt = textValue(formData, "expected_updated_at")
  const serializedValue = textValue(formData, "value")
  if (!projectId || !uuidPattern.test(projectId) || !sectionId || !sectionIds.has(sectionId as ScopeSectionId) || !expectedUpdatedAt || Number.isNaN(Date.parse(expectedUpdatedAt)) || serializedValue === null) {
    return { status: "error", message: "درخواست ذخیره بخش معتبر نیست." }
  }
  let value: unknown
  try {
    value = JSON.parse(serializedValue)
  } catch {
    return { status: "error", message: "ساختار بخش معتبر نیست." }
  }
  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return actionError(error)
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return { status: "error", message: "فضای کاری قابل استفاده نیست." }
  try {
    const draft = await replaceScopeSection(
      access.accessToken,
      access.account.id,
      projectId,
      sectionId as ScopeSectionId,
      value,
      expectedUpdatedAt
    )
    revalidatePath(`/projects/${projectId}/scope`)
    return {
      status: "success",
      message: "بخش ذخیره شد.",
      updatedAt: draft.updated_at,
      completionId: randomUUID(),
      event: {
        eventId: randomUUID(),
        sectionId: sectionId as ScopeSectionId,
        contextVersion: draft.context_version
      }
    }
  } catch (error) {
    return actionError(error)
  }
}

function actionError(error: unknown): ScopeMutationState {
  const fallback = "ذخیره بخش انجام نشد. تغییرات شما حفظ شده است؛ دوباره تلاش کنید."
  if (!(error instanceof ProjectApiError)) return { status: "error", message: fallback }
  const messages: Readonly<Record<string, string>> = {
    VERSION_CONFLICT: "نسخه پیش‌نویس تغییر کرده است. تغییر محلی شما حفظ شده؛ صفحه را در یک تب تازه بررسی کنید.",
    SCOPE_DRAFT_STALE: "این پیش‌نویس به نسخه قدیمی زمینه تعلق دارد و دیگر قابل ویرایش نیست.",
    RESOURCE_NOT_FOUND: "پیش‌نویس فعلی در دسترس نیست یا مجوز مشاهده آن را ندارید.",
    VALIDATION_FAILED: "ساختار این بخش معتبر نیست. مقادیر را بررسی کنید."
  }
  return {
    status: "error",
    message: messages[error.code] ?? fallback,
    requestId: error.requestId,
    ...(error.code === "VERSION_CONFLICT" ? { reason: "conflict" as const } : {}),
    ...(error.code === "SCOPE_DRAFT_STALE" ? { reason: "stale" as const } : {})
  }
}

function textValue(formData: FormData, key: string): string | null {
  const value = formData.get(key)
  return typeof value === "string" && value ? value : null
}
