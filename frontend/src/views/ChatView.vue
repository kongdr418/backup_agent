<template>
  <div class="chat-shell">
    <!-- Mobile sidebar overlay -->
    <div class="mobile-overlay" :class="{ open: mobileMenuOpen }" @click="mobileMenuOpen = false" />
    <aside class="mobile-sidebar glass-sidebar flex flex-col" :class="{ open: mobileMenuOpen }">
      <div class="px-3 pt-3 pb-2">
        <button class="new-chat-btn" @click="newChat(); mobileMenuOpen = false">
          <Plus class="w-3.5 h-3.5" />
          新对话
        </button>
      </div>

      <div class="px-2 py-1 text-[10.5px] text-ink-4 uppercase tracking-wider font-medium">
        会话历史
      </div>

      <div class="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        <div
          v-if="sessionStore.sessions.length === 0"
          class="text-[12px] text-ink-4 px-2 py-4 text-center"
        >
          暂无对话
        </div>

        <div
          v-for="s in sessionStore.sessions"
          :key="s.id"
          class="session-item"
          :class="sessionStore.currentSessionId === s.id ? 'is-active' : ''"
          @click="switchTo(s.id); mobileMenuOpen = false"
        >
          <MessageSquare class="w-3.5 h-3.5 shrink-0 mr-2 text-ink-3" />
          <span class="flex-1 truncate">{{ s.name }}</span>
          <button
            class="session-action"
            @click.stop="startRename(s.id, s.name)"
            title="重命名"
          >
            <Pencil class="w-3 h-3" />
          </button>
          <button
            v-if="sessionStore.sessions.length > 1"
            class="session-action danger"
            @click.stop="askDelete(s.id, s.name)"
            title="删除"
          >
            <Trash2 class="w-3 h-3" />
          </button>
        </div>
      </div>
    </aside>

    <!-- PC sidebar -->
    <aside class="pc-sidebar w-60 shrink-0 glass-sidebar flex flex-col">
      <div class="px-3 pt-3 pb-2">
        <button class="new-chat-btn" @click="newChat">
          <Plus class="w-3.5 h-3.5" />
          新对话
        </button>
      </div>

      <div class="px-2 py-1 text-[10.5px] text-ink-4 uppercase tracking-wider font-medium">
        会话历史
      </div>

      <div class="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        <div
          v-if="sessionStore.sessions.length === 0"
          class="text-[12px] text-ink-4 px-2 py-4 text-center"
        >
          暂无对话
        </div>

        <div
          v-for="s in sessionStore.sessions"
          :key="s.id"
          class="session-item"
          :class="sessionStore.currentSessionId === s.id ? 'is-active' : ''"
          @click="switchTo(s.id)"
        >
          <MessageSquare class="w-3.5 h-3.5 shrink-0 mr-2 text-ink-3" />
          <span class="flex-1 truncate">{{ s.name }}</span>
          <button
            class="session-action"
            @click.stop="startRename(s.id, s.name)"
            title="重命名"
          >
            <Pencil class="w-3 h-3" />
          </button>
          <button
            v-if="sessionStore.sessions.length > 1"
            class="session-action danger"
            @click.stop="askDelete(s.id, s.name)"
            title="删除"
          >
            <Trash2 class="w-3 h-3" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main + Document split-grid -->
    <div
      class="main-grid"
      :class="chatView.isSplit ? 'is-split' : ''"
    >
      <!-- Chat column -->
      <div class="chat-column">
        <!-- Mobile hamburger -->
        <div class="mobile-chat-header">
          <button class="mobile-menu-btn" @click="mobileMenuOpen = !mobileMenuOpen">
            <component :is="mobileMenuOpen ? X : Menu" class="w-5 h-5" />
          </button>
          <span class="mobile-chat-title">对话</span>
          <button class="mobile-menu-btn" @click="newChat">
            <Plus class="w-5 h-5" />
          </button>
        </div>

        <div ref="scrollEl" class="chat-scroll" :class="chatView.isSplit ? 'is-split' : ''">
          <div class="chat-stream">
            <section v-if="profileInterviewActive" class="onboarding-mode-bar">
              <div class="onboarding-mode-icon"><BrainCircuit class="w-4 h-4" /></div>
              <div>
                <strong>正在建立你的学习画像</strong>
                <span>通过自然对话了解你的基础、目标和学习偏好，确认前不会保存。</span>
              </div>
              <small>{{ onboardingProgress }}</small>
            </section>

            <EmptyState
              v-if="messages.length === 0 && !isProfileOnboarding"
              :icon="Sparkles"
              title="开始一段新对话"
              description="输入主题，让多智能体协同生成讲义、习题、思维导图或图文内容。"
            />

            <ChatMessage
              v-for="m in messages"
              :key="m.id"
              :message="m"
              :allow-actions="!profileInterviewActive"
            />

            <ProfileOnboardingSummary
              v-if="profileInterviewActive && onboardingState?.completed"
              :state="onboardingState"
              :loading="activeLoading"
              @continue="profileOnboarding.continueEditing"
              @confirm="profileOnboarding.confirm"
            />
          </div>
        </div>

        <ChatInput
          v-if="!profileInterviewActive || !onboardingState?.completed"
          :is-loading="activeLoading"
          :mode="profileInterviewActive ? 'profile_onboarding' : 'chat'"
          :can-cancel="!profileInterviewActive"
          @send="onSend"
          @cancel="cancel"
        />
      </div>

      <!-- Document viewer column (only when split) -->
      <div v-if="chatView.isSplit" class="doc-column">
        <DocumentViewer
          :kind="expandedMessage?.type"
          :data="expandedMessage?.data"
          :markdown-content="
            expandedMessage?.type === 'markdown' || expandedMessage?.type === 'text'
              ? expandedMessage?.content
              : ''
          "
          @close="chatView.collapse()"
        />
      </div>
    </div>

    <!-- Rename dialog -->
    <n-modal
      v-model:show="renameShow"
      preset="dialog"
      title="重命名对话"
      positive-text="确认"
      negative-text="取消"
      @positive-click="confirmRename"
    >
      <n-input v-model:value="renameValue" placeholder="新名称" @keyup.enter="confirmRename" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NModal, NInput, useDialog } from 'naive-ui'
import { Plus, MessageSquare, Pencil, Trash2, Sparkles, Menu, X, BrainCircuit } from 'lucide-vue-next'
import { useSessionStore } from '@/stores/sessionStore'
import { useChatStore } from '@/stores/chatStore'
import { useChatViewStore } from '@/stores/chatViewStore'
import { useChat } from '@/composables/useChat'
import { useProfileOnboardingConversation } from '@/composables/useProfileOnboardingConversation'
import { useRefreshGuard } from '@/composables/useRefreshGuard'
import ChatInput from '@/components/chat/ChatInput.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import DocumentViewer from '@/components/chat/DocumentViewer.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ProfileOnboardingSummary from '@/components/profile/ProfileOnboardingSummary.vue'
import { PROFILE_ONBOARDING_SESSION_KIND } from '@/utils/profileOnboarding'

const route = useRoute()
const router = useRouter()
const sessionStore = useSessionStore()
const chatStore = useChatStore()
const chatView = useChatViewStore()
const { messages, isLoading, sendMessage, cancel } = useChat()
const profileOnboarding = useProfileOnboardingConversation()
const dialog = useDialog()
useRefreshGuard()

const scrollEl = ref<HTMLElement | null>(null)
const mobileMenuOpen = ref(false)
const isProfileOnboarding = computed(
  () => sessionStore.currentSession?.kind === PROFILE_ONBOARDING_SESSION_KIND,
)
const onboardingState = computed(() => profileOnboarding.state.value)
const profileInterviewActive = computed(
  () => isProfileOnboarding.value && !onboardingState.value?.confirmed,
)
const activeLoading = computed(() => (
  profileInterviewActive.value ? profileOnboarding.isLoading.value : isLoading.value
))
const onboardingProgress = computed(() => {
  if (onboardingState.value?.confirmed) return '画像已保存'
  if (onboardingState.value?.completed) return '等待你确认'
  return '可随时离开，稍后继续'
})

// 当前展开的消息
const expandedMessage = computed(() => {
  if (!chatView.expandedMessageId) return null
  return messages.value.find((m) => m.id === chatView.expandedMessageId) || null
})

onMounted(async () => {
  chatView.init()
  if (route.query.mode === PROFILE_ONBOARDING_SESSION_KIND) {
    await profileOnboarding.startOrResume({ reopenConfirmed: true })
  } else if (sessionStore.sessions.length === 0) {
    sessionStore.createSession()
  } else if (!sessionStore.currentSessionId) {
    sessionStore.switchSession(sessionStore.sessions[0].id)
  }
})

// 消息变多时滚到底
watch(
  () => messages.value.length,
  () => nextTick(scrollToBottom),
  { immediate: true },
)
watch(
  () => messages.value[messages.value.length - 1]?.content,
  () => {
    // 只有非分栏时跟随底部
    if (!chatView.isSplit) nextTick(scrollToBottom)
  },
)

// 退出分栏时还原 scrollTop
watch(
  () => chatView.isSplit,
  (isSplit) => {
    if (!isSplit && scrollEl.value) {
      const top = chatView.lastScrollTop || 0
      nextTick(() => scrollEl.value?.scrollTo({ top, behavior: 'smooth' }))
    }
  },
)

function scrollToBottom() {
  scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
}

function newChat() {
  sessionStore.createSession()
  chatView.collapse()
  if (route.query.mode) void router.replace('/chat')
}

function switchTo(id: string) {
  sessionStore.switchSession(id)
  if (route.query.mode) void router.replace('/chat')
}

const renameShow = ref(false)
const renameValue = ref('')
const renameTargetId = ref('')

function startRename(id: string, name: string) {
  renameTargetId.value = id
  renameValue.value = name
  renameShow.value = true
}

function confirmRename() {
  const v = renameValue.value.trim()
  if (v) sessionStore.renameSession(renameTargetId.value, v)
  renameShow.value = false
}

function askDelete(id: string, name: string) {
  dialog.warning({
    title: '删除对话',
    content: `确定删除「${name}」?该对话的全部消息将被清空,操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      chatStore.dropSession(id)
      sessionStore.deleteSession(id)
    },
  })
}

async function onSend(text: string) {
  if (profileInterviewActive.value) {
    await profileOnboarding.sendMessage(text)
    return
  }
  await sendMessage(text)
}

const _ = computed(() => activeLoading.value)
</script>

<style scoped>
.chat-shell {
  height: 100%;
  display: flex;
  min-width: 0;
}

/* ============ Session sidebar ============ */
.new-chat-btn {
  width: 100%;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-radius: 10px;
  background: rgb(0, 0, 0);
  color: white;
  font-size: 13px;
  border: none;
  cursor: pointer;
  transition: all 250ms cubic-bezier(0.16, 1, 0.3, 1);
}

.session-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  color: rgb(var(--ink-2-rgb));
  transition: background-color 250ms cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}
.session-item:hover {
  background: rgb(var(--bg-subtle-rgb) / 0.7);
  color: rgb(var(--ink-1-rgb));
}
.session-item.is-active {
  background: transparent;
  color: rgb(var(--ink-1-rgb));
  font-weight: 500;
}
.session-item.is-active:hover {
  background: rgb(220, 220, 220);
  color: rgb(var(--ink-1-rgb));
}
.session-item.is-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  background: rgb(var(--ink-3-rgb));
  border-radius: 0 3px 3px 0;
}

.session-action {
  opacity: 0;
  padding: 3px;
  border-radius: 5px;
  background: transparent;
  border: none;
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  margin-left: 2px;
  transition: all 150ms cubic-bezier(0.16, 1, 0.3, 1);
}
.session-item:hover .session-action {
  opacity: 1;
}
.session-action:hover {
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-1-rgb));
}
.session-action.danger:hover {
  background: rgb(var(--terra-pale-rgb) / 0.6);
  color: rgb(var(--terra-rgb));
}

/* ============ Main grid (chat + document) ============ */
.main-grid {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: grid;
  grid-template-columns: 1fr;
  transition: grid-template-columns 400ms cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
}
.main-grid.is-split {
  grid-template-columns: 2fr 3fr;
}

.chat-column {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  min-height: 0;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.chat-stream {
  max-width: 1024px;  /* max-w-5xl */
  margin: 0 auto;
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.onboarding-mode-bar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 11px;
  padding: 12px 14px;
  border: 1px solid rgb(var(--forest-rgb) / 0.18);
  border-radius: 14px;
  background: rgb(var(--forest-rgb) / 0.055);
}

.onboarding-mode-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: rgb(var(--forest-rgb));
  background: rgb(var(--forest-rgb) / 0.11);
}

.onboarding-mode-bar div:nth-child(2) {
  display: grid;
  gap: 2px;
}

.onboarding-mode-bar strong {
  color: rgb(var(--ink-1-rgb));
  font-size: 12.5px;
}

.onboarding-mode-bar span,
.onboarding-mode-bar small {
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
}

/* 分栏模式收紧 */
.chat-scroll.is-split .chat-stream {
  max-width: 640px;
  padding: 24px 24px;
  gap: 20px;
}

.doc-column {
  min-width: 0;
  height: 100%;
  overflow: hidden;
  animation: doc-enter 400ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes doc-enter {
  0% { opacity: 0; transform: translateX(20px); }
  100% { opacity: 1; transform: translateX(0); }
}

/* ============ Mobile ============ */
@media (max-width: 767px) {
  /* Hide PC sidebar on mobile */
  .pc-sidebar {
    display: none !important;
  }
  /* Mobile chat header */
  .mobile-chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    height: 48px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--line);
    background: var(--bg-surface);
  }

  .mobile-menu-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--ink-secondary);
    background: transparent;
    border: none;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .mobile-menu-btn:active {
    background: rgb(var(--bg-subtle-rgb));
  }

  .mobile-chat-title {
    font-size: 15px;
    font-weight: 500;
    color: var(--ink-primary);
  }

  /* Mobile sidebar overlay */
  .mobile-overlay {
    position: fixed;
    inset: 0;
    z-index: 80;
    background: rgb(0 0 0 / 0.35);
    backdrop-filter: blur(2px);
    pointer-events: none;
    opacity: 0;
    transition: opacity 200ms ease;
  }
  .mobile-overlay.open {
    opacity: 1;
    pointer-events: auto;
  }

  @keyframes overlay-in {
    0% { opacity: 0; }
    100% { opacity: 1; }
  }

  /* Mobile sidebar */
  .mobile-sidebar {
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: 260px;
    z-index: 90;
    transform: translateX(-100%);
    transition: transform 300ms cubic-bezier(0.16, 1, 0.3, 1);
    background: var(--bg-surface);
    border-right: 1px solid var(--line);
    box-shadow: 4px 0 24px rgb(0 0 0 / 0.12);
    padding-top: env(safe-area-inset-top, 0);
    padding-bottom: env(safe-area-inset-bottom, 0);
  }
  .mobile-sidebar.open {
    transform: translateX(0);
  }

  /* Chat stream */
  .chat-stream {
    max-width: 100%;
    padding: 20px 16px;
    gap: 20px;
  }

  /* Main grid */
  .main-grid.is-split {
    grid-template-columns: 1fr;
  }

  /* Document viewer full-screen on mobile */
  .main-grid.is-split .doc-column {
    position: fixed;
    inset: 0;
    z-index: 70;
    background: var(--bg-surface);
    animation: doc-enter-mobile 300ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes doc-enter-mobile {
    0% { opacity: 0; transform: translateY(20px); }
    100% { opacity: 1; transform: translateY(0); }
  }

  /* Hide new chat button in header on mobile since sidebar has one */
  .mobile-chat-header .mobile-menu-btn:last-child {
    /* Keep it — user might want quick new chat */
  }
}

/* Hide mobile elements on desktop only */
@media (min-width: 768px) {
  .mobile-chat-header { display: none !important; }
  .mobile-overlay { display: none !important; }
  .mobile-sidebar { display: none !important; }
}
</style>
