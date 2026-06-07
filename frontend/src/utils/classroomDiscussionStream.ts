import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import type { SseEvent } from '@/types'

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

  const nextMessage: ClassroomDiscussionMessage = {
    role: 'assistant',
    content: nextContent,
    trigger,
    agent_id: event.agent_id || current?.agent_id || 'teacher',
    agent_name: event.agent_name || current?.agent_name || 'AI 教师',
    message_id: messageId,
    pending: event.type === 'agent_start',
  }

  if (event.type === 'agent_chunk' || event.type === 'agent_done') {
    nextMessage.pending = false
  }

  if (existingIndex >= 0) {
    updated[existingIndex] = nextMessage
  } else {
    updated.push(nextMessage)
  }
  return updated
}
