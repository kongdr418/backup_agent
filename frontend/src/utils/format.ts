/**
 * Formatting helpers.
 */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

export function formatTime(ts: number | string): string {
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
  if (Number.isNaN(d.getTime())) return '-'
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
}

export function relativeTime(ts: number | string): string {
  const d = typeof ts === 'number' ? new Date(ts) : new Date(ts)
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)} 天前`
  return formatTime(ts)
}

function pad2(n: number) {
  return n.toString().padStart(2, '0')
}

export function truncate(text: string, max = 30): string {
  if (text.length <= max) return text
  return `${text.slice(0, max)}…`
}
