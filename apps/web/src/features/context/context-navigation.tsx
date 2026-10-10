import Link from "next/link"

export function ContextNavigation({ projectId, current }: Readonly<{ projectId: string; current: "sources" | "structured" }>) {
  return (
    <nav className="context-navigation" aria-label="بخش‌های زمینه پروژه">
      <Link className={current === "sources" ? "context-navigation__link context-navigation__link--active" : "context-navigation__link"} href={`/projects/${projectId}/context/sources`} aria-current={current === "sources" ? "page" : undefined}>منابع</Link>
      <Link className={current === "structured" ? "context-navigation__link context-navigation__link--active" : "context-navigation__link"} href={`/projects/${projectId}/context`} aria-current={current === "structured" ? "page" : undefined}>زمینه ساختاریافته</Link>
    </nav>
  )
}
