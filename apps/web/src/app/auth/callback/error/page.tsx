import Link from "next/link"

type CallbackErrorPageProps = Readonly<{
  searchParams: Promise<{ reason?: string }>
}>

export default async function CallbackErrorPage({ searchParams }: CallbackErrorPageProps) {
  const { reason } = await searchParams
  const serviceUnavailable = reason !== "invalid_or_expired"
  return (
    <main id="main-content" className="auth-main" tabIndex={-1}>
      <section className="auth-card auth-state" aria-labelledby="callback-error-title">
        <p className="eyebrow">
          {serviceUnavailable ? "فضای کاری آماده نشد" : "تأیید حساب کامل نشد"}
        </p>
        <h1 id="callback-error-title">
          {serviceUnavailable
            ? "ارتباط موقتاً برقرار نیست"
            : "لینک تأیید نامعتبر یا منقضی است"}
        </h1>
        <p role="alert">
          {serviceUnavailable
            ? "حساب تأیید شد، اما آماده‌سازی فضای کاری کامل نشد. دوباره وارد شوید."
            : "برای ادامه دوباره وارد شوید. اگر حساب هنوز تأیید نشده است، ثبت‌نام را تکرار کنید."}
        </p>
        <div className="button-row">
          <Link className="button button--primary" href="/auth/login">
            ورود
          </Link>
          <Link className="button button--secondary" href="/auth/signup">
            {serviceUnavailable ? "بازگشت به ثبت‌نام" : "ثبت‌نام دوباره"}
          </Link>
        </div>
      </section>
    </main>
  )
}
