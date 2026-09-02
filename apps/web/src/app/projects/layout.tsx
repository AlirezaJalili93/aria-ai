import Link from "next/link"
import type { ReactNode } from "react"

import { LogoutButton } from "../../features/auth/logout-button"

export default function ProjectsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="app-shell">
      <header className="app-header" aria-label="سربرگ محصول">
        <Link className="product-name" href="/projects" lang="en">
          Aria AI
        </Link>
        <nav aria-label="پیمایش اصلی">
          <Link className="header-navigation-link" href="/projects">
            پروژه‌ها
          </Link>
        </nav>
        <LogoutButton />
      </header>
      {children}
    </div>
  )
}
