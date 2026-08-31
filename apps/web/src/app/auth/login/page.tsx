import { AuthForm } from "../../../features/auth/auth-form"
import { loginAction } from "../../../features/auth/actions"

export default function LoginPage() {
  return (
    <main id="main-content" className="auth-main" tabIndex={-1}>
      <section className="auth-card" aria-labelledby="login-title">
        <p className="eyebrow">ورود به فضای کاری</p>
        <h1 id="login-title">خوش آمدید</h1>
        <p className="auth-intro">برای ادامه، ایمیل و رمز عبور خود را وارد کنید.</p>
        <AuthForm action={loginAction} mode="login" />
      </section>
    </main>
  )
}
