export const CLASSROOM_GENERATION_STORAGE_KEY = 'ai_creator.classroom_generation'

export type ClassroomGenerationSurface = 'home' | 'ppt-studio'

export interface PersistedClassroomGeneration {
  requestId: string
  surface: ClassroomGenerationSurface
  topic: string
  startedAt: number
}

function isPersistedClassroomGeneration(value: unknown): value is PersistedClassroomGeneration {
  if (!value || typeof value !== 'object') return false
  const data = value as Partial<PersistedClassroomGeneration>
  return (
    typeof data.requestId === 'string' &&
    data.requestId.length > 0 &&
    (data.surface === 'home' || data.surface === 'ppt-studio') &&
    typeof data.topic === 'string' &&
    typeof data.startedAt === 'number'
  )
}

export function savePersistedClassroomGeneration(state: PersistedClassroomGeneration) {
  localStorage.setItem(CLASSROOM_GENERATION_STORAGE_KEY, JSON.stringify(state))
}

export function loadPersistedClassroomGeneration() {
  const raw = localStorage.getItem(CLASSROOM_GENERATION_STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (isPersistedClassroomGeneration(parsed)) return parsed
  } catch {
    // Ignore corrupt storage and let the next generation overwrite it.
  }
  clearPersistedClassroomGeneration()
  return null
}

export function clearPersistedClassroomGeneration() {
  localStorage.removeItem(CLASSROOM_GENERATION_STORAGE_KEY)
}
