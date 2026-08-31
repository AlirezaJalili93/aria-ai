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

export function createAuthTrace(): AuthTrace {
  return { requestId: randomUUID(), correlationId: randomUUID() }
}

export function emitAuthEvent(
  eventName: AuthEventName,
  trace: AuthTrace,
  options: Readonly<{ reasonCode?: string; durationMs?: number }> = {}
): void {
  const record = {
    timestamp: new Date().toISOString(),
    service: "aria-web",
    event_name: eventName,
    request_id: trace.requestId,
    correlation_id: trace.correlationId,
    ...(options.reasonCode ? { reason_code: options.reasonCode } : {}),
    ...(options.durationMs === undefined ? {} : { duration_ms: options.durationMs })
  }
  console.info(JSON.stringify(record))
}
