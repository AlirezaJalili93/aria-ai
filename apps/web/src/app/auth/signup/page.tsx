import { signupAction } from "../../../features/auth/actions"
import { AuthForm } from "../../../features/auth/auth-form"

export default function SignupPage() {
  return (
    <main id="main-content" className="auth-main" tabIndex={-1}>
      <section className="auth-card" aria-labelledby="signup-title">
        <p className="eyebrow">ساخت حساب</p>
        <h1 id="signup-title">شروع با Aria</h1>
        <p className="auth-intro">حساب خود را با ایمیل و رمز عبور ایجاد کنید.</p>
        <AuthForm
          action={signupAction}
          mode="signup"
          confirmationMessage="ایمیل تأیید ارسال شد"
        />
      </section>
    </main>
  )
}
