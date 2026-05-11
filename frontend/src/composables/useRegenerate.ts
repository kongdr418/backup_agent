/**
 * useRegenerate — 重新生成上一条 AI 回复
 *
 * 流程:
 * 1. 找到当前 session 最后一条 user 消息(被回复的那条 prompt)
 * 2. 删除 session 末尾的 assistant 消息
 * 3. 用同一 prompt 重新调用 useChat.sendMessage
 *
 * 注意:必须在 isLoading=false 时才允许重试,否则可能并发两个流。
 */
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useChat } from './useChat'

export function useRegenerate() {
  const chatStore = useChatStore()
  const sessionStore = useSessionStore()
  const { sendMessage, cancel } = useChat()

  async function regenerate(): Promise<boolean> {
    const sid = sessionStore.currentSessionId
    if (!sid) return false

    // 如果还在流式生成,先取消
    if (chatStore.isLoading) {
      cancel()
      // 等一帧让 abort 生效
      await new Promise((r) => setTimeout(r, 50))
    }

    const lastUser = chatStore.getLastUserMessage(sid)
    if (!lastUser || !lastUser.content) return false

    // 移除最后一条 assistant(可能是错误/取消/或正常完成的)
    chatStore.removeLastAssistant(sid)

    // 用同一 prompt 重发
    await sendMessage(lastUser.content)
    return true
  }

  return { regenerate }
}
