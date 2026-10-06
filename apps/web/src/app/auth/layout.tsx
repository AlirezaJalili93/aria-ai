import type { ReactNode } from "react"
import Link from "next/link"

export default function AuthLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="auth-shell app-shell">
      <header className="app-header auth-header" aria-label="سربرگ احراز هویت">
        <Link href="/" className="header-brand">
          <div className="brand-logo-icon">A</div>
          <span className="product-name" lang="en">
            Aria AI
          </span>
        </Link>
      </header>
      {children}
    </div>
  )
}
