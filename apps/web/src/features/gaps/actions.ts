"use server"

import { randomUUID } from "node:crypto"
import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import { ProjectApiError, resolveProjectAccess } from "../projects/api"
import { dismissGap, editClarification, fetchClarifications, fetchGaps, resolveClarification } from "./api"
import type { ClarificationAuthorType, ClarificationResolutionType, GapFilters, GapMutationState, LoadClarificationsResult, LoadGapsResult } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const resolutionTypes = new Set<ClarificationResolutionType>(["provided_information", "internal_decision", "accepted_assumption", "ignored"])
const authorTypes = new Set<ClarificationAuthorType>(["user", "client"])

export async function loadGapsAction(projectId: string, filters: GapFilters, cursor?: string): Promise<LoadGapsResult> {
  if (!uuidPattern.test(projectId)) return { status: "error", message: "شناسه پروژه معتبر نیست." }
  const access = await resolveAccess("بارگذاری ابهام‌ها انجام نشد.")
  if ("message" in access) return access
  try { return { status: "success", page: await fetchGaps(access.accessToken, access.account.id, projectId, { ...filters, ...(cursor ? { cursor } : {}) }) } }
  catch (error) { return requestError(error, "بارگذاری ابهام‌ها انجام نشد.") }
}

export async function loadClarificationsAction(projectId: string, gapId: string): Promise<LoadClarificationsResult> {
  if (!uuidPattern.test(projectId) || !uuidPattern.test(gapId)) return { status: "error", message: "شناسه Gap معتبر نیست." }
  const access = await resolveAccess("تاریخچه پرسش‌ها بارگذاری نشد.")
  if ("message" in access) return access
  try { return { status: "success", history: await fetchClarifications(access.accessToken, access.account.id, projectId, gapId) } }
  catch (error) { return requestError(error, "تاریخچه پرسش‌ها بارگذاری نشد.") }
}

export async function editClarificationAction(_state: GapMutationState, formData: FormData): Promise<GapMutationState> {
  const fields = identifiers(formData, true)
  const questionText = formData.get("question_text")
  const expectedUpdatedAt = formData.get("expected_updated_at")
  if (!fields || typeof questionText !== "string" || !questionText.trim() || typeof expectedUpdatedAt !== "string" || Number.isNaN(Date.parse(expectedUpdatedAt))) return { status: "error", message: "درخواست ویرایش کامل یا معتبر نیست." }
  return execute(fields.projectId, async (token, accountId) => editClarification(token, accountId, fields.projectId, fields.gapId, fields.clarificationId, { question_text: questionText, expected_updated_at: expectedUpdatedAt }), "پرسش ویرایش شد.")
}

export async function resolveClarificationAction(_state: GapMutationState, formData: FormData): Promise<GapMutationState> {
  const fields = identifiers(formData, true)
  const resolutionType = formData.get("resolution_type")
  const authorType = formData.get("author_type")
  const answerText = formData.get("answer_text")
  const idempotencyKey = formData.get("idempotency_key")
  if (!fields || typeof resolutionType !== "string" || !resolutionTypes.has(resolutionType as ClarificationResolutionType) || typeof authorType !== "string" || !authorTypes.has(authorType as ClarificationAuthorType) || typeof idempotencyKey !== "string" || !idempotencyKey) return { status: "error", message: "درخواست ثبت نتیجه معتبر نیست." }
  const requiresText = resolutionType === "provided_information" || resolutionType === "internal_decision"
  if ((requiresText && (typeof answerText !== "string" || !answerText.trim())) || (!requiresText && typeof answerText === "string" && answerText.length > 0)) return { status: "error", message: requiresText ? "متن پاسخ را وارد کنید." : "این عملیات متن پاسخ نمی‌پذیرد." }
  return execute(fields.projectId, async (token, accountId) => resolveClarification(token, accountId, fields.projectId, fields.gapId, fields.clarificationId, { resolution_type: resolutionType as ClarificationResolutionType, author_type: authorType as ClarificationAuthorType, idempotencyKey, ...(requiresText ? { answer_text: answerText as string } : {}) }), resolutionType === "ignored" ? "پرسش نادیده گرفته شد." : "نتیجه پرسش ثبت شد.")
}

export async function dismissGapAction(_state: GapMutationState, formData: FormData): Promise<GapMutationState> {
  const fields = identifiers(formData, false)
  const idempotencyKey = formData.get("idempotency_key")
  if (!fields || typeof idempotencyKey !== "string" || !idempotencyKey) return { status: "error", message: "درخواست کنارگذاشتن Gap معتبر نیست." }
  return execute(fields.projectId, async (token, accountId) => dismissGap(token, accountId, fields.projectId, fields.gapId, idempotencyKey), "Gap کنار گذاشته شد.")
}

async function execute(projectId: string, operation: (token: string, accountId: string) => Promise<void>, successMessage: string): Promise<GapMutationState> {
  const access = await resolveAccess("عملیات روی Gap انجام نشد.")
  if ("message" in access) return access
  try { await operation(access.accessToken, access.account.id) } catch (error) { return mutationError(error) }
  revalidatePath(`/projects/${projectId}/gaps`)
  return { status: "success", message: successMessage, completionId: randomUUID() }
}

async function resolveAccess(message: string) {
  let access
  try { access = await resolveProjectAccess() } catch (error) { return requestError(error, message) }
  if (access.status === "auth_required") redirect("/auth/login")
  if (access.status !== "selected") return { status: "error" as const, message: "فضای کاری قابل استفاده نیست." }
  return access
}

function identifiers(formData: FormData, clarificationRequired: true): { projectId: string; gapId: string; clarificationId: string } | null
function identifiers(formData: FormData, clarificationRequired: false): { projectId: string; gapId: string } | null
function identifiers(formData: FormData, clarificationRequired: boolean) {
  const projectId = text(formData, "project_id")
  const gapId = text(formData, "gap_id")
  const clarificationId = text(formData, "clarification_id")
  if (!projectId || !gapId || !uuidPattern.test(projectId) || !uuidPattern.test(gapId) || (clarificationRequired && (!clarificationId || !uuidPattern.test(clarificationId)))) return null
  return { projectId, gapId, ...(clarificationId ? { clarificationId } : {}) }
}
function mutationError(error: unknown): GapMutationState {
  const fallback = "عملیات روی Gap انجام نشد. دوباره تلاش کنید."
  if (!(error instanceof ProjectApiError)) return { status: "error", message: fallback }
  const messages: Readonly<Record<string, string>> = { VERSION_CONFLICT: "این پرسش هم‌زمان تغییر کرده است. صفحه را دوباره بارگذاری کنید.", INVALID_CLARIFICATION_STATE: "این مورد دیگر در وضعیت قابل تغییر نیست.", RESOURCE_NOT_FOUND: "این مورد در دسترس نیست یا مجوز مشاهده آن را ندارید.", IDEMPOTENCY_CONFLICT: "این درخواست با داده متفاوت قبلاً استفاده شده است.", DUPLICATE_CLARIFICATION: "پرسش یکسانی برای این Gap باز است.", VALIDATION_FAILED: "مقادیر ارسال‌شده معتبر نیستند." }
  return { status: "error", message: messages[error.code] ?? fallback, requestId: error.requestId }
}
function requestError(error: unknown, message: string): { status: "error"; message: string; requestId?: string } { return error instanceof ProjectApiError ? { status: "error", message, requestId: error.requestId } : { status: "error", message } }
function text(formData: FormData, key: string): string | null { const value = formData.get(key); return typeof value === "string" && value ? value : null }
