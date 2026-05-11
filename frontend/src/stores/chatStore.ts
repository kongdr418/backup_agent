import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import type { ChatMessage } from '@/types'
import * as storage from '@/utils/storage'

const MSG_KEY_PREFIX = 'ai_creator.messages.'
const MAX_MESSAGES_PER_SESSION = 500

/**
 * Strip large binary fields before persisting; keep textual content + meta.
 * - slides[].base64 → drop
 * - imageBase64 / audioBase64 → drop
 * Replace with a flag so UI can re-fetch if needed.
 */
function sanitizeForStorage(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((m) => {
    if (!m.data) return m
    const data: Record<string, unknown> = { ...m.data }
    if (Array.isArray(data.slides)) {
      data.slides = (data.slides as Array<Record<string, unknown>>).map((s) => ({
        page: s.page,
        title: s.title,
        // base64 dropped
      }))
      data.slides_dropped = true
    }
    if (data.imageBase64) {
      delete data.imageBase64
      data.image_dropped = true
    }
    if (data.audioBase64) {
      delete data.audioBase64
      data.audio_dropped = true
    }
    return { ...m, data }
  })
}

export const useChatStore = defineStore('chat', () => {
  const isLoading = ref(false)
  const abortController = ref<AbortController | null>(null)

  // sessionId -> reactive ChatMessage[]
  const messagesMap = reactive<Record<string, ChatMessage[]>>({})

  // Debounce write per-session
  const writeTimers: Record<string, ReturnType<typeof setTimeout>> = {}

  function ensureSession(sessionId: string) {
    if (!messagesMap[sessionId]) {
      const stored = storage.getItem<ChatMessage[]>(`${MSG_KEY_PREFIX}${sessionId}`)
      messagesMap[sessionId] = reactive(stored || []) as ChatMessage[]
    }
  }

  function getMessages(sessionId: string): ChatMessage[] {
    ensureSession(sessionId)
    return messagesMap[sessionId]
  }

  function persist(sessionId: string) {
    if (writeTimers[sessionId]) clearTimeout(writeTimers[sessionId])
    writeTimers[sessionId] = setTimeout(() => {
      const list = messagesMap[sessionId]
      if (!list) return
      // Cap and sanitize before write
      const tail = list.length > MAX_MESSAGES_PER_SESSION
        ? list.slice(-MAX_MESSAGES_PER_SESSION)
        : list
      storage.setItem(`${MSG_KEY_PREFIX}${sessionId}`, sanitizeForStorage(tail))
    }, 200)
  }

  function addMessage(sessionId: string, message: ChatMessage) {
    ensureSession(sessionId)
    messagesMap[sessionId].push(message)
    persist(sessionId)
  }

  function updateLastMessage(sessionId: string, updater: (msg: ChatMessage) => void) {
    ensureSession(sessionId)
    const list = messagesMap[sessionId]
    if (list.length > 0) {
      updater(list[list.length - 1])
      persist(sessionId)
    }
  }

  function clearMessages(sessionId: string) {
    ensureSession(sessionId)
    messagesMap[sessionId].splice(0)
    storage.removeItem(`${MSG_KEY_PREFIX}${sessionId}`)
  }

  /**
   * Remove the last assistant message — used by 重新生成 / retry flow.
   * Returns the removed message (caller can read its data if needed).
   */
  function removeLastAssistant(sessionId: string): ChatMessage | null {
    ensureSession(sessionId)
    const list = messagesMap[sessionId]
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].role === 'assistant') {
        const [removed] = list.splice(i, 1)
        persist(sessionId)
        return removed
      }
    }
    return null
  }

  /**
   * Get the last user message — used by 重新生成 to retrieve the original prompt.
   */
  function getLastUserMessage(sessionId: string): ChatMessage | null {
    ensureSession(sessionId)
    const list = messagesMap[sessionId]
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].role === 'user') return list[i]
    }
    return null
  }

  function dropSession(sessionId: string) {
    delete messagesMap[sessionId]
    storage.removeItem(`${MSG_KEY_PREFIX}${sessionId}`)
  }

  function setAbortController(ctrl: AbortController | null) {
    abortController.value = ctrl
  }

  function cancelStream() {
    abortController.value?.abort()
    abortController.value = null
    isLoading.value = false
  }

  return {
    isLoading,
    abortController,
    getMessages,
    addMessage,
    updateLastMessage,
    clearMessages,
    removeLastAssistant,
    getLastUserMessage,
    dropSession,
    setAbortController,
    cancelStream,
  }
})
