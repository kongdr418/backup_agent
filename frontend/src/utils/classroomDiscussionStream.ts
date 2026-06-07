import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import type { SseEvent } from '@/types'

export function scopeDiscussionMessageId(requestId: string, messageId?: string) {
  const scopedSuffix = (messageId || 'assistant').trim() || 'assistant'
  return `${requestId}:${scopedSuffix}`
}

export function upsertDiscussionAssistantMessage(
  messages: ClassroomDiscussionMessage[],
  payload: {
    message_id: string
    content: string
    trigger: string
    agent_id?: string
    agent_name?: string
    pending?: boolean
  },
): ClassroomDiscussionMessage[] {
  const updated = [...messages]
  const existingIndex = updated.findIndex((item) => item.message_id === payload.message_id)
  const nextMessage: ClassroomDiscussionMessage = {
    role: 'assistant',
    content: payload.content,
    trigger: payload.trigger,
    agent_id: payload.agent_id || 'teacher',
    agent_name: payload.agent_name || 'AI 教师',
    message_id: payload.message_id,
    pending: Boolean(payload.pending),
  }

  if (existingIndex >= 0) {
    updated[existingIndex] = {
      ...updated[existingIndex],
      ...nextMessage,
    }
  } else {
    updated.push(nextMessage)
  }
  return updated
}

export function applyDiscussionAgentEvent(
  messages: ClassroomDiscussionMessage[],
  event: Pick<SseEvent, 'type' | 'message_id' | 'agent_id' | 'agent_name' | 'chunk' | 'content'>,
  trigger: string,
): ClassroomDiscussionMessage[] {
  const messageId = event.message_id || `${event.agent_id || 'teacher'}-${Date.now()}`
  const updated = [...messages]
  const existingIndex = updated.findIndex((item) => item.message_id === messageId)
  const current = existingIndex >= 0 ? updated[existingIndex] : null

  const nextContent = event.type === 'agent_chunk'
    ? `${current?.content || ''}${event.chunk || ''}`
    : event.type === 'agent_done'
      ? event.content ?? current?.content ?? ''
      : current?.content ?? ''

  return upsertDiscussionAssistantMessage(updated, {
    message_id: messageId,
    content: nextContent,
    trigger,
    agent_id: event.agent_id || current?.agent_id || 'teacher',
    agent_name: event.agent_name || current?.agent_name || 'AI 教师',
    pending: event.type === 'agent_start',
  })
}
