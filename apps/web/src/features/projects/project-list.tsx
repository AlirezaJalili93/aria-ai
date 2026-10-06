"use client"

import Link from "next/link"
import { useState, useTransition } from "react"
import {
  FolderPlus,
  Plus,
  Clock,
  Layout,
  Building2,
  Sparkles,
  ChevronLeft,
  Briefcase
} from "lucide-react"

import { loadMoreProjectsAction } from "./actions"
import { projectStatusLabel, projectTypeLabel } from "./presentation"
import type { ProjectSummary, ProjectType } from "./types"

type ProjectListProps = Readonly<{
  initialProjects: readonly ProjectSummary[]
  initialNextCursor: string | null
  initialHasMore: boolean
}>

function getProjectTypeIcon(type: ProjectType) {
  switch (type) {
    case "landing":
      return <Layout className="icon-sm" aria-hidden="true" />
    case "corporate":
      return <Building2 className="icon-sm" aria-hidden="true" />
    case "portfolio":
      return <Sparkles className="icon-sm" aria-hidden="true" />
    default:
      return <Briefcase className="icon-sm" aria-hidden="true" />
  }
}

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
        <div className="empty-state__icon-wrapper" aria-hidden="true">
          <FolderPlus className="icon-xl" />
        </div>
        <p className="eyebrow">پروژه‌ها</p>
        <h1 id="projects-title">هنوز پروژه‌ای ندارید</h1>
        <p className="empty-state__description">
          اولین پروژه را بسازید تا اطلاعات آن را در یک فضای قابل ردیابی مدیریت کنید.
        </p>
        <Link className="button button--primary" href="/projects/new">
          <Plus className="icon-sm" aria-hidden="true" />
          <span>ایجاد اولین پروژه</span>
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
          <p className="section-intro">
            مدیریت، رصد نیازمندی‌ها و تبدیل سند بریف به محدوده کاری برای پروژه‌های فعال شما.
          </p>
        </div>
        <Link className="button button--primary" href="/projects/new">
          <Plus className="icon-sm" aria-hidden="true" />
          <span>ایجاد پروژه</span>
        </Link>
      </div>
      <ul className="project-list">
        {projects.map((project) => (
          <li key={project.id}>
            <Link className="project-card" href={`/projects/${project.id}`}>
              <div className="project-card__header">
                <div className="project-card__icon-badge" aria-hidden="true">
                  {getProjectTypeIcon(project.project_type)}
                </div>
                <span className="project-card__title">{project.title}</span>
                <span className="status-badge">{projectStatusLabel(project.status)}</span>
              </div>
              <div className="project-card__meta">
                <span className="project-card__type-tag">
                  {projectTypeLabel(project.project_type)}
                </span>
                <span className="project-card__updated">
                  <Clock className="icon-xs" aria-hidden="true" />
                  <span>آخرین تغییر:</span>{" "}
                  <time dateTime={project.updated_at}>{project.updated_at}</time>
                </span>
              </div>
              <div className="project-card__action" aria-hidden="true">
                <span>مشاهده پروژه</span>
                <ChevronLeft className="icon-xs" />
              </div>
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
