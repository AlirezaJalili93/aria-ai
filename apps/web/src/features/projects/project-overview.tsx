import Link from "next/link"
import {
  ArrowRight,
  Clock,
  Tag,
  Activity,
  FileText,
  ListChecks,
  HelpCircle,
  FileSignature,
  Layers
} from "lucide-react"

import { projectStatusLabel, projectTypeLabel } from "./presentation"
import { ProjectOpenedEvent } from "./project-opened-event"
import { ProjectWorkspace } from "./project-workspace"
import type { AccountSelection, ContextSourceItem, Project } from "./types"

const modulesConfig = [
  {
    key: "Context",
    label: "زمینه پروژه",
    description: "بارگذاری ورودی‌ها، بریف‌های اولیه و تحلیل مستندات پیشین",
    icon: FileText
  },
  {
    key: "Requirements",
    label: "نیازمندی‌ها",
    description: "استخراج و تفکیک خودکار نیازمندی‌های عملکردی و کیفی",
    icon: ListChecks
  },
  {
    key: "Gaps",
    label: "ابهامات",
    description: "کشف تناقض‌ها، پرسش‌های شفاف‌سازی و نقاط مبهم پروژه",
    icon: HelpCircle
  },
  {
    key: "Scope",
    label: "محدوده",
    description: "تدوین سند رسمی محدوده کار و آماده‌سازی برای تأیید کارفرما",
    icon: FileSignature
  }
] as const

export function ProjectOverview({
  account,
  project,
  initialSources = [],
  emitOpenedEvent = true
}: Readonly<{
  account: AccountSelection
  project: Project
  initialSources?: readonly ContextSourceItem[]
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
          <ArrowRight className="icon-xs" aria-hidden="true" />
          <span>بازگشت به پروژه‌ها</span>
        </Link>

        <div className="overview-heading">
          <div className="overview-heading__info">
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
          <div className="metadata-card">
            <dt className="metadata-card__label">
              <Tag className="icon-xs" aria-hidden="true" />
              <span>نوع پروژه</span>
            </dt>
            <dd className="metadata-card__value">{projectTypeLabel(project.project_type)}</dd>
          </div>
          <div className="metadata-card">
            <dt className="metadata-card__label">
              <Activity className="icon-xs" aria-hidden="true" />
              <span>وضعیت</span>
            </dt>
            <dd className="metadata-card__value">{projectStatusLabel(project.status)}</dd>
          </div>
          <div className="metadata-card">
            <dt className="metadata-card__label">
              <Clock className="icon-xs" aria-hidden="true" />
              <span>آخرین تغییر</span>
            </dt>
            <dd className="metadata-card__value">
              <time dateTime={project.updated_at}>{project.updated_at}</time>
            </dd>
          </div>
        </dl>

        <section className="future-modules" aria-labelledby="project-sections-title">
          <div className="section-subheading">
            <Layers className="icon-sm text-primary" aria-hidden="true" />
            <h2 id="project-sections-title">بخش‌های پروژه</h2>
          </div>
          <div className="module-grid">
            {modulesConfig.map(({ key, label, description, icon: Icon }) => (
              <section className="module-card" key={key}>
                <div className="module-card__header">
                  <div className="module-card__icon" aria-hidden="true">
                    <Icon className="icon-sm" />
                  </div>
                  <div>
                    <span className="module-card__key">{key}</span>
                    <h3>{label}</h3>
                  </div>
                </div>
                <p className="module-card__desc">{description}</p>
                <div className="module-card__status">
                  <span className="module-card__badge">هنوز شروع نشده</span>
                </div>
              </section>
            ))}
          </div>
        </section>

        <ProjectWorkspace project={project} initialSources={initialSources} />
      </article>
    </>
  )
}
