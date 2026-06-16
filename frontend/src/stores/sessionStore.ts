import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Session } from '@/types'
import { uuid } from '@/utils/id'

const STORAGE_KEY = 'ai_creator.sessions'
const CURRENT_KEY = 'ai_creator.current_session_id'

export const useSessionStore = defineStore(
  'session',
  () => {
    const sessions = ref<Session[]>([])
    const currentSessionId = ref<string>('')

    const currentSession = computed(() =>
      sessions.value.find((s) => s.id === currentSessionId.value),
    )

    function createSession(name?: string, kind: Session['kind'] = 'chat'): Session {
      const now = Date.now()
      const session: Session = {
        id: uuid(),
        name: name?.trim() || `新对话 ${sessions.value.length + 1}`,
        createdAt: now,
        updatedAt: now,
        kind,
      }
      sessions.value.unshift(session)
      currentSessionId.value = session.id
      return session
    }

    function ensureSession(): Session {
      if (!currentSessionId.value || !currentSession.value) {
        return createSession()
      }
      return currentSession.value
    }

    function switchSession(id: string) {
      if (sessions.value.some((s) => s.id === id)) {
        currentSessionId.value = id
      }
    }

    function renameSession(id: string, name: string) {
      const s = sessions.value.find((x) => x.id === id)
      if (s) {
        s.name = name.trim() || s.name
        s.updatedAt = Date.now()
      }
    }

    function deleteSession(id: string) {
      const idx = sessions.value.findIndex((s) => s.id === id)
      if (idx === -1) return
      sessions.value.splice(idx, 1)
      if (currentSessionId.value === id) {
        currentSessionId.value = sessions.value[0]?.id || ''
      }
    }

    function updateTimestamp(id: string) {
      const s = sessions.value.find((x) => x.id === id)
      if (s) {
        s.updatedAt = Date.now()
        // Reorder: most recent first
        sessions.value.sort((a, b) => b.updatedAt - a.updatedAt)
      }
    }

    return {
      sessions,
      currentSessionId,
      currentSession,
      createSession,
      ensureSession,
      switchSession,
      renameSession,
      deleteSession,
      updateTimestamp,
    }
  },
  {
    persist: {
      key: STORAGE_KEY,
      storage: localStorage,
      paths: ['sessions', 'currentSessionId'],
      // serializer fallback to JSON
    } as never,
  },
)

// Re-export storage keys for tests/debug
export const SESSION_STORAGE_KEYS = { STORAGE_KEY, CURRENT_KEY }
