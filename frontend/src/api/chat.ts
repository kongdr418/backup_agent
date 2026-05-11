import client from './client'
import { sseFetch } from './sse'
import type { ChatMessage, SseEvent } from '@/types'

export async function sendChat(message: string, sessionId: string) {
  const res = await client.post<{ response: string; history: ChatMessage[] }>('/api/chat', {
    message,
    session_id: sessionId,
  })
  return res.data
}

export async function clearHistory(sessionId: string) {
  await client.post('/api/clear', { session_id: sessionId })
}

export async function fetchHistory(sessionId: string) {
  const res = await client.get<{ history: ChatMessage[] }>('/api/history', {
    params: { session_id: sessionId },
  })
  return res.data.history
}

export interface ChatStreamArgs {
  message: string
  sessionId: string
  signal?: AbortSignal
}

export function chatStream(args: ChatStreamArgs): AsyncGenerator<SseEvent, void, void> {
  return sseFetch({
    url: '/api/chat/stream',
    method: 'POST',
    body: { message: args.message, session_id: args.sessionId },
    signal: args.signal,
  })
}
