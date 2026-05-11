/**
 * localStorage wrapper with JSON serialization, schema versioning,
 * and graceful quota-exceeded handling.
 */
const VERSION_KEY = 'ai_creator.schema_version'
const SCHEMA_VERSION = 1

function ensureVersion() {
  try {
    const v = localStorage.getItem(VERSION_KEY)
    if (v == null) {
      localStorage.setItem(VERSION_KEY, String(SCHEMA_VERSION))
    }
  } catch {
    /* ignore */
  }
}

ensureVersion()

export function getItem<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    if (raw == null) return null
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setItem<T>(key: string, value: T): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch (e) {
    if (isQuotaError(e)) {
      pruneOldestSessions()
      try {
        localStorage.setItem(key, JSON.stringify(value))
        return true
      } catch {
        return false
      }
    }
    return false
  }
}

export function removeItem(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

export function listKeys(prefix: string): string[] {
  const keys: string[] = []
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k && k.startsWith(prefix)) keys.push(k)
    }
  } catch {
    /* ignore */
  }
  return keys
}

function isQuotaError(e: unknown): boolean {
  if (!(e instanceof Error)) return false
  const name = e.name
  return (
    name === 'QuotaExceededError' ||
    name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
    /quota/i.test(e.message)
  )
}

/**
 * Best-effort: drop the messages of the least-recently-updated session
 * when storage is full. Sessions metadata is left intact.
 */
function pruneOldestSessions() {
  try {
    const meta = getItem<Array<{ id: string; updatedAt: number }>>('ai_creator.sessions') || []
    if (meta.length <= 1) return
    const sorted = [...meta].sort((a, b) => a.updatedAt - b.updatedAt)
    // remove oldest 25% messages payloads
    const dropCount = Math.max(1, Math.floor(sorted.length * 0.25))
    for (let i = 0; i < dropCount; i++) {
      removeItem(`ai_creator.messages.${sorted[i].id}`)
    }
  } catch {
    /* ignore */
  }
}
