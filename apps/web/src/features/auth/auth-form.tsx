"use client"

import Link from "next/link"
import { useActionState } from "react"
import { useFormStatus } from "react-dom"

import { initialAuthActionState, type AuthActionState } from "./types"

type AuthFormProps = Readonly<{
  action: (state: AuthActionState, formData: FormData) => Promise<AuthActionState>
}> &
  (
    | Readonly<{ mode: "login"; confirmationMessage?: never }>
    | Readonly<{ mode: "signup"; confirmationMessage: string }>
  )

export function AuthForm({ action, mode, confirmationMessage }: AuthFormProps) {
  const [state, formAction] = useActionState(action, initialAuthActionState)
  const isLogin = mode === "login"

  if (state.status === "confirmation-sent") {
    return (
      <section className="auth-state" aria-labelledby="confirmation-title" aria-live="polite">
        <h2 id="confirmation-title">{confirmationMessage}</h2>
        <p>برای ادامه، پیام تأیید حساب را در صندوق ورودی خود باز کنید.</p>
        <Link className="button button--secondary" href="/auth/login">
          بازگشت به ورود
        </Link>
      </section>
    )
  }

  return (
    <form className="auth-form" action={formAction} noValidate={false}>
      <div className="field-group">
        <label htmlFor={`${mode}-email`}>ایمیل</label>
        <input
          id={`${mode}-email`}
          className="text-field text-field--ltr"
          name="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          required
        />
      </div>
      <div className="field-group">
        <label htmlFor={`${mode}-password`}>رمز عبور</label>
        <input
          id={`${mode}-password`}
          className="text-field text-field--ltr"
          name="password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          required
        />
      </div>
      {state.status === "error" ? (
        <p className="inline-alert" role="alert">
          {state.message}
        </p>
      ) : (
        <p className="form-status" aria-live="polite" />
      )}
      <SubmitButton label={isLogin ? "ورود" : "ساخت حساب"} />
      <p className="auth-alternative">
        {isLogin ? "حساب ندارید؟" : "قبلاً حساب ساخته‌اید؟"}{" "}
        <Link href={isLogin ? "/auth/signup" : "/auth/login"}>
          {isLogin ? "ثبت‌نام" : "ورود"}
        </Link>
      </p>
    </form>
  )
}

function SubmitButton({ label }: Readonly<{ label: string }>) {
  const { pending } = useFormStatus()
  return (
    <button className="button button--primary" type="submit" disabled={pending}>
      {pending ? "در حال انجام…" : label}
    </button>
  )
}
