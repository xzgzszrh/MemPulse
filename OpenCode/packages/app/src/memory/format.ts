/**
 * Small formatting helpers for the memory surfaces. Relative timestamps come
 * from `utils/time.ts` so memory reads the same as the rest of the app.
 */

export function formatCount(value: number | undefined): string {
  if (!value) return "0"
  if (value < 1000) return String(value)
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`
  return `${(value / 1_000_000).toFixed(1)}M`
}

export function formatBytes(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "—"
  if (value < 1024) return `${value} B`
  const units = ["KB", "MB", "GB", "TB"]
  let size = value / 1024
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${size.toFixed(size < 10 ? 1 : 0)} ${units[unit]}`
}

const clock = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" })

export function formatClock(value: string | undefined): string {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  return clock.format(date)
}

export function formatDateTime(value: string | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date)
}

/** Collapse whitespace and clip to a single readable line. */
export function summarize(value: string | undefined, limit = 160): string {
  if (!value) return ""
  const flat = value.replace(/\s+/g, " ").trim()
  if (flat.length <= limit) return flat
  return `${flat.slice(0, limit - 1)}…`
}

/** Render an unknown JSON value as something a person can read in one line. */
export function describeValue(value: unknown): string {
  if (value === null || value === undefined) return "—"
  if (typeof value === "string") return value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function percent(part: number, total: number): number {
  if (!total) return 0
  return Math.round((part / total) * 100)
}
