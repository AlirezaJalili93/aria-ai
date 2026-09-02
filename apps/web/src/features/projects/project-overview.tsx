import Link from "next/link"

import { projectStatusLabel, projectTypeLabel } from "./presentation"
import { ProjectOpenedEvent } from "./project-opened-event"
import type { AccountSelection, Project } from "./types"

export function ProjectOverview({
  account,
  project,
  emitOpenedEvent = true
}: Readonly<{
  account: AccountSelection
  project: Project
  emitOpenedEvent?: boolean
}>) {
  return (
    <>
      {emitOpenedEvent ? (
        <ProjectOpenedEvent
          accountId={account.id}
          projectId={project.id}
          projectType={project.project_type}
          role={account.role}
        />
      ) : null}
      <article className="project-overview" aria-labelledby="project-title">
        <Link className="back-link" href="/projects">
          بازگشت به پروژه‌ها
        </Link>
        <div className="overview-heading">
          <div>
            <p className="eyebrow">نمای کلی پروژه</p>
            <h1 id="project-title">{project.title}</h1>
          </div>
          <span className="status-badge">{projectStatusLabel(project.status)}</span>
        </div>
        {project.status === "archived" ? (
          <p className="archived-notice" role="status">
            این پروژه بایگانی شده و در حالت فقط‌خواندنی است.
          </p>
        ) : null}
        <dl className="project-metadata">
          <div>
            <dt>نوع پروژه</dt>
            <dd>{projectTypeLabel(project.project_type)}</dd>
          </div>
          <div>
            <dt>وضعیت</dt>
            <dd>{projectStatusLabel(project.status)}</dd>
          </div>
          <div>
            <dt>آخرین تغییر</dt>
            <dd>
              <time dateTime={project.updated_at}>{project.updated_at}</time>
            </dd>
          </div>
        </dl>
        <section className="future-modules" aria-labelledby="project-sections-title">
          <h2 id="project-sections-title">بخش‌های پروژه</h2>
          <div className="module-grid">
            {[
              ["Context", "زمینه پروژه"],
              ["Requirements", "نیازمندی‌ها"],
              ["Gaps", "ابهام‌ها"],
              ["Scope", "محدوده"]
            ].map(([key, label]) => (
              <section className="module-card" key={key}>
                <h3>{label}</h3>
                <p>هنوز شروع نشده</p>
              </section>
            ))}
          </div>
        </section>
      </article>
    </>
  )
}
