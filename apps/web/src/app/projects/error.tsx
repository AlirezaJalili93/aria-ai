"use client"

export default function ProjectsError({ reset }: Readonly<{ reset: () => void }>) {
  return (
    <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
      <section className="status-card status-card--centered" aria-labelledby="projects-error-title">
        <h1 id="projects-error-title">فضای کاری بارگذاری نشد</h1>
        <p role="alert">یک خطای موقت رخ داد. دوباره تلاش کنید.</p>
        <button className="button button--primary" type="button" onClick={reset}>
          تلاش دوباره
        </button>
      </section>
    </main>
  )
}
