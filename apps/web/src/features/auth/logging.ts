import { randomUUID } from "node:crypto"

export type AuthEventName =
  | "auth.signup_started"
  | "auth.signup_completed"
  | "auth.signup_failed"
  | "auth.login_succeeded"
  | "auth.login_failed"
  | "auth.callback_succeeded"
  | "auth.callback_failed"
  | "auth.logout_completed"

export type AuthTrace = Readonly<{
  requestId: string
  correlationId: string
}>

const safeName = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/

export function createAuthTrace(): AuthTrace {
  return { requestId: randomUUID(), correlationId: randomUUID() }
}

export function emitAuthEvent(
  eventName: AuthEventName,
  trace: AuthTrace,
  options: Readonly<{ reasonCode?: string; durationMs?: number }> = {}
): void {
  if (!safeName.test(eventName)) throw new Error("Invalid structured event name")
  const reasonCode = options.reasonCode && safeName.test(options.reasonCode)
    ? options.reasonCode
    : undefined
  const durationMs = options.durationMs === undefined
    ? undefined
    : Math.round(Math.max(0, options.durationMs) * 1000) / 1000
  const record = {
    timestamp: new Date().toISOString(),
    level: eventName.endsWith("_failed") ? "WARNING" : "INFO",
    schema_version: "1",
    service: "aria-web",
    environment: process.env.VERCEL_ENV ?? process.env.NODE_ENV ?? "unknown",
    app_version: process.env.npm_package_version ?? "0.1.0",
    release_commit_sha: process.env.VERCEL_GIT_COMMIT_SHA ?? null,
    event_name: eventName,
    request_id: trace.requestId,
    correlation_id: trace.correlationId,
    account_id: null,
    project_id: null,
    job_id: null,
    route: null,
    task_type: null,
    status: null,
    error_code: null,
    provider_request_id: null,
    ...(reasonCode ? { reason_code: reasonCode } : {}),
    ...(durationMs === undefined ? {} : { duration_ms: durationMs })
  }
  console.info(JSON.stringify(record))
}
