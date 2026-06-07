import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'

const STORAGE_PREFIX = 'ai_creator.classroom_discussion.v2'

function storageKey(classroomId: string, sceneId: string) {
  return `${STORAGE_PREFIX}.${classroomId}.${sceneId}`
}

function isDiscussionMessage(value: unknown): value is ClassroomDiscussionMessage {
  if (!value || typeof value !== 'object') return false
  const row = value as Partial<ClassroomDiscussionMessage>
  if ((row.role !== 'assistant' && row.role !== 'user') || typeof row.content !== 'string') {
    return false
  }
  const stringFieldsValid = ['agent_id', 'agent_name', 'message_id', 'trigger'].every((key) => {
    const value = row[key as keyof ClassroomDiscussionMessage]
    return value === undefined || typeof value === 'string'
  })
  const pendingValid = row.pending === undefined || typeof row.pending === 'boolean'
  return stringFieldsValid && pendingValid
}

export function savePersistedDiscussionMessages(
  classroomId: string,
  sceneId: string,
  messages: ClassroomDiscussionMessage[],
) {
  localStorage.setItem(storageKey(classroomId, sceneId), JSON.stringify(messages))
}

export function loadPersistedDiscussionMessages(classroomId: string, sceneId: string) {
  const raw = localStorage.getItem(storageKey(classroomId, sceneId))
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.every(isDiscussionMessage)) {
      return parsed
    }
  } catch {
    // ignore corrupt storage
  }
  clearPersistedDiscussionMessages(classroomId, sceneId)
  return null
}

export function clearPersistedDiscussionMessages(classroomId: string, sceneId: string) {
  localStorage.removeItem(storageKey(classroomId, sceneId))
}
