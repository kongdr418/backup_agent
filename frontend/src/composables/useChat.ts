import { computed, ref } from 'vue'
import type { ChatMessage } from '@/types'
import { genId } from '@/utils/id'
import { chatStream } from '@/api/chat'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useSettingStore } from '@/stores/settingStore'

export function useChat() {
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()
  const settingStore = useSettingStore()
  const error = ref<string>('')

  const sessionId = computed(() => sessionStore.currentSessionId)
  const messages = computed(() => {
    if (!sessionId.value) return []
    return chatStore.getMessages(sessionId.value)
  })

  async function sendMessage(content: string) {
    const trimmed = content.trim()
    if (!trimmed) return

    const session = sessionStore.ensureSession()
    const sid = session.id
    error.value = ''

    // Append user message
    const userMsg: ChatMessage = {
      id: genId('m'),
      role: 'user',
      content: trimmed,
      createdAt: Date.now(),
      type: 'text',
    }
    chatStore.addMessage(sid, userMsg)
    sessionStore.updateTimestamp(sid)

    // Auto-rename: take first user message as session name
    if (session.name.startsWith('新对话') && !session.name.includes(' · ')) {
      const previewName = trimmed.length > 18 ? `${trimmed.slice(0, 18)}…` : trimmed
      sessionStore.renameSession(sid, previewName)
    }

    // Append empty assistant placeholder
    const assistantMsg: ChatMessage = {
      id: genId('m'),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      status: 'streaming',
      type: 'text',
    }
    chatStore.addMessage(sid, assistantMsg)

    chatStore.isLoading = true
    const ctrl = new AbortController()
    chatStore.setAbortController(ctrl)

    let streamingText = ''

    try {
      const stream = chatStream({
        message: trimmed,
        sessionId: sid,
        signal: ctrl.signal,
        model: settingStore.settings.chat_model,
        apiKey: settingStore.getEffectiveApiKey(),
        baseUrl: settingStore.getEffectiveBaseUrl(),
        providerType: settingStore.getProviderType(),
        contentModel: settingStore.settings.content_model,
        contentApiKey: settingStore.getEffectiveContentApiKey(),
        contentBaseUrl: settingStore.getEffectiveContentBaseUrl(),
        contentProviderType: settingStore.getContentProviderType(),
      })

      for await (const ev of stream) {
        if (ev.done) break

        if (ev.chunk) {
          streamingText += ev.chunk
          chatStore.updateLastMessage(sid, (m) => {
            m.content = streamingText
            if (!m.type || m.type === 'text' || m.type === 'markdown') m.type = 'markdown'
          })
        }

        if (ev.type === 'ppt_preview_start') {
          chatStore.updateLastMessage(sid, (m) => {
            m.type = 'ppt_preview'
            m.data = {
              totalPages: ev.total_pages,
              filename: ev.filename,
              slides: [],
            }
          })
        }

        if (ev.type === 'ppt_slide' && ev.base64) {
          chatStore.updateLastMessage(sid, (m) => {
            if (!m.data) m.data = {}
            const arr = (m.data.slides as Array<{ page: number; base64: string; title: string }>) || []
            arr.push({
              page: Number(ev.page) || arr.length + 1,
              base64: String(ev.base64),
              title: String(ev.title || ''),
            })
            m.data.slides = arr
          })
        }

        if (ev.type === 'graphic_text_data' && ev.xiaohongshu) {
          chatStore.updateLastMessage(sid, (m) => {
            m.data = { ...(m.data || {}), xiaohongshu: ev.xiaohongshu }
          })
        }

        if (ev.type === 'graphic_image_data' && ev.image_base64) {
          chatStore.updateLastMessage(sid, (m) => {
            m.type = 'graphic_image'
            m.data = { ...(m.data || {}), imageBase64: ev.image_base64, image_path: ev.image_filename, prompt: ev.prompt }
          })
        }

        if (ev.type === 'video_audio_data' && ev.audio_base64) {
          chatStore.updateLastMessage(sid, (m) => {
            m.type = 'video_audio'
            m.data = { audioBase64: ev.audio_base64, audio_path: ev.audio_filename, voiceoverText: ev.voiceover_text }
          })
        }

        if (ev.type === 'progress') {
          chatStore.updateLastMessage(sid, (m) => {
            // Don't let progress overwrite media card types
            const isMedia = m.type === 'graphic_image' || m.type === 'video_audio' || m.type === 'ppt_preview'
            if (!isMedia) {
              m.type = 'progress'
            }
            m.data = {
              ...(m.data || {}),
              stage: ev.stage,
              kind: (ev as Record<string, unknown>).kind,
              percent: (ev as Record<string, unknown>).percent as number ?? ev.progress ?? 0,
              label: ev.message,
              detail: (ev as Record<string, unknown>).detail,
              format: (ev as Record<string, unknown>).format,
              startedAt: m.data?.startedAt || Date.now(),
            }
          })
        }

        if (ev.type?.endsWith('_complete')) {
          // graphic_complete / video_complete 已经由 graphic_image_data / video_audio_data 渲染专用卡片，
          // 这里只需要把 ev.data 合并进 m.data 作为元信息（topic / filepath 等），不能覆盖 m.type
          const isMediaComplete = ev.type === 'graphic_complete' || ev.type === 'video_complete'
          chatStore.updateLastMessage(sid, (m) => {
            if (!isMediaComplete) {
              m.type = 'content_result'
            }
            m.data = { ...(m.data || {}), ...(ev.data as Record<string, unknown> || {}), completeType: ev.type }
          })
        }

        if (ev.type === 'error' && ev.message) {
          throw new Error(ev.message)
        }
      }

      chatStore.updateLastMessage(sid, (m) => {
        m.status = 'done'
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败'
      const aborted = msg.includes('aborted') || msg === 'AbortError'
      if (!aborted) error.value = msg
      chatStore.updateLastMessage(sid, (m) => {
        m.status = aborted ? 'cancelled' : 'error'
        m.error = aborted ? '已停止' : msg
      })
    } finally {
      chatStore.isLoading = false
      chatStore.setAbortController(null)
    }
  }

  function cancel() {
    chatStore.cancelStream()
  }

  function clear() {
    if (sessionId.value) {
      chatStore.clearMessages(sessionId.value)
    }
  }

  return {
    messages,
    isLoading: computed(() => chatStore.isLoading),
    error,
    sendMessage,
    cancel,
    clear,
  }
}
