/**
 * Lightweight unique-id generator. Sufficient for client-side
 * message / session ids; not cryptographically secure.
 */
export function genId(prefix = ''): string {
  const s = Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
  return prefix ? `${prefix}_${s}` : s
}

export function uuid(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  // Fallback (RFC4122-ish, not strictly compliant)
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
