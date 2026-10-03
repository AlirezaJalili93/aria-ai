"use server"

import { createHash, randomUUID } from "node:crypto"
import { revalidatePath } from "next/cache"

import { ProjectApiError, resolveProjectAccess } from "../projects/api"
import { archiveContextSource, createTextSource, fetchContextSource, fetchContextSources, retryParserJob, uploadTxtSource } from "./api"
import type { ContextSourceActionState, ContextSourcePageResult, ContextSourceRefreshResult } from "./types"

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export async function loadMoreSourcesAction(projectId: string, cursor: string): Promise<ContextSourcePageResult> {
  if (!uuidPattern.test(projectId) || !cursor) return failure("درخواست منابع معتبر نیست.")
  const access = await selectedAccess()
  if ("message" in access) return access
  try { return { status: "success", page: await fetchContextSources(access.accessToken, access.account.id, projectId, cursor) } }
  catch (error) { return fromError(error, "بارگذاری منابع انجام نشد.") }
}

export async function refreshSourcesAction(projectId: string, sourceIds: readonly string[]): Promise<ContextSourceRefreshResult> {
  if (!uuidPattern.test(projectId) || sourceIds.some((id) => !uuidPattern.test(id))) return failure("درخواست تازه‌سازی معتبر نیست.")
  const access = await selectedAccess()
  if ("message" in access) return access
  try {
    const sources = await Promise.all(sourceIds.map((id) => fetchContextSource(access.accessToken, access.account.id, projectId, id)))
    return { status: "success", sources }
  } catch (error) { return fromError(error, "تازه‌سازی وضعیت منابع انجام نشد.") }
}

export async function createTextSourceAction(previous: ContextSourceActionState, formData: FormData): Promise<ContextSourceActionState> {
  const projectId = text(formData, "project_id")
  const rawText = formData.get("raw_text")
  if (!projectId || !uuidPattern.test(projectId) || typeof rawText !== "string" || rawText.trim().length === 0 || rawText.length > 50_000) return failure("متن باید بین ۱ تا ۵۰٬۰۰۰ نویسه باشد.")
  const fingerprint = createHash("sha256").update(projectId).update("\0").update(rawText, "utf8").digest("hex")
  const idempotencyKey = previous.submissionFingerprint && previous.submissionFingerprint !== fingerprint ? randomUUID() : previous.idempotencyKey ?? randomUUID()
  const access = await selectedAccess()
  if ("message" in access) return { ...access, idempotencyKey, submissionFingerprint: fingerprint }
  try { await createTextSource(access.accessToken, access.account.id, projectId, rawText, idempotencyKey) }
  catch (error) { return { ...fromError(error, "افزودن متن انجام نشد."), idempotencyKey, submissionFingerprint: fingerprint } }
  revalidatePath(`/projects/${projectId}/context/sources`)
  return { status: "success", message: "متن برای پردازش ثبت شد.", idempotencyKey: randomUUID(), submissionFingerprint: null }
}

export async function uploadTxtSourceAction(_previous: ContextSourceActionState, formData: FormData): Promise<ContextSourceActionState> {
  const projectId = text(formData, "project_id")
  const idempotencyKey = text(formData, "idempotency_key")
  const file = formData.get("file")
  if (!projectId || !uuidPattern.test(projectId) || !idempotencyKey || !uuidPattern.test(idempotencyKey) || !(file instanceof File) || file.size === 0) return failure("یک فایل TXT معتبر انتخاب کنید.")
  const access = await selectedAccess()
  if ("message" in access) return access
  try { await uploadTxtSource(access.accessToken, access.account.id, projectId, file, idempotencyKey) }
  catch (error) { return fromError(error, uploadMessage(error)) }
  revalidatePath(`/projects/${projectId}/context/sources`)
  return { status: "success", message: "فایل برای پردازش ثبت شد." }
}

export async function archiveSourceAction(projectId: string, sourceId: string): Promise<ContextSourceActionState> {
  if (!uuidPattern.test(projectId) || !uuidPattern.test(sourceId)) return failure("درخواست بایگانی معتبر نیست.")
  const access = await selectedAccess()
  if ("message" in access) return access
  try { await archiveContextSource(access.accessToken, access.account.id, projectId, sourceId) }
  catch (error) { return fromError(error, error instanceof ProjectApiError && error.code === "CONTEXT_SOURCE_BUSY" ? "این منبع در حال پردازش است و فعلاً بایگانی نمی‌شود." : "بایگانی منبع انجام نشد.") }
  revalidatePath(`/projects/${projectId}/context/sources`)
  return { status: "success", message: "منبع بایگانی شد." }
}

export async function retrySourceJobAction(projectId: string, jobId: string, idempotencyKey: string): Promise<ContextSourceActionState> {
  if (![projectId, jobId, idempotencyKey].every((value) => uuidPattern.test(value))) return failure("درخواست تلاش دوباره معتبر نیست.")
  const access = await selectedAccess()
  if ("message" in access) return access
  try { await retryParserJob(access.accessToken, access.account.id, jobId, idempotencyKey) }
  catch (error) { return fromError(error, error instanceof ProjectApiError && error.code === "JOB_NOT_RETRYABLE" ? "این پردازش دیگر قابل تلاش دوباره نیست." : "تلاش دوباره ثبت نشد.") }
  revalidatePath(`/projects/${projectId}/context/sources`)
  return { status: "success", message: "تلاش دوباره ثبت شد." }
}

async function selectedAccess() {
  try {
    const access = await resolveProjectAccess()
    return access.status === "selected" ? access : failure("فضای کاری قابل استفاده نیست.")
  } catch (error) { return fromError(error, "اتصال به فضای کاری انجام نشد.") }
}

function uploadMessage(error: unknown): string {
  if (!(error instanceof ProjectApiError)) return "بارگذاری فایل انجام نشد."
  const messages: Record<string, string> = {
    FEATURE_NOT_ENABLED: "بارگذاری TXT در این محیط فعال نیست.", UNSUPPORTED_FILE_TYPE: "فقط فایل TXT معتبر پذیرفته می‌شود.",
    FILE_TOO_LARGE: "حجم یا متن فایل بیشتر از حد مجاز است.", STORAGE_ERROR: "ذخیره‌سازی موقتاً در دسترس نیست. دوباره تلاش کنید."
  }
  return messages[error.code] ?? "بارگذاری فایل انجام نشد."
}

function fromError(error: unknown, message: string) { return error instanceof ProjectApiError ? { status: "error" as const, message, requestId: error.requestId } : failure(message) }
function failure(message: string): { status: "error"; message: string } { return { status: "error", message } }
function text(formData: FormData, key: string): string | null { const value = formData.get(key); return typeof value === "string" && value ? value : null }
