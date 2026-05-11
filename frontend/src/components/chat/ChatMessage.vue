<template>
  <div
    class="chat-row"
    :class="message.role === 'user' ? 'is-user' : 'is-assistant'"
  >
    <!-- Avatar (assistant 在左,user 在右) -->
    <div
      v-if="message.role === 'assistant'"
      class="avatar avatar-assistant"
    >
      <Sparkles class="w-[14px] h-[14px]" />
    </div>

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
          :class="message.role === 'user' ? 'prose-on-accent' : ''"
          v-html="rendered"
        />
        <div v-else class="streaming-dots">
          <span /><span /><span />
        </div>
      </div>

      <!-- 各种内容卡(摘要 chip) -->
      <PptPreviewCard
        v-else-if="message.type === 'ppt_preview'"
        :data="message.data"
        :is-expanded="isExpanded"
        @toggle="toggleExpand"
      />
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
        <button class="retry-btn" @click="onRegenerate">
          <RotateCcw class="w-3 h-3" /> 重新生成
        </button>
      </div>
      <div
        v-else-if="message.status === 'cancelled'"
        class="status-row cancelled"
      >
        <Square class="w-3.5 h-3.5" />
        <span>已停止</span>
        <button class="retry-btn" @click="onRegenerate">
          <RotateCcw class="w-3 h-3" /> 重新生成
        </button>
      </div>

      <!-- Action toolbar(assistant + done 时显示) -->
      <div
        v-if="
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

    <!-- User avatar 在右 -->
    <div
      v-if="message.role === 'user'"
      class="avatar avatar-user"
    >
      我
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
  Sparkles,
  RotateCcw,
} from 'lucide-vue-next'
import type { ChatMessage } from '@/types'
import PptPreviewCard from './PptPreviewCard.vue'
import GraphicImageCard from './GraphicImageCard.vue'
import VideoAudioCard from './VideoAudioCard.vue'
import ContentResultCard from './ContentResultCard.vue'
import ProgressCard from './ProgressCard.vue'
import { useChatViewStore } from '@/stores/chatViewStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useRegenerate } from '@/composables/useRegenerate'

const props = defineProps<{ message: ChatMessage }>()

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
  const sid = sessionStore.currentSessionId
  if (!sid) return
  // 找到当前 chat scroll 容器的 scrollTop(简单实现:从 ChatView 提供)
  const scrollEl = document.querySelector('.chat-scroll') as HTMLElement | null
  const top = scrollEl?.scrollTop || 0
  chatView.toggle(sid, props.message.id, top)
}

const copied = ref(false)
async function copy() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* ignore */
  }
}

async function onRegenerate() {
  await regenerate()
}
</script>

<style scoped>
/* ============ 行容器 ============ */
.chat-row {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  width: 100%;
}

.chat-row.is-user {
  justify-content: flex-end;
}
.chat-row.is-assistant {
  justify-content: flex-start;
}

/* ============ Avatar ============ */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  margin-top: 2px;
}
.avatar-assistant {
  background: linear-gradient(
    135deg,
    rgb(var(--accent-rgb)),
    rgb(var(--hue-ppt-rgb))
  );
  color: white;
  box-shadow: 0 2px 8px -2px rgb(var(--accent-rgb) / 0.4);
}
.avatar-user {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border: 1px solid rgb(var(--line-rgb));
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
  line-height: 1.7;
  word-break: break-word;
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.04);
}

.bubble-user {
  background: rgb(var(--accent-rgb));
  color: white;
  border-bottom-right-radius: 6px;
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
  border-radius: 9999px;
  background: rgb(var(--ink-4-rgb));
  animation: dot-bounce 1.4s ease-in-out infinite;
}
.streaming-dots span:nth-child(2) { animation-delay: 0.16s; }
.streaming-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
  40% { transform: translateY(-4px); opacity: 1; }
}

/* ============ Status row(error / cancelled) ============ */
.status-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
}
.status-row.error { color: rgb(var(--danger-rgb)); }
.status-row.cancelled { color: rgb(var(--ink-3-rgb)); }

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  margin-left: 4px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 11px;
  cursor: pointer;
  transition: all 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.retry-btn:hover {
  background: rgb(var(--accent-rgb));
  color: white;
  border-color: transparent;
}

/* ============ Toolbar (hover 显示) ============ */
.toolbar {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.chat-row:hover .toolbar {
  opacity: 1;
}
.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
  cursor: pointer;
  transition: all 120ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.tool-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--line-rgb));
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
  padding-left: 1.4em;
}
:deep(.prose-bubble li) { margin: 0.3em 0; }
:deep(.prose-bubble strong) { font-weight: 600; }
:deep(.prose-bubble code) {
  background: rgb(var(--bg-subtle-rgb));
  padding: 0.1em 0.4em;
  border-radius: 5px;
  font-size: 0.86em;
  font-family: 'JetBrains Mono', monospace;
  color: rgb(var(--accent-rgb));
}
:deep(.prose-bubble pre) {
  background: rgb(var(--bg-inset-rgb));
  border: 1px solid rgb(var(--line-rgb));
  padding: 12px 14px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 0.6em 0;
  font-size: 13px;
}
:deep(.prose-bubble pre code) {
  background: none;
  color: inherit;
  padding: 0;
}

/* User 气泡(蓝色背景)上的 prose 反色 */
:deep(.prose-on-accent) { color: white; }
:deep(.prose-on-accent strong) { color: white; }
:deep(.prose-on-accent code) {
  background: rgb(255 255 255 / 0.18);
  color: white;
}
:deep(.prose-on-accent pre) {
  background: rgb(0 0 0 / 0.20);
  border-color: rgb(255 255 255 / 0.15);
}
</style>
