import { computed } from 'vue'
import { saveLearnerProfile, sendProfileOnboardingMessage } from '@/api/learnerProfile'
import type { ChatMessage } from '@/types'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useSettingStore } from '@/stores/settingStore'
import { genId } from '@/utils/id'
import {
  PROFILE_ONBOARDING_SESSION_KIND,
  PROFILE_ONBOARDING_SESSION_NAME,
  findProfileOnboardingSession,
  getProfileOnboardingState,
  reopenProfileOnboardingState,
  type ProfileOnboardingState,
} from '@/utils/profileOnboarding'

export function useProfileOnboardingConversation() {
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()
  const settingStore = useSettingStore()

  const sessionId = computed(() => sessionStore.currentSessionId)
  const messages = computed(() => (
    sessionId.value ? chatStore.getMessages(sessionId.value) : []
  ))
  const state = computed(() => getProfileOnboardingState(messages.value))

  function ensureSession(): string {
    const existing = findProfileOnboardingSession(sessionStore.sessions)
    const session = existing || sessionStore.createSession(
      PROFILE_ONBOARDING_SESSION_NAME,
      PROFILE_ONBOARDING_SESSION_KIND,
    )
    sessionStore.switchSession(session.id)
    return session.id
  }

  function llmConfig() {
    return {
      content_model: settingStore.settings.content_model,
      content_api_key: settingStore.getEffectiveContentApiKey(),
      content_base_url: settingStore.getEffectiveContentBaseUrl(),
      content_provider_type: settingStore.getContentProviderType(),
    }
  }

  function conversationMessages(list: ChatMessage[]) {
    return list
      .filter((message) => message.status !== 'streaming' && message.content.trim())
      .map((message) => ({ role: message.role, content: message.content }))
  }

  function appendAssistantState(
    sid: string,
    content: string,
    nextState: ProfileOnboardingState,
  ) {
    chatStore.updateLastMessage(sid, (message) => {
      message.content = content
      message.status = 'done'
      message.data = { ...(message.data || {}), profileOnboarding: nextState }
    })
  }

  async function requestNext(sid: string) {
    const list = chatStore.getMessages(sid)
    const previousState = getProfileOnboardingState(list)
    const requestMessages = conversationMessages(list)
    chatStore.addMessage(sid, {
      id: genId('m'),
      role: 'assistant',
      content: '',
      createdAt: Date.now(),
      type: 'text',
      status: 'streaming',
    })
    chatStore.isLoading = true
    try {
      const result = await sendProfileOnboardingMessage(
        requestMessages,
        previousState?.draft,
        llmConfig(),
      )
      appendAssistantState(sid, result.reply, {
        draft: result.draft,
        completed: result.completed,
        currentField: result.current_field,
        confirmed: false,
      })
      sessionStore.updateTimestamp(sid)
    } catch (error) {
      const message = error instanceof Error ? error.message : '画像访谈暂时不可用'
      chatStore.updateLastMessage(sid, (assistant) => {
        assistant.status = 'error'
        assistant.error = message
      })
    } finally {
      chatStore.isLoading = false
    }
  }

  async function startOrResume(options: { reopenConfirmed?: boolean } = {}) {
    const sid = ensureSession()
    const list = chatStore.getMessages(sid)
    const last = list[list.length - 1]
    if (last?.status === 'streaming') {
      chatStore.removeLastAssistant(sid)
    }
    const current = getProfileOnboardingState(chatStore.getMessages(sid))
    if (options.reopenConfirmed && current?.confirmed) {
      chatStore.addMessage(sid, {
        id: genId('m'),
        role: 'assistant',
        content: '可以，我们继续梳理。你想修改哪部分，或者最近的学习目标和偏好有什么变化？',
        createdAt: Date.now(),
        type: 'text',
        status: 'done',
        data: {
          profileOnboarding: reopenProfileOnboardingState(current),
        },
      })
    } else if (chatStore.getMessages(sid).length === 0) {
      await requestNext(sid)
    }
  }

  async function sendMessage(content: string) {
    const trimmed = content.trim()
    if (!trimmed || chatStore.isLoading) return
    const sid = ensureSession()
    chatStore.addMessage(sid, {
      id: genId('m'),
      role: 'user',
      content: trimmed,
      createdAt: Date.now(),
      type: 'text',
      status: 'done',
    })
    await requestNext(sid)
  }

  function continueEditing() {
    const sid = ensureSession()
    const current = getProfileOnboardingState(chatStore.getMessages(sid))
    if (!current) return
    chatStore.addMessage(sid, {
      id: genId('m'),
      role: 'assistant',
      content: '可以继续补充或修正任何信息，我会重新整理画像草稿。',
      createdAt: Date.now(),
      type: 'text',
      status: 'done',
      data: {
        profileOnboarding: {
          ...current,
          completed: false,
          confirmed: false,
        },
      },
    })
  }

  async function confirm() {
    const sid = ensureSession()
    const current = getProfileOnboardingState(chatStore.getMessages(sid))
    if (!current || !current.completed || current.confirmed) return
    chatStore.isLoading = true
    try {
      const saved = await saveLearnerProfile(current.draft)
      chatStore.addMessage(sid, {
        id: genId('m'),
        role: 'assistant',
        content: '学习画像已经保存。接下来你可以继续告诉我想学习什么，我会结合这份画像来帮助你。',
        createdAt: Date.now(),
        type: 'text',
        status: 'done',
        data: {
          profileOnboarding: {
            ...current,
            draft: saved,
            confirmed: true,
          },
        },
      })
      sessionStore.updateTimestamp(sid)
    } catch (error) {
      const message = error instanceof Error ? error.message : '画像保存失败'
      chatStore.addMessage(sid, {
        id: genId('m'),
        role: 'assistant',
        content: '画像暂时没有保存成功，请稍后再试。',
        createdAt: Date.now(),
        type: 'text',
        status: 'error',
        error: message,
        data: {
          profileOnboarding: current,
        },
      })
    } finally {
      chatStore.isLoading = false
    }
  }

  return {
    messages,
    state,
    isLoading: computed(() => chatStore.isLoading),
    ensureSession,
    startOrResume,
    sendMessage,
    continueEditing,
    confirm,
  }
}
