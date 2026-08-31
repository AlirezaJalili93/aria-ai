export type AuthActionState = Readonly<{
  status: "idle" | "error" | "confirmation-sent"
  message: string
}>

export const initialAuthActionState: AuthActionState = { status: "idle", message: "" }
