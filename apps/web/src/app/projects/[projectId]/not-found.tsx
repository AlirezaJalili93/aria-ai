import Link from "next/link"

export default function ProjectNotFound() {
  return (
    <main id="main-content" className="projects-main projects-main--centered" tabIndex={-1}>
      <section className="status-card status-card--centered" aria-labelledby="project-not-found-title">
        <h1 id="project-not-found-title">پروژه پیدا نشد</h1>
        <p>پروژه در این فضای کاری در دسترس نیست.</p>
        <Link className="button button--primary" href="/projects">
          بازگشت به پروژه‌ها
        </Link>
      </section>
    </main>
  )
}
