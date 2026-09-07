"use server"

import { randomUUID } from "node:crypto"
import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../projects/api"
import {
  createManualRequirement,
  deactivateRequirement,
  fetchRequirements,
  updateRequirement
} from "./api"
import type {
  CreateRequirementState,
  LoadRequirementsResult,
  RequirementCategory,
  RequirementFilters,
  RequirementMutationState,
  RequirementPriority
} from "./types"

const categories = new Set<RequirementCategory>([
  "functional",
  "content",
  "visual",
  "technical",
  "constraint",
  "business"
])
const priorities = new Set<RequirementPriority>(["must", "should", "could"])
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function loadRequirementsAction(
  projectId: string,
  filters: RequirementFilters,
  cursor?: string
): Promise<LoadRequirementsResult> {
  if (!uuidPattern.test(projectId) || (cursor !== undefined && !cursor)) {
    return { status: "error", message: "درخواست فهرست نیازمندی‌ها معتبر نیست." }
  }
  const access = await resolveAccess("بارگذاری نیازمندی‌ها انجام نشد.")
  if ("message" in access) return access
  try {
    return {
      status: "success",
      page: await fetchRequirements(access.accessToken, access.account.id, projectId, {
        ...filters,
        ...(cursor ? { cursor } : {})
      })
    }
  } catch (error) {
    return requestError(error, "بارگذاری نیازمندی‌ها انجام نشد.")
  }
}

export async function createRequirementAction(
  previousState: CreateRequirementState,
  formData: FormData
): Promise<CreateRequirementState> {
  const projectId = textValue(formData, "project_id")
  const title = formData.get("title")
  const description = formData.get("description")
  const category = formData.get("category")
  const priority = formData.get("priority")
  const fieldErrors: { title?: string; category?: string; priority?: string } = {}
  if (typeof title !== "string" || title.length > 255) fieldErrors.title = "عنوان نباید بیشتر از ۲۵۵ نویسه باشد."
  if (typeof category !== "string" || !categories.has(category as RequirementCategory)) fieldErrors.category = "دسته نیازمندی را انتخاب کنید."
  if (typeof priority !== "string" || !priorities.has(priority as RequirementPriority)) fieldErrors.priority = "اولویت نیازمندی را انتخاب کنید."
  if (!projectId || typeof description !== "string" || Object.keys(fieldErrors).length) {
    return { ...previousState, status: "error", message: "فیلدهای مشخص‌شده را بررسی کنید.", fieldErrors }
  }
  const titleValue = title as string
  const categoryValue = category as RequirementCategory
  const priorityValue = priority as RequirementPriority

  const fingerprint = JSON.stringify({ projectId, title: titleValue, description, category: categoryValue, priority: priorityValue })
  const idempotencyKey = previousState.submissionFingerprint && previousState.submissionFingerprint !== fingerprint
    ? randomUUID()
    : previousState.idempotencyKey
  const access = await resolveAccess("افزودن نیازمندی انجام نشد. دوباره تلاش کنید.")
  if ("message" in access) return { ...previousState, ...access, idempotencyKey, submissionFingerprint: fingerprint, fieldErrors: {} }
  try {
    await createManualRequirement(access.accessToken, access.account.id, projectId, {
      title: titleValue,
      description,
      category: categoryValue,
      priority: priorityValue,
      idempotencyKey
    })
  } catch (error) {
    const failure = requestError(error, "افزودن نیازمندی انجام نشد. دوباره تلاش کنید.")
    const message = error instanceof ProjectApiError && error.code === "CONTEXT_VERSION_REQUIRED"
      ? "برای افزودن نیازمندی، ابتدا باید زمینه معتبر پروژه ایجاد شود."
      : failure.message
    return { status: "error", message, idempotencyKey, submissionFingerprint: fingerprint, fieldErrors: {}, ...(failure.requestId ? { requestId: failure.requestId } : {}) }
  }
  revalidatePath(`/projects/${projectId}/requirements`)
  return { status: "success", message: "نیازمندی افزوده شد.", idempotencyKey: randomUUID(), submissionFingerprint: null, fieldErrors: {} }
}

export async function editRequirementAction(
  _previousState: RequirementMutationState,
  formData: FormData
): Promise<RequirementMutationState> {
  const fields = mutationFields(formData)
  if (!fields) return { status: "error", message: "درخواست ویرایش کامل نیست." }
  const title = formData.get("title")
  const description = formData.get("description")
  const priority = formData.get("priority")
  const acceptanceNote = formData.get("acceptance_note")
  if (typeof title !== "string" || title.length > 255 || typeof description !== "string" || typeof acceptanceNote !== "string" || typeof priority !== "string" || !priorities.has(priority as RequirementPriority)) {
    return { status: "error", message: "مقادیر ویرایش معتبر نیستند." }
  }
  return executeMutation(fields.projectId, fields.requirementId, async (accessToken, accountId) => {
    await updateRequirement(accessToken, accountId, fields.projectId, fields.requirementId, {
      expected_updated_at: fields.expectedUpdatedAt,
      title,
      description,
      priority,
      acceptance_note: acceptanceNote
    })
  }, "requirement_edited", "ویرایش نیازمندی ذخیره شد.")
}

export async function confirmRequirementAction(
  _previousState: RequirementMutationState,
  formData: FormData
): Promise<RequirementMutationState> {
  const fields = mutationFields(formData)
  if (!fields) return { status: "error", message: "درخواست تأیید کامل نیست." }
  return executeMutation(fields.projectId, fields.requirementId, async (accessToken, accountId) => {
    await updateRequirement(accessToken, accountId, fields.projectId, fields.requirementId, {
      expected_updated_at: fields.expectedUpdatedAt,
      status: "confirmed"
    })
  }, null, "نیازمندی تأیید شد.")
}

export async function deactivateRequirementAction(
  _previousState: RequirementMutationState,
  formData: FormData
): Promise<RequirementMutationState> {
  const projectId = textValue(formData, "project_id")
  const requirementId = textValue(formData, "requirement_id")
  if (!projectId || !requirementId || !uuidPattern.test(projectId) || !uuidPattern.test(requirementId)) return { status: "error", message: "درخواست غیرفعال‌سازی معتبر نیست." }
  return executeMutation(projectId, requirementId, async (accessToken, accountId) => {
    await deactivateRequirement(accessToken, accountId, projectId, requirementId)
  }, "requirement_removed", "نیازمندی غیرفعال شد.")
}

async function executeMutation(
  projectId: string,
  requirementId: string,
  operation: (accessToken: string, accountId: string) => Promise<void>,
  eventName: "requirement_edited" | "requirement_removed" | null,
  successMessage: string
): Promise<RequirementMutationState> {
  const access = await resolveAccess("عملیات روی نیازمندی انجام نشد. دوباره تلاش کنید.")
  if ("message" in access) return access
  try {
    await operation(access.accessToken, access.account.id)
  } catch (error) {
    return mutationError(error)
  }
  revalidatePath(`/projects/${projectId}/requirements`)
  return {
    status: "success",
    message: successMessage,
    completionId: randomUUID(),
    ...(eventName
      ? { event: { name: eventName, requirementId, eventId: randomUUID() } }
      : {})
  }
}

async function resolveAccess(message: string) {
  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return requestError(error, message)
  }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return { status: "error" as const, message: "فضای کاری قابل استفاده نیست." }
  return access
}

function mutationFields(formData: FormData): Readonly<{ projectId: string; requirementId: string; expectedUpdatedAt: string }> | null {
  const projectId = textValue(formData, "project_id")
  const requirementId = textValue(formData, "requirement_id")
  const expectedUpdatedAt = textValue(formData, "expected_updated_at")
  if (!projectId || !requirementId || !expectedUpdatedAt || !uuidPattern.test(projectId) || !uuidPattern.test(requirementId) || Number.isNaN(Date.parse(expectedUpdatedAt))) return null
  return { projectId, requirementId, expectedUpdatedAt }
}

function mutationError(error: unknown): RequirementMutationState {
  const fallback = "عملیات روی نیازمندی انجام نشد. دوباره تلاش کنید."
  if (!(error instanceof ProjectApiError)) return { status: "error", message: fallback }
  const messages: Readonly<Record<string, string>> = {
    VERSION_CONFLICT: "این نیازمندی هم‌زمان تغییر کرده است. صفحه را دوباره بارگذاری کنید.",
    INVALID_REQUIREMENT_STATE: "این نیازمندی دیگر در وضعیت قابل ویرایش نیست.",
    RESOURCE_NOT_FOUND: "نیازمندی در دسترس نیست یا مجوز مشاهده آن را ندارید.",
    VALIDATION_FAILED: "مقادیر ارسال‌شده معتبر نیستند. فرم را بررسی کنید."
  }
  return { status: "error", message: messages[error.code] ?? fallback, requestId: error.requestId }
}

function requestError(error: unknown, message: string): Extract<LoadRequirementsResult, { status: "error" }> {
  return error instanceof ProjectApiError ? { status: "error", message, requestId: error.requestId } : { status: "error", message }
}

function textValue(formData: FormData, key: string): string | null {
  const value = formData.get(key)
  return typeof value === "string" && value ? value : null
}
