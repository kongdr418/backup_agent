<template>
  <aside class="discussion-sidebar">
    <div class="sidebar-header">
      <div>
        <div class="sidebar-kicker">课堂讨论</div>
        <div class="sidebar-title">正在讨论本课内容</div>
      </div>
      <span v-if="autoAdvancePaused" class="pause-badge">自动翻页已暂停</span>
    </div>

    <div class="message-list">
      <div v-if="!messages.length" class="empty-state">
        <p>你可以随时追问这一课已经讲过的内容。</p>
        <p>我会尽量用提示、追问和例子来带你想清楚。</p>
      </div>

      <article
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}`"
        class="message-card"
        :class="message.role"
      >
        <div class="message-role">{{ message.role === 'assistant' ? 'AI 教师' : '我' }}</div>
        <div class="message-content">{{ message.content }}</div>
      </article>

      <article v-if="submitting" class="message-card assistant pending">
        <div class="message-role">AI 教师</div>
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

    <form class="input-area" @submit.prevent="submit">
      <textarea
        v-model="draft"
        class="question-input"
        :disabled="submitting"
        rows="4"
        placeholder="输入你的问题，比如：这页为什么要先判断条件？"
        @keydown="onTextareaKeydown"
      />
      <button type="submit" class="submit-btn" :disabled="submitting || !draft.trim()">
        {{ submitting ? '思考中...' : '发送问题' }}
      </button>
    </form>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ClassroomDiscussionMessage } from '@/api/interactiveClassroom'
import { shouldSubmitDiscussionOnEnter } from '@/utils/discussionInput'

const props = defineProps<{
  messages: ClassroomDiscussionMessage[]
  submitting?: boolean
  autoAdvancePaused?: boolean
}>()

const emit = defineEmits<{
  submit: [content: string]
  'quick-action': [action: string]
}>()

const draft = ref('')
const quickActions = ['换个例子', '再提示一点', '总结一下']

function submit() {
  const content = draft.value.trim()
  if (!content || props.submitting) return
  emit('submit', content)
  draft.value = ''
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
  submit()
}
</script>

<style scoped>
.discussion-sidebar {
  display: flex;
  flex-direction: column;
  min-width: 0;
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
}

.message-card.pending {
  border-style: dashed;
}

.message-card.user {
  background: rgba(15, 23, 42, 0.06);
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
  padding: 0 16px 16px;
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

.submit-btn {
  align-self: flex-end;
  border: none;
  border-radius: 10px;
  background: rgb(var(--ink-1-rgb));
  color: white;
  padding: 10px 16px;
  font-size: 13px;
  cursor: pointer;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
