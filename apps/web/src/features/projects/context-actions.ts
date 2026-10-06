"use server"

import { createContextSource, resolveProjectAccess } from "./api"
import type { ContextSourceItem } from "./types"

export async function saveBriefAction(
  projectId: string,
  rawText: string
): Promise<{ success: boolean; message?: string; source?: ContextSourceItem }> {
  if (!rawText.trim()) return { success: false, message: "متن بریف نمی‌تواند خالی باشد." }
  let access
  try {
    access = await resolveProjectAccess()
  } catch {
    return { success: false, message: "احراز هویت یا دسترسی به پروژه ناموفق بود." }
  }
  if (access.status !== "selected") {
    return { success: false, message: "فضای کاری معتبر یافت نشد." }
  }
  try {
    const source = await createContextSource(access.accessToken, access.account.id, projectId, {
      rawText: rawText.trim(),
      originalName: "بریف ورودی کاربر"
    })
    return { success: true, source }
  } catch {
    return { success: false, message: "ذخیره بریف در سرور با خطا مواجه شد." }
  }
}
