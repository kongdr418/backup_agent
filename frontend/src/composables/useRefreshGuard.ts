import { onMounted, onUnmounted } from 'vue'
import { usePptStore } from '@/stores/pptStore'
import { useChatStore } from '@/stores/chatStore'

/**
 * 任意生成任务运行中时阻止页面刷新/关闭，弹出浏览器原生确认框。
 * 无参数——内部检查所有生成器状态。
 */
export function useRefreshGuard() {
  const pptStore = usePptStore()
  const chatStore = useChatStore()

  function handler(e: BeforeUnloadEvent) {
    if (pptStore.isGenerating || chatStore.isLoading) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  onMounted(() => window.addEventListener('beforeunload', handler))
  onUnmounted(() => window.removeEventListener('beforeunload', handler))
}
