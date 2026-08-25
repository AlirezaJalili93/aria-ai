import type { ReactNode } from "react"

export default function AuthLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="auth-shell">
      <header className="auth-header" aria-label="سربرگ احراز هویت">
        <span className="product-name" lang="en">
          Aria AI
        </span>
      </header>
      {children}
    </div>
  )
}
