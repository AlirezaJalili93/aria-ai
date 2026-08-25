"use client"

import { useState } from "react"

export function LogoutButton() {
  const [pending, setPending] = useState(false)
  return (
    <form action="/auth/logout" method="post" onSubmit={() => setPending(true)}>
      <button className="button button--secondary" type="submit" disabled={pending}>
        {pending ? "در حال خروج…" : "خروج"}
      </button>
    </form>
  )
}
