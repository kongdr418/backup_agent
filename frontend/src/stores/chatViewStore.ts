/**
 * Chat View Store — 分栏展开状态机
 *
 * - expandedMessageId: 当前在右侧分栏面板查看的消息 ID(全局只允许一个展开)
 * - expandedSessionId: 该消息所属 session(切换会话时自动收起)
 * - lastScrollTop: 进入分栏前对话流的滚动位置(收起时还原)
 *
 * 用法:
 *   const view = useChatViewStore()
 *   view.expand(sid, mid, scrollEl.scrollTop)
 *   view.collapse()
 *   view.isSplit  // computed boolean
 */
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useSessionStore } from './sessionStore'

export const useChatViewStore = defineStore('chatView', () => {
  const expandedMessageId = ref<string | null>(null)
  const expandedSessionId = ref<string | null>(null)
  const lastScrollTop = ref(0)

  const isSplit = computed(() => expandedMessageId.value !== null)

  function expand(sessionId: string, messageId: string, scrollTop: number) {
    lastScrollTop.value = scrollTop
    expandedSessionId.value = sessionId
    expandedMessageId.value = messageId
  }

  function collapse() {
    expandedMessageId.value = null
    expandedSessionId.value = null
  }

  function toggle(sessionId: string, messageId: string, scrollTop: number) {
    if (expandedMessageId.value === messageId) collapse()
    else expand(sessionId, messageId, scrollTop)
  }

  // 切换会话时自动收起(需 session store 已就绪)
  let watcher: (() => void) | null = null
  function init() {
    if (watcher) return
    const session = useSessionStore()
    watcher = watch(
      () => session.currentSessionId,
      () => collapse(),
    )
  }

  return {
    expandedMessageId,
    expandedSessionId,
    lastScrollTop,
    isSplit,
    expand,
    collapse,
    toggle,
    init,
  }
})
