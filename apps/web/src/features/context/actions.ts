"use server"

import { revalidatePath } from "next/cache"

import { resolveProjectAccess } from "../projects/api"
import { ProjectApiError } from "../projects/api"
import { reviewContextItem } from "./api"
import type { ContextReviewActionState } from "./types"

const idleState: ContextReviewActionState = { status: "idle", message: "" }

export async function confirmContextItemAction(formData: FormData): Promise<ContextReviewActionState> {
  return executeReview(formData, "confirm")
}

export async function rejectContextItemAction(formData: FormData): Promise<ContextReviewActionState> {
  return executeReview(formData, "reject")
}

export async function editContextItemAction(formData: FormData): Promise<ContextReviewActionState> {
  return executeReview(formData, "edit")
}

async function executeReview(
  formData: FormData,
  command: "confirm" | "reject" | "edit"
): Promise<ContextReviewActionState> {
  const projectId = textValue(formData, "project_id")
  const itemId = textValue(formData, "item_id")
  const expectedUpdatedAt = textValue(formData, "expected_updated_at")
  const content = formData.get("content")
  if (!projectId || !itemId || !expectedUpdatedAt || (command === "edit" && typeof content !== "string")) {
    return { status: "error", message: "درخواست ویرایش کامل نیست." }
  }

  let access
  try {
    access = await resolveProjectAccess()
  } catch (error) {
    return actionError(error, "عملیات روی آیتم انجام نشد. دوباره تلاش کنید.")
  }
  if (access.status !== "selected") {
    return { status: "error", message: "فضای کاری قابل استفاده نیست." }
  }
  try {
    await reviewContextItem(access.accessToken, access.account.id, projectId, itemId, {
      command,
      expectedUpdatedAt,
      ...(command === "edit" ? { content: content as string } : {})
    })
  } catch (error) {
    return actionError(error, "عملیات روی آیتم انجام نشد. دوباره تلاش کنید.")
  }
  revalidatePath(`/projects/${projectId}/context`)
  return idleState
}

function actionError(error: unknown, message: string): ContextReviewActionState {
  if (error instanceof ProjectApiError) {
    const conflictMessage =
      error.code === "VERSION_CONFLICT"
        ? "این آیتم هم‌زمان تغییر کرده است. صفحه را دوباره بارگذاری کنید."
        : error.code === "INVALID_CONTEXT_ITEM_STATE"
          ? "این آیتم دیگر در وضعیت قابل ویرایش نیست."
          : message
    return {
      status: "error",
      message: conflictMessage,
      requestId: error.requestId
    }
  }
  return { status: "error", message }
}

function textValue(formData: FormData, key: string): string | null {
  const value = formData.get(key)
  return typeof value === "string" && value ? value : null
}
