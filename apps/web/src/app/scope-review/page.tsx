import type { Metadata } from "next"

import { ScopeReviewBootstrap } from "../../features/scope-review/scope-review-bootstrap"

export const metadata: Metadata = {
  title: "مرور محدوده پروژه | Aria AI",
  robots: { index: false, follow: false }
}

export default function ScopeReviewPage() {
  return <ScopeReviewBootstrap />
}
