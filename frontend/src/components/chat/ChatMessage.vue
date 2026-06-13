<template>
  <div
    class="chat-row"
    :class="message.role === 'user' ? 'is-user' : 'is-assistant'"
  >
    <!-- Body -->
    <div class="bubble-wrap">
      <!-- Text / Markdown 气泡 -->
      <div
        v-if="!message.type || message.type === 'text' || message.type === 'markdown'"
        class="bubble"
        :class="message.role === 'user' ? 'bubble-user' : 'bubble-assistant'"
      >
        <div
          v-if="message.content || message.status !== 'streaming'"
          class="prose prose-bubble"
          v-html="rendered"
        />
        <div v-else class="streaming-dots">
          <span /><span /><span />
        </div>
      </div>

      <!-- 各种内容卡(摘要 chip) -->
      <GraphicImageCard
        v-else-if="message.type === 'graphic_image'"
        :data="message.data"
        :is-expanded="isExpanded"
        @toggle="toggleExpand"
      />
      <VideoAudioCard
        v-else-if="message.type === 'video_audio'"
        :data="message.data"
        :is-expanded="isExpanded"
        @toggle="toggleExpand"
      />
      <ProgressCard
        v-else-if="message.type === 'progress'"
        :data="message.data!"
      />
      <ContentResultCard
        v-else-if="message.type === 'content_result'"
        :data="message.data"
        :is-expanded="isExpanded"
        @toggle="toggleExpand"
      />

      <!-- 错误 / 已停止 + 重试 -->
      <div
        v-if="message.status === 'error'"
        class="status-row error"
      >
        <CircleAlert class="w-3.5 h-3.5" />
        <span>{{ message.error || '生成失败' }}</span>
        <button v-if="allowActions" class="retry-btn" @click="onRegenerate">
          <RotateCcw class="w-3 h-3" /> 重新生成
        </button>
      </div>
      <div
        v-else-if="message.status === 'cancelled'"
        class="status-row cancelled"
      >
        <Square class="w-3.5 h-3.5" />
        <span>已停止</span>
        <button v-if="allowActions" class="retry-btn" @click="onRegenerate">
          <RotateCcw class="w-3 h-3" /> 重新生成
        </button>
      </div>

      <!-- Action toolbar(assistant + done 时显示) -->
      <div
        v-if="
          allowActions &&
          message.role === 'assistant' &&
          message.status !== 'streaming' &&
          message.status !== 'error' &&
          message.status !== 'cancelled'
        "
        class="toolbar"
      >
        <button
          v-if="message.content"
          class="tool-btn"
          @click="copy"
          :title="copied ? '已复制' : '复制'"
        >
          <Copy class="w-3 h-3" />
          <span>{{ copied ? '已复制' : '复制' }}</span>
        </button>
        <button class="tool-btn" @click="onRegenerate" title="重新生成">
          <RotateCcw class="w-3 h-3" />
          <span>重新生成</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import {
  Copy,
  CircleAlert,
  Square,
  RotateCcw,
} from 'lucide-vue-next'
import type { ChatMessage } from '@/types'
import GraphicImageCard from './GraphicImageCard.vue'
import VideoAudioCard from './VideoAudioCard.vue'
import ContentResultCard from './ContentResultCard.vue'
import ProgressCard from './ProgressCard.vue'
import { useChatViewStore } from '@/stores/chatViewStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useRegenerate } from '@/composables/useRegenerate'

const props = withDefaults(defineProps<{
  message: ChatMessage
  allowActions?: boolean
}>(), {
  allowActions: true,
})

const chatView = useChatViewStore()
const sessionStore = useSessionStore()
const { regenerate } = useRegenerate()

marked.setOptions({ gfm: true, breaks: true })

const rendered = computed(() => {
  const raw = props.message.content || ''
  if (!raw) return ''
  const html = marked.parse(raw, { async: false }) as string
  return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] })
})

const isExpanded = computed(() => chatView.expandedMessageId === props.message.id)

function toggleExpand() {
  if (isExpanded.value) {
    chatView.collapse()
  } else {
    const scrollEl = document.querySelector('.chat-scroll') as HTMLElement
    chatView.expand(sessionStore.currentSessionId, props.message.id, scrollEl?.scrollTop ?? 0)
  }
}

const copied = ref(false)
function copy() {
  navigator.clipboard.writeText(props.message.content || '').then(() => {
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  })
}

function onRegenerate() {
  regenerate()
}
</script>

<style scoped>
/* ============ 行容器 ============ */
.chat-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  animation: slideUpFade 280ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.chat-row.is-user {
  flex-direction: row-reverse;
}
.chat-row.is-assistant {
  justify-content: flex-start;
}

/* ============ 气泡 wrap (左右轨道) ============ */
.bubble-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.is-user .bubble-wrap {
  align-items: flex-end;
  max-width: 60%;
}
.is-assistant .bubble-wrap {
  align-items: flex-start;
  max-width: 68%;
}

/* 分栏模式下气泡比例放宽(由父容器加 .is-split class 触发) */
:global(.chat-scroll.is-split) .is-user .bubble-wrap { max-width: 80%; }
:global(.chat-scroll.is-split) .is-assistant .bubble-wrap { max-width: 88%; }

/* ============ 气泡本体 ============ */
.bubble {
  border-radius: 20px;
  padding: 14px 18px;
  font-size: 14.5px;
  line-height: 1.75;
  word-break: break-word;
}
.bubble-user {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  color: rgb(var(--ink-1-rgb));
  border-bottom-left-radius: 6px;
}
.bubble-assistant {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  color: rgb(var(--ink-1-rgb));
  border-bottom-left-radius: 6px;
}

/* ============ Streaming dots ============ */
.streaming-dots {
  display: flex;
  gap: 5px;
  padding: 4px 0;
}
.streaming-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgb(var(--ink-4-rgb));
  animation: pulse-soft 1.4s ease-in-out infinite;
}
.streaming-dots span:nth-child(2) { animation-delay: 0.2s; }
.streaming-dots span:nth-child(3) { animation-delay: 0.4s; }

/* ============ Status row ============ */
.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 12px;
  font-size: 13px;
  margin-top: 4px;
}
.status-row.error {
  background: rgb(var(--danger-rgb) / 0.08);
  color: rgb(var(--danger-rgb));
  border: 1px solid rgb(var(--danger-rgb) / 0.20);
}
.status-row.cancelled {
  background: rgb(var(--warning-rgb) / 0.08);
  color: rgb(var(--warning-rgb));
  border: 1px solid rgb(var(--warning-rgb) / 0.20);
}
.retry-btn {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition: all 150ms;
}
.retry-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
}

/* ============ Action toolbar ============ */
.toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 6px;
  padding: 0 4px;
  opacity: 0;
  animation: fade-in 250ms ease-out forwards;
}
.chat-row:hover .toolbar {
  opacity: 1;
}
.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 150ms;
}
.tool-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}
.tool-btn.copied {
  color: rgb(var(--success-rgb));
}

/* ============ Prose 气泡内 MD ============ */
:deep(.prose-bubble) {
  font-size: 14.5px;
  line-height: 1.75;
}
:deep(.prose-bubble p) { margin: 0.5em 0; }
:deep(.prose-bubble p:first-child) { margin-top: 0; }
:deep(.prose-bubble p:last-child) { margin-bottom: 0; }
:deep(.prose-bubble ul),
:deep(.prose-bubble ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}
:deep(.prose-bubble li) { margin: 0.3em 0; }
:deep(.prose-bubble strong) { font-weight: 600; }
:deep(.prose-bubble code) {
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 4px;
  padding: 0.1em 0.4em;
  font-size: 12.5px;
}
:deep(.prose-bubble pre) {
  background: rgb(var(--bg-inset-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  padding: 12px 16px;
  margin: 0.6em 0;
  overflow-x: auto;
  font-size: 13px;
}
:deep(.prose-bubble pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

@keyframes slideUpFade {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes pulse-soft {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
