import type { SseEvent } from '@/types'
import { getUserId } from '@/composables/useUserId'

export interface SseRequest {
  url: string
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
  headers?: Record<string, string>
}

/**
 * Fetch an SSE endpoint and yield each parsed `data:` JSON event.
 *
 * Backend frames look like:
 *   data: {"chunk": "...", ...}\n\n
 *
 * We tolerate heartbeat comments (`: ping`) and unparsable lines.
 */
export async function* sseFetch(req: SseRequest): AsyncGenerator<SseEvent, void, void> {
  const res = await fetch(req.url, {
    credentials: 'include',
    method: req.method ?? 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Accept: 'text/event-stream',
      ...req.headers,
    },
    body: req.body !== undefined
      ? JSON.stringify({ ...req.body, user_id: getUserId() })
      : undefined,
    signal: req.signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}${text ? `: ${text}` : ''}`)
  }
  if (!res.body) throw new Error('No response body')

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // Split on newlines, keep the trailing partial line in buffer
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const rawLine of lines) {
        const line = rawLine.trimEnd()
        if (!line) continue
        if (line.startsWith(':')) continue // heartbeat
        if (!line.startsWith('data:')) continue

        const dataStr = line.slice(5).trim()
        if (!dataStr) continue

        try {
          const parsed = JSON.parse(dataStr) as SseEvent
          yield parsed
          if (parsed.done) return
        } catch {
          // ignore unparsable line
        }
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* ignore */
    }
  }
}
