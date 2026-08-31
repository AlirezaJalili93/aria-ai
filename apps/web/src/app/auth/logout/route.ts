import { revalidatePath } from "next/cache"
import { type NextRequest, NextResponse } from "next/server"

import { createAuthTrace, emitAuthEvent } from "../../../features/auth/logging"
import { createClient } from "../../../features/auth/supabase/server"

export async function POST(request: NextRequest): Promise<NextResponse> {
  const trace = createAuthTrace()
  const startedAt = performance.now()
  try {
    const supabase = await createClient()
    const { data } = await supabase.auth.getClaims()
    if (data?.claims) {
      const { error } = await supabase.auth.signOut()
      if (error) return logoutFailure(request)
    }
  } catch {
    return logoutFailure(request)
  }

  emitAuthEvent("auth.logout_completed", trace, {
    durationMs: performance.now() - startedAt
  })
  revalidatePath("/", "layout")
  return privateNoStore(
    NextResponse.redirect(new URL("/auth/login", request.url), { status: 303 })
  )
}

function logoutFailure(request: NextRequest): NextResponse {
  return privateNoStore(
    NextResponse.redirect(new URL("/auth/logout/error", request.url), { status: 303 })
  )
}

function privateNoStore(response: NextResponse): NextResponse {
  response.headers.set("Cache-Control", "private, no-cache, no-store, must-revalidate, max-age=0")
  response.headers.set("Expires", "0")
  response.headers.set("Pragma", "no-cache")
  return response
}
