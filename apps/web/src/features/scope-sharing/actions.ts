"use server"

import { randomUUID } from "node:crypto"
import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../projects/api"
import { createScopeShare, revokeScopeShare } from "./api"
import type { ShareMutationState } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function createScopeShareAction(_previous: ShareMutationState, formData: FormData): Promise<ShareMutationState> {
  const input = parseInput(formData, true)
  if (!input) return { status: "error", message: "درخواست ایجاد لینک معتبر نیست." }
  const access = await safeAccess()
  if (access === null) return { status: "error", message: "فضای کاری قابل استفاده نیست." }
  try {
    const result = await createScopeShare(access.accessToken, access.account.id, input.projectId, input.versionNo, input.expiresAt!, input.idempotencyKey)
    revalidatePath(`/projects/${input.projectId}/scope/versions/${input.versionNo}/share`)
    return { status: "success", message: result.tokenAvailable ? "لینک اشتراک ایجاد شد." : "این درخواست قبلاً ثبت شده و توکن آن قابل بازیابی نیست.", shareLinkId: result.id, rawToken: result.rawToken, tokenAvailable: result.tokenAvailable, completionId: randomUUID() }
  } catch (error) { return actionError(error) }
}

export async function revokeScopeShareAction(_previous: ShareMutationState, formData: FormData): Promise<ShareMutationState> {
  const input = parseInput(formData, false)
  const shareLinkId = textValue(formData, "share_link_id")
  if (!input || !shareLinkId || !uuidPattern.test(shareLinkId)) return { status: "error", message: "درخواست لغو لینک معتبر نیست." }
  const access = await safeAccess()
  if (access === null) return { status: "error", message: "فضای کاری قابل استفاده نیست." }
  try {
    await revokeScopeShare(access.accessToken, access.account.id, input.projectId, shareLinkId, input.idempotencyKey)
    revalidatePath(`/projects/${input.projectId}/scope/versions/${input.versionNo}/share`)
    return { status: "success", message: "دسترسی لینک لغو شد.", completionId: randomUUID() }
  } catch (error) { return actionError(error) }
}

async function safeAccess() {
  let access
  try { access = await resolveProjectAccess() } catch { return null }
  if (access.status === "auth_required") redirect("/auth/login")
  return access.status === "selected" ? access : null
}

function parseInput(formData: FormData, requireExpiry: boolean): { projectId: string; versionNo: number; idempotencyKey: string; expiresAt: string | null } | null {
  const projectId = textValue(formData, "project_id")
  const versionRaw = textValue(formData, "version_no")
  const idempotencyKey = textValue(formData, "idempotency_key")
  const expiresAt = textValue(formData, "expires_at")
  const versionNo = Number(versionRaw)
  if (!projectId || !uuidPattern.test(projectId) || !Number.isInteger(versionNo) || versionNo < 1 || !idempotencyKey || !uuidPattern.test(idempotencyKey) || (requireExpiry && (!expiresAt || Number.isNaN(Date.parse(expiresAt))))) return null
  return { projectId, versionNo, idempotencyKey, expiresAt }
}

function actionError(error: unknown): ShareMutationState {
  if (!(error instanceof ProjectApiError)) return { status: "error", message: "عملیات انجام نشد. دوباره تلاش کنید." }
  const messages: Readonly<Record<string, string>> = { RESOURCE_NOT_FOUND: "نسخه یا لینک در دسترس نیست.", IDEMPOTENCY_CONFLICT: "این کلید برای درخواست دیگری استفاده شده است.", VALIDATION_FAILED: "مقادیر درخواست معتبر نیستند." }
  return { status: "error", message: messages[error.code] ?? "عملیات انجام نشد. دوباره تلاش کنید.", requestId: error.requestId }
}
function textValue(formData: FormData, key: string): string | null { const value = formData.get(key); return typeof value === "string" && value ? value : null }
