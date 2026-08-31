"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"

import { BootstrapRequestError, bootstrapSession } from "./bootstrap"
import { getPublicAppUrl, isAuthConfigurationError } from "./config"
import { createAuthTrace, emitAuthEvent } from "./logging"
import { createClient } from "./supabase/server"
import type { AuthActionState } from "./types"

export async function loginAction(
  previousState: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  void previousState
  const trace = createAuthTrace()
  const startedAt = performance.now()
  const credentials = readCredentials(formData)
  if (!credentials) {
    emitAuthEvent("auth.login_failed", trace, {
      reasonCode: "invalid_input",
      durationMs: performance.now() - startedAt
    })
    return errorState("ایمیل و رمز عبور را کامل وارد کنید.")
  }

  try {
    const supabase = await createClient()
    const { data, error } = await supabase.auth.signInWithPassword(credentials)
    if (error || !data.session?.access_token) {
      const failureReason = authFailureReason(error?.status)
      emitAuthEvent("auth.login_failed", trace, {
        reasonCode: failureReason,
        durationMs: performance.now() - startedAt
      })
      return errorState(loginFailureMessage(failureReason))
    }
    await bootstrapSession(data.session.access_token, trace)
  } catch (error) {
    emitAuthEvent("auth.login_failed", trace, {
      reasonCode: safeFailureReason(error),
      durationMs: performance.now() - startedAt
    })
    return errorState("ورود کامل نشد. کمی بعد دوباره تلاش کنید.")
  }

  emitAuthEvent("auth.login_succeeded", trace, {
    durationMs: performance.now() - startedAt
  })
  revalidatePath("/", "layout")
  redirect("/projects")
}

export async function signupAction(
  previousState: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  void previousState
  const trace = createAuthTrace()
  const startedAt = performance.now()
  emitAuthEvent("auth.signup_started", trace)
  const credentials = readCredentials(formData)
  if (!credentials) {
    emitAuthEvent("auth.signup_failed", trace, {
      reasonCode: "invalid_input",
      durationMs: performance.now() - startedAt
    })
    return errorState("ایمیل و رمز عبور را کامل وارد کنید.")
  }

  try {
    const supabase = await createClient()
    const callbackUrl = new URL("/auth/callback", getPublicAppUrl()).toString()
    const { data, error } = await supabase.auth.signUp({
      ...credentials,
      options: { emailRedirectTo: callbackUrl }
    })
    if (error) {
      emitAuthEvent("auth.signup_failed", trace, {
        reasonCode: authFailureReason(error.status),
        durationMs: performance.now() - startedAt
      })
      return errorState("ثبت‌نام انجام نشد. اطلاعات را بررسی و دوباره تلاش کنید.")
    }
    if (data.session) {
      const { error: signOutError } = await supabase.auth.signOut()
      if (signOutError) throw signOutError
    }
  } catch (error) {
    emitAuthEvent("auth.signup_failed", trace, {
      reasonCode: safeFailureReason(error),
      durationMs: performance.now() - startedAt
    })
    return errorState("ثبت‌نام موقتاً در دسترس نیست. کمی بعد دوباره تلاش کنید.")
  }

  emitAuthEvent("auth.signup_completed", trace, {
    durationMs: performance.now() - startedAt
  })
  return { status: "confirmation-sent", message: "ایمیل تأیید ارسال شد" }
}

function readCredentials(formData: FormData): { email: string; password: string } | null {
  const email = formData.get("email")
  const password = formData.get("password")
  if (typeof email !== "string" || typeof password !== "string") return null
  const normalizedEmail = email.trim()
  if (!normalizedEmail || !password) return null
  return { email: normalizedEmail, password }
}

function authFailureReason(status: number | undefined): string {
  if (status === 429) return "rate_limited"
  if (status !== undefined && status >= 500) return "provider_unavailable"
  return "provider_rejected"
}

function safeFailureReason(error: unknown): string {
  if (error instanceof BootstrapRequestError) return error.reasonCode
  if (isAuthConfigurationError(error)) return "configuration_unavailable"
  return "unexpected_failure"
}

function loginFailureMessage(reasonCode: string): string {
  if (reasonCode === "rate_limited") {
    return "تعداد تلاش‌ها زیاد است. کمی بعد دوباره امتحان کنید."
  }
  if (reasonCode === "provider_unavailable") {
    return "ورود موقتاً در دسترس نیست. کمی بعد دوباره تلاش کنید."
  }
  return "ایمیل یا رمز عبور صحیح نیست. دوباره تلاش کنید."
}

function errorState(message: string): AuthActionState {
  return { status: "error", message }
}
