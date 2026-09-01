import { redirect } from "next/navigation"

import { LogoutButton } from "../../features/auth/logout-button"
import { createClient } from "../../features/auth/supabase/server"

export default async function ProjectsPage() {
  const supabase = await createClient()
  const { data: claimsData } = await supabase.auth.getClaims()
  if (!claimsData?.claims) redirect("/auth/login")

  return (
    <div className="app-shell">
      <header className="app-header" aria-label="سربرگ محصول">
        <span className="product-name" lang="en">
          Aria AI
        </span>
        <LogoutButton />
      </header>
      <main id="main-content" className="projects-main" tabIndex={-1}>
        <section className="empty-state" aria-labelledby="projects-title">
          <p className="eyebrow">پروژه‌ها</p>
          <h1 id="projects-title">هنوز پروژه‌ای ندارید</h1>
          <p>اولین پروژه را بسازید تا Context و Scope آن را در یک فضای قابل ردیابی مدیریت کنید.</p>
          <button className="button button--primary" type="button" disabled>
            ایجاد اولین پروژه
          </button>
        </section>
      </main>
    </div>
  )
}
