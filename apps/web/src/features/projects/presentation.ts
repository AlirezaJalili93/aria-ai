import type { Project } from "./types"

export function projectTypeLabel(type: Project["project_type"]): string {
  return { landing: "لندینگ", corporate: "شرکتی", portfolio: "پورتفولیو" }[type]
}

export function projectStatusLabel(status: Project["status"]): string {
  return {
    draft: "پیش‌نویس",
    active: "فعال",
    awaiting_approval: "در انتظار تأیید",
    approved: "تأییدشده",
    generating: "در حال تولید",
    delivered: "تحویل‌شده",
    archived: "بایگانی‌شده"
  }[status]
}
