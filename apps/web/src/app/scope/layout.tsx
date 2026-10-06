import Link from "next/link"
import type { ReactNode } from "react"
import { ShieldCheck } from "lucide-react"

export default function ScopeLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="app-shell scope-portal-shell">
      <header className="app-header" aria-label="سربرگ پورتال تأییدیه کارفرما">
        <div className="app-header__start">
          <Link className="product-name" href="/" lang="en">
            <span className="product-logo-mark" aria-hidden="true">A</span>
            <span>Aria AI</span>
          </Link>
          <span className="portal-badge">پورتال اسناد و تأییدیه کارفرما</span>
        </div>
        <div className="app-header__end">
          <span className="status-badge">
            <ShieldCheck className="icon-xs text-primary" aria-hidden="true" />
            <span>اتصال امن</span>
          </span>
        </div>
      </header>
      <main id="main-content" className="scope-portal-main" tabIndex={-1}>
        {children}
      </main>
    </div>
  )
}
