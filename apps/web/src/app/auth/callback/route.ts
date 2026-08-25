import type { EmailOtpType } from "@supabase/supabase-js"
import { type NextRequest, NextResponse } from "next/server"

import { bootstrapSession } from "../../../features/auth/bootstrap"
import { createAuthTrace, emitAuthEvent } from "../../../features/auth/logging"
import { createClient } from "../../../features/auth/supabase/server"

const allowedOtpTypes = new Set<EmailOtpType>(["email", "signup"])

export async function GET(request: NextRequest): Promise<NextResponse> {
  const trace = createAuthTrace()
  const startedAt = performance.now()
  const code = request.nextUrl.searchParams.get("code")
  const tokenHash = request.nextUrl.searchParams.get("token_hash")
  const rawType = request.nextUrl.searchParams.get("type")
  const redirectTo = request.nextUrl.clone()
  redirectTo.searchParams.delete("code")
  redirectTo.searchParams.delete("token_hash")
  redirectTo.searchParams.delete("type")
  redirectTo.search = ""

  try {
    const supabase = await createClient()
    const result = code
      ? await supabase.auth.exchangeCodeForSession(code)
      : tokenHash && isAllowedOtpType(rawType)
        ? await supabase.auth.verifyOtp({ token_hash: tokenHash, type: rawType })
        : null
    const accessToken = result?.data.session?.access_token
    if (!result || result.error || !accessToken) {
      return callbackFailure(redirectTo, trace, startedAt, "invalid_or_expired")
    }
    await bootstrapSession(accessToken, trace)
  } catch {
    return callbackFailure(redirectTo, trace, startedAt, "bootstrap_unavailable")
  }

  emitAuthEvent("auth.callback_succeeded", trace, {
    durationMs: performance.now() - startedAt
  })
  redirectTo.pathname = "/projects"
  return privateNoStore(NextResponse.redirect(redirectTo, { status: 303 }))
}

function isAllowedOtpType(value: string | null): value is EmailOtpType {
  return value !== null && allowedOtpTypes.has(value as EmailOtpType)
}

function callbackFailure(
  redirectTo: URL,
  trace: ReturnType<typeof createAuthTrace>,
  startedAt: number,
  reasonCode: "invalid_or_expired" | "bootstrap_unavailable"
): NextResponse {
  emitAuthEvent("auth.callback_failed", trace, {
    reasonCode,
    durationMs: performance.now() - startedAt
  })
  redirectTo.pathname = "/auth/callback/error"
  redirectTo.search = ""
  redirectTo.searchParams.set("reason", reasonCode)
  return privateNoStore(NextResponse.redirect(redirectTo, { status: 303 }))
}

function privateNoStore(response: NextResponse): NextResponse {
  response.headers.set("Cache-Control", "private, no-cache, no-store, must-revalidate, max-age=0")
  response.headers.set("Expires", "0")
  response.headers.set("Pragma", "no-cache")
  return response
}
