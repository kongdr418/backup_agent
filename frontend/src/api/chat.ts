import client from './client'
import { sseFetch } from './sse'
import type { ChatMessage, SseEvent } from '@/types'

export async function sendChat(message: string, sessionId: string, opts?: {
  model?: string
  apiKey?: string
  baseUrl?: string
  providerType?: string
  contentModel?: string
  contentApiKey?: string
  contentBaseUrl?: string
}) {
  const res = await client.post<{ response: string; history: ChatMessage[] }>('/api/chat', {
    message,
    session_id: sessionId,
    model: opts?.model,
    api_key: opts?.apiKey,
    base_url: opts?.baseUrl,
    provider_type: opts?.providerType,
    content_model: opts?.contentModel,
    content_api_key: opts?.contentApiKey,
    content_base_url: opts?.contentBaseUrl,
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
  model?: string
  apiKey?: string
  baseUrl?: string
  providerType?: string
  contentModel?: string
  contentApiKey?: string
  contentBaseUrl?: string
}

export function chatStream(args: ChatStreamArgs): AsyncGenerator<SseEvent, void, void> {
  return sseFetch({
    url: '/api/chat/stream',
    method: 'POST',
    body: {
      message: args.message,
      session_id: args.sessionId,
      model: args.model,
      api_key: args.apiKey,
      base_url: args.baseUrl,
      provider_type: args.providerType,
      content_model: args.contentModel,
      content_api_key: args.contentApiKey,
      content_base_url: args.contentBaseUrl,
    },
    signal: args.signal,
  })
}
