import type { Metadata } from "next"

import { getScopeSignatureAction } from "../../../features/scope/actions"
import { ScopeSignoff } from "../../../features/scope/scope-signoff"

export const metadata: Metadata = {
  title: "سند محدوده کارفرما - Aria AI",
  description: "مشاهده و تأیید رسمی سند محدوده کار و اقلام تحویلی پروژه در پورتال Aria AI"
}

export default async function ScopePage({
  params
}: Readonly<{ params: Promise<{ scopeId: string }> }>) {
  const { scopeId } = await params
  const initialSignature = await getScopeSignatureAction(scopeId)

  return <ScopeSignoff scopeId={scopeId} initialSignature={initialSignature} />
}
