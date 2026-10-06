import Link from "next/link"
import type { ReactNode } from "react"
import { FolderGit2 } from "lucide-react"

import { LogoutButton } from "../../features/auth/logout-button"

export default function ProjectsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="app-shell">
      <header className="app-header" aria-label="سربرگ محصول">
        <div className="app-header__start">
          <Link className="product-name" href="/projects" lang="en">
            <span className="product-logo-mark" aria-hidden="true">A</span>
            <span>Aria AI</span>
          </Link>
          <nav aria-label="پیمایش اصلی">
            <Link className="header-navigation-link header-navigation-link--active" href="/projects">
              <FolderGit2 className="icon-xs" aria-hidden="true" />
              <span>پروژه‌ها</span>
            </Link>
          </nav>
        </div>
        <div className="app-header__end">
          <LogoutButton />
        </div>
      </header>
      {children}
    </div>
  )
}
