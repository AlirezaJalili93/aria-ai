import { getApiBaseUrl } from "./config"
import type { AuthTrace } from "./logging"

export type BootstrapFailureReason =
  | "auth_required"
  | "auth_provider_unavailable"
  | "bootstrap_unavailable"

export class BootstrapRequestError extends Error {
  readonly reasonCode: BootstrapFailureReason

  constructor(reasonCode: BootstrapFailureReason) {
    super("Account Bootstrap request failed")
    this.name = "BootstrapRequestError"
    this.reasonCode = reasonCode
  }
}

export async function bootstrapSession(accessToken: string, trace: AuthTrace): Promise<void> {
  const endpoint = new URL("auth/bootstrap", ensureTrailingSlash(getApiBaseUrl()))
  let response: Response
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Request-ID": trace.requestId,
        "X-Correlation-ID": trace.correlationId
      },
      cache: "no-store"
    })
  } catch {
    throw new BootstrapRequestError("bootstrap_unavailable")
  }

  if (response.status === 204) return
  if (response.status === 401) throw new BootstrapRequestError("auth_required")
  if (response.status === 503) {
    const errorCode = await readStableErrorCode(response)
    throw new BootstrapRequestError(
      errorCode === "AUTH_PROVIDER_UNAVAILABLE"
        ? "auth_provider_unavailable"
        : "bootstrap_unavailable"
    )
  }
  throw new BootstrapRequestError("bootstrap_unavailable")
}

async function readStableErrorCode(response: Response): Promise<string | null> {
  try {
    const payload: unknown = await response.json()
    if (!isObject(payload) || !isObject(payload.error)) return null
    return typeof payload.error.code === "string" ? payload.error.code : null
  } catch {
    return null
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

function ensureTrailingSlash(value: string): string {
  return value.endsWith("/") ? value : `${value}/`
}
