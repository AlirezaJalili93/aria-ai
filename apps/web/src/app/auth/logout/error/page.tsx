import Link from "next/link"

export default function LogoutErrorPage() {
  return (
    <main id="main-content" className="auth-main" tabIndex={-1}>
      <section className="auth-card auth-state" aria-labelledby="logout-error-title">
        <p className="eyebrow">خروج کامل نشد</p>
        <h1 id="logout-error-title">ارتباط موقتاً برقرار نیست</h1>
        <p role="alert">به فضای کاری بازگردید و دوباره برای خروج تلاش کنید.</p>
        <Link className="button button--primary" href="/projects">
          بازگشت به فضای کاری
        </Link>
      </section>
    </main>
  )
}
