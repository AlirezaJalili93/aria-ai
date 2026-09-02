"use client"

import Link from "next/link"
import { useState, useTransition } from "react"

import { loadMoreProjectsAction } from "./actions"
import { projectStatusLabel, projectTypeLabel } from "./presentation"
import type { ProjectSummary } from "./types"

type ProjectListProps = Readonly<{
  initialProjects: readonly ProjectSummary[]
  initialNextCursor: string | null
  initialHasMore: boolean
}>

export function ProjectList({
  initialProjects,
  initialNextCursor,
  initialHasMore
}: ProjectListProps) {
  const [projects, setProjects] = useState(initialProjects)
  const [nextCursor, setNextCursor] = useState(initialNextCursor)
  const [hasMore, setHasMore] = useState(initialHasMore)
  const [failure, setFailure] = useState<{ message: string; requestId?: string } | null>(null)
  const [isPending, startTransition] = useTransition()

  if (projects.length === 0) {
    return (
      <section className="empty-state" aria-labelledby="projects-title">
        <p className="eyebrow">پروژه‌ها</p>
        <h1 id="projects-title">هنوز پروژه‌ای ندارید</h1>
        <p>اولین پروژه را بسازید تا اطلاعات آن را در یک فضای قابل ردیابی مدیریت کنید.</p>
        <Link className="button button--primary" href="/projects/new">
          ایجاد اولین پروژه
        </Link>
      </section>
    )
  }

  const loadMore = () => {
    if (!nextCursor || isPending) return
    setFailure(null)
    startTransition(async () => {
      const result = await loadMoreProjectsAction(nextCursor)
      if (result.status === "error") {
        setFailure({
          message: result.message,
          ...(result.requestId ? { requestId: result.requestId } : {})
        })
        return
      }
      setProjects((current) => {
        const known = new Set(current.map((project) => project.id))
        return [...current, ...result.page.data.filter((project) => !known.has(project.id))]
      })
      setNextCursor(result.page.meta.next_cursor)
      setHasMore(result.page.meta.has_more)
    })
  }

  return (
    <section className="projects-section" aria-labelledby="projects-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">فضای کاری</p>
          <h1 id="projects-title">پروژه‌ها</h1>
        </div>
        <Link className="button button--primary" href="/projects/new">
          ایجاد پروژه
        </Link>
      </div>
      <ul className="project-list">
        {projects.map((project) => (
          <li key={project.id}>
            <Link className="project-card" href={`/projects/${project.id}`}>
              <span className="project-card__title">{project.title}</span>
              <span className="project-card__meta">
                <span>{projectTypeLabel(project.project_type)}</span>
                <span className="status-badge">{projectStatusLabel(project.status)}</span>
              </span>
              <span className="project-card__updated">
                آخرین تغییر: <time dateTime={project.updated_at}>{project.updated_at}</time>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <div className="pagination-region" aria-live="polite">
        {failure ? (
          <p className="inline-alert" role="alert">
            {failure.message}
            {failure.requestId ? <span className="request-reference">شناسه پیگیری: {failure.requestId}</span> : null}
          </p>
        ) : null}
        {hasMore ? (
          <button
            className="button button--secondary"
            type="button"
            onClick={loadMore}
            disabled={isPending || !nextCursor}
          >
            {isPending ? "در حال بارگذاری…" : "نمایش پروژه‌های بیشتر"}
          </button>
        ) : null}
      </div>
    </section>
  )
}
