export default function ProjectsLoading() {
  return (
    <main id="main-content" className="projects-main" tabIndex={-1}>
      <section className="loading-skeleton" aria-labelledby="projects-loading-title" aria-live="polite">
        <p className="eyebrow">فضای کاری</p>
        <h1 id="projects-loading-title">در حال بارگذاری پروژه‌ها</h1>
        <div className="status-card" aria-hidden="true">
          <p>اطلاعات پروژه‌ها در حال دریافت است.</p>
        </div>
      </section>
    </main>
  )
}
