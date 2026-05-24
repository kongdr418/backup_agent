import { uuid } from '@/utils/id'

const STORAGE_KEY = 'ai_creator.user_id'

let cached: string | null = null

export function getUserId(): string {
  if (cached) return cached
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    cached = stored
    return stored
  }
  const newId = uuid()
  localStorage.setItem(STORAGE_KEY, newId)
  cached = newId
  return newId
}
