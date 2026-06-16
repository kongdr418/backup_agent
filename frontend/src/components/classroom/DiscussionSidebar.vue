<template>
  <aside class="discussion-sidebar">
    <div class="sidebar-header">
      <div>
        <div class="sidebar-kicker">课堂讨论</div>
        <div class="sidebar-title">正在讨论本课内容</div>
      </div>
      <div class="header-actions">
        <span v-if="autoAdvancePaused" class="pause-badge">自动翻页已暂停</span>
      </div>
    </div>

    <div ref="messageListRef" class="message-list" @wheel.passive="onUserScroll" @scroll="onScrollEvent">
      <div v-if="!messages.length" class="empty-state">
        <p>你可以随时追问这一课已经讲过的内容。</p>
        <p>我会尽量用提示、追问和例子来带你想清楚。</p>
      </div>

      <article
        v-for="(message, index) in messages"
        :key="message.message_id || `${message.role}-${index}-${message.content.slice(0, 24)}`"
        class="message-card"
        :class="[message.role, message.agent_id || '', { pending: message.pending }]"
      >
        <div class="message-role">{{ roleLabel(message) }}</div>
        <div v-if="message.pending && !message.content" class="thinking-row">
          <span class="thinking-label">正在思考</span>
          <span class="thinking-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </div>
        <div v-else class="message-content" v-html="renderMarkdown(message.content)" />
      </article>

      <article v-if="submitting && !hasStreamingAssistant" class="message-card assistant pending">
        <div class="message-role">{{ multiAgentEnabled ? '多 Agent 讨论' : 'AI 教师' }}</div>
        <div class="thinking-row">
          <span class="thinking-label">正在思考</span>
          <span class="thinking-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        </div>
      </article>
    </div>

    <div class="quick-actions">
      <button
        v-for="action in quickActions"
        :key="action"
        type="button"
        class="quick-btn"
        :disabled="submitting"
        @click="$emit('quick-action', action)"
      >
        {{ action }}
      </button>
    </div>

    <form class="input-area" @submit.prevent="handleSubmit">
      <textarea
        v-model="draft"
        class="question-input"
        :disabled="submitting"
        rows="4"
        placeholder="输入你的问题，比如：这页为什么要先判断条件？"
        @keydown="onTextareaKeydown"
      />
      <div class="input-actions">
        <label class="agent-toggle">
          <input
            type="checkbox"
            :checked="multiAgentEnabled"
            :disabled="submitting"
            @change="onMultiAgentChange"
          />
          <span class="agent-toggle-track" aria-hidden="true">
            <span class="agent-toggle-thumb" />
          </span>
          <span>多 Agent</span>
        </label>
        <div class="submit-actions">
          <button
            type="button"
            class="clear-btn"
            :disabled="submitting || !messages.length"
            @click="$emit('clear-history')"
          >
            清空
          </button>
          <button type="submit" class="submit-btn" :disabled="submitting || !draft.trim()">
            {{ submitting ? '思考中...' : '发送' }}
          </button>
        </div>
      </div>
    </form>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import { shouldSubmitDiscussionOnEnter } from '@/utils/discussionInput'

const props = defineProps<{
  messages: ClassroomDiscussionMessage[]
  submitting?: boolean
  autoAdvancePaused?: boolean
  multiAgentEnabled?: boolean
}>()

const emit = defineEmits<{
  submit: [content: string]
  'quick-action': [action: string]
  'update:multi-agent-enabled': [enabled: boolean]
  'clear-history': []
}>()

const draft = ref('')
const quickActions = ['换个例子', '再提示一点', '总结一下']
const messageListRef = ref<HTMLElement | null>(null)

// ── 智能滚动：对标豆包 ──
const autoFollow = ref(true)

function isAtBottom(): boolean {
  const el = messageListRef.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 32
}

function scrollToBottom(behavior: ScrollBehavior = 'auto') {
  const el = messageListRef.value
  if (!el) return
  el.scrollTo({ top: el.scrollHeight, behavior })
}

function onUserScroll(event: WheelEvent) {
  if (event.deltaY < 0) {
    // 用户向上滚 → 立即终止自动跟随
    autoFollow.value = false
  }
}

function onScrollEvent() {
  // 用户手动滚回底部 → 恢复自动跟随
  if (isAtBottom()) {
    autoFollow.value = true
  }
}

// 用户发送新消息 → 重新启用自动跟随并滚到底
function handleSubmit() {
  autoFollow.value = true
  nextTick(() => scrollToBottom('auto'))
  const content = draft.value.trim()
  if (!content || props.submitting) return
  emit('submit', content)
  draft.value = ''
}

// 监听消息变化：流式输出时自动跟随
watch(
  () => props.messages.length,
  () => {
    if (autoFollow.value) {
      nextTick(() => scrollToBottom('auto'))
    }
  },
)

// 监听最后一条消息内容变化（流式增量）
watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return last?.content ?? ''
  },
  () => {
    if (autoFollow.value) {
      nextTick(() => scrollToBottom('auto'))
    }
  },
)

// 当 messages 末尾是 assistant 时，隐藏"正在思考"指示器，避免双气泡
const hasStreamingAssistant = computed(
  () => props.messages[props.messages.length - 1]?.role === 'assistant',
)

marked.setOptions({ gfm: true, breaks: true })

/**
 * 闭合 LLM 流式回复里常见的未配对 markdown 标记。
 *
 * 背景：讨论回复走 `content_llm_call_stream` 逐 chunk 推，LLM 经常在
 * 写到一半（开新 `**bold**` 段、或者写 `inline code`）时被 token 上限
 * / 取消信号截断，留下一串未闭合的 `**` 或 `` ` ``。`marked` 配
 * `gfm:true` 对奇数个不闭合的标记不会自动补救，会把 `**` 当字面量
 * 渲染出来（在回复末尾出现光秃秃的星号）。
 *
 * 策略：按出现次数判奇偶，缺一个补一个（补在末尾）。这对绝大多数
 * 教学场景回复够用——LLM 一般不会在中间开 bold/code 写到一半。
 *
 * 只处理 prompt 里明确鼓励的 `**` 与 `` ` ``（见 discussion_service.py
 * system_prompt），避免误伤文本里其它字符。
 */
function closeUnclosedMarkdown(text: string): string {
  if (!text) return text
  let result = text
  const doubleStar = (result.match(/\*\*/g) || []).length
  if (doubleStar % 2 === 1) {
    result += '**'
  }
  const backtick = (result.match(/`/g) || []).length
  if (backtick % 2 === 1) {
    result += '`'
  }
  return result
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  // 把连续多个 \n 折叠成单个 \n，marked 的 breaks:true 会把单 \n 渲染成 <br>
  // — 让 AI 教师整段回复只有一个 <p>，段内换行用 <br>
  const normalized = content.replace(/\n{2,}/g, '\n')
  const closed = closeUnclosedMarkdown(normalized)
  const html = marked.parse(closed, { async: false }) as string
  // marked 输出末尾会带 \n，配合 message-content 的 white-space: pre-wrap
  // 会渲染成一空行，导致 div 高度比 p 多一行。trim 掉两端空白即可。
  return DOMPurify.sanitize(html.trim())
}

function roleLabel(message: ClassroomDiscussionMessage): string {
  if (message.role === 'user') return '我'
  return message.agent_name || 'AI 教师'
}

function onMultiAgentChange(event: Event) {
  const checked = (event.target as HTMLInputElement | null)?.checked ?? false
  emit('update:multi-agent-enabled', checked)
}

function onTextareaKeydown(event: KeyboardEvent) {
  if (!shouldSubmitDiscussionOnEnter({
    key: event.key,
    shiftKey: event.shiftKey,
    isComposing: event.isComposing,
  })) {
    return
  }
  event.preventDefault()
  handleSubmit()
}

function submitDraft(text: string) {
  const content = text.trim()
  if (!content || props.submitting) return
  autoFollow.value = true
  nextTick(() => scrollToBottom('auto'))
  emit('submit', content)
}

defineExpose({ submitDraft })
</script>

<style scoped>
.discussion-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  border-left: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid rgb(var(--line-rgb));
}

.header-actions {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.agent-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 5px 10px 5px 8px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: background 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.agent-toggle input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.agent-toggle-track {
  position: relative;
  width: 30px;
  height: 18px;
  border-radius: 999px;
  background: #d8dee6;
  transition: background 0.18s ease;
}

.agent-toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.22);
  transition: transform 0.18s ease;
}

.agent-toggle:has(input:checked) {
  border-color: rgba(15, 118, 110, 0.22);
  background: rgba(240, 253, 250, 0.88);
  color: #115e59;
}

.agent-toggle:has(input:checked) .agent-toggle-track {
  background: #5daea6;
}

.agent-toggle:has(input:checked) .agent-toggle-thumb {
  transform: translateX(12px);
}

.agent-toggle:has(input:focus-visible) {
  outline: 2px solid rgba(15, 118, 110, 0.28);
  outline-offset: 2px;
}

.agent-toggle:has(input:disabled) {
  opacity: 0.6;
  cursor: not-allowed;
}

.sidebar-kicker {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.sidebar-title {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}

.pause-badge {
  align-self: flex-start;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
  font-size: 12px;
  white-space: nowrap;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  padding: 16px;
  border: 1px dashed rgb(var(--line-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
  line-height: 1.6;
}

.empty-state p {
  margin: 0 0 6px;
}

.empty-state p:last-child {
  margin-bottom: 0;
}

.message-card {
  padding: 12px 14px;
  border-radius: 12px;
  line-height: 1.7;
}

.message-card.assistant {
  background: rgb(var(--bg-base-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-left: 4px solid #8aa3bf;
}

.message-card.student_peer {
  background: rgb(var(--bg-base-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-left: 4px solid #9bb89c;
}

.message-card.pending {
  border-style: dashed;
}

.message-card.user {
  background: #f8f4ee;
  border: 1px solid #eadfce;
  border-left: 4px solid #d9b26f;
}

.message-role {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--ink-2-rgb));
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  color: rgb(var(--ink-1-rgb));
  font-size: 14px;
  line-height: 1.4;
}

.message-content :deep(p) {
  margin: 0 0 2px;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(strong) {
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}

.message-content :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.92em;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

.message-content :deep(pre) {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgb(var(--bg-subtle-rgb));
  border: 1px solid rgb(var(--line-rgb));
  overflow-x: auto;
  margin: 6px 0;
}

.message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 2px 0;
  padding-left: 22px;
}

.message-content :deep(li) {
  margin: 0;
}

.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3) {
  font-family: var(--font-display);
  font-weight: 600;
  margin: 8px 0 4px;
}

.message-content :deep(blockquote) {
  margin: 6px 0;
  padding: 6px 12px;
  border-left: 3px solid rgb(var(--line-strong-rgb));
  color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-base-rgb));
  border-radius: 0 6px 6px 0;
}

.thinking-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgb(var(--ink-2-rgb));
  font-size: 14px;
}

.thinking-label {
  white-space: nowrap;
}

.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.thinking-dots i {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: rgb(var(--ink-2-rgb));
  opacity: 0.25;
  animation: thinkingPulse 1.2s ease-in-out infinite;
}

.thinking-dots i:nth-child(2) {
  animation-delay: 0.18s;
}

.thinking-dots i:nth-child(3) {
  animation-delay: 0.36s;
}

@keyframes thinkingPulse {
  0%, 80%, 100% {
    opacity: 0.2;
    transform: translateY(0);
  }
  40% {
    opacity: 0.9;
    transform: translateY(-2px);
  }
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
}

.quick-btn {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-base-rgb));
  padding: 10px 8px;
  font-size: 12px;
  cursor: pointer;
}

.quick-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-area {
  border-top: 1px solid rgb(var(--line-rgb));
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.question-input {
  width: 100%;
  resize: vertical;
  border-radius: 12px;
  border: 1px solid rgb(var(--line-rgb));
  padding: 12px;
  font: inherit;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-1-rgb));
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.submit-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.clear-btn {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-2-rgb));
  min-width: 56px;
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.clear-btn:hover:not(:disabled) {
  border-color: rgb(var(--line-strong-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.submit-btn {
  border: none;
  border-radius: 10px;
  background: rgb(var(--ink-1-rgb));
  color: white;
  min-width: 76px;
  padding: 10px 16px;
  font-size: 13px;
  cursor: pointer;
}

.submit-btn:disabled,
.clear-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
