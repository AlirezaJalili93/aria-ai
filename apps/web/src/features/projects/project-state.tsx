import Link from "next/link"

export function AccountBlockedState({ reason }: Readonly<{ reason: "none" | "multiple" }>) {
  const message =
    reason === "multiple"
      ? "چند فضای کاری فعال برای این حساب وجود دارد و انتخاب فضای کاری هنوز در این نسخه فعال نیست."
      : "فضای کاری فعالی برای این حساب در دسترس نیست."
  return (
    <section className="status-card status-card--centered" aria-labelledby="account-state-title">
      <p className="eyebrow">فضای کاری</p>
      <h1 id="account-state-title">امکان نمایش پروژه‌ها وجود ندارد</h1>
      <p>{message}</p>
    </section>
  )
}

export function ProjectRequestFailure({
  message,
  requestId
}: Readonly<{ message: string; requestId?: string }>) {
  return (
    <section className="status-card status-card--centered" aria-labelledby="project-failure-title">
      <h1 id="project-failure-title">فضای کاری بارگذاری نشد</h1>
      <p role="alert">{message}</p>
      {requestId ? <p className="request-reference">شناسه پیگیری: {requestId}</p> : null}
      <Link className="button button--primary" href="/projects">
        تلاش دوباره
      </Link>
    </section>
  )
}
