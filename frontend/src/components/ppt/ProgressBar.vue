<template>
  <div class="progress-bar">
    <div class="progress-header">
      <div class="progress-status">
        <component :is="stageIcon" class="status-icon" :class="stageIconCls" />
        <span class="status-label">{{ stageLabel }}</span>
      </div>
      <span class="progress-pct">{{ Math.round(progress) }}%</span>
    </div>

    <!-- Bar -->
    <div class="progress-track">
      <div
        class="progress-fill"
        :class="barCls"
        :style="{ width: `${Math.max(2, Math.min(progress, 100))}%` }"
      />
    </div>

    <!-- Message + page count -->
    <div class="progress-meta">
      <span class="meta-message">{{ message || '准备中...' }}</span>
      <span v-if="totalSlides" class="meta-count">{{ doneSlides }} / {{ totalSlides }} 页</span>
    </div>

    <!-- Stage timeline -->
    <div class="stage-row">
      <template v-for="(s, i) in stages" :key="s.key">
        <div class="stage-dot" :class="stageDotCls(s.key)" />
        <span class="stage-label" :class="stageLabelCls(s.key)">{{ s.label }}</span>
        <div v-if="i < stages.length - 1" class="stage-line" :class="stageLineCls(i)" />
      </template>
    </div>

    <div
      v-if="status === 'streaming' && stage === 'svg_generation' && (doneSlides || 0) > 0"
      class="stage-hint"
    >
      页面并发生成，预览顺序可能与页码不一致
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, CircleAlert, CircleCheck, CircleX } from 'lucide-vue-next'

const props = defineProps<{
  status: 'idle' | 'streaming' | 'done' | 'error' | 'cancelled'
  stage: string
  message: string
  progress: number
  totalSlides?: number
  doneSlides?: number
}>()

const stages = [
  { key: 'content_planning', label: '规划' },
  { key: 'design', label: '设计规范' },
  { key: 'svg_generation', label: '逐页 SVG' },
  { key: 'export', label: '转换 PPTX' },
]

const stageIdx = computed(() => stages.findIndex((s) => s.key === props.stage))

function stageDotCls(key: string) {
  const idx = stages.findIndex((s) => s.key === key)
  if (props.status === 'error') return idx <= stageIdx.value ? 'dot-error' : 'dot-pending'
  if (props.status === 'done') return 'dot-done'
  if (idx < stageIdx.value) return 'dot-done'
  if (idx === stageIdx.value) return 'dot-active'
  return 'dot-pending'
}

function stageLabelCls(key: string) {
  const idx = stages.findIndex((s) => s.key === key)
  if (props.status === 'done') return 'label-done'
  if (idx <= stageIdx.value) return 'label-active'
  return ''
}

function stageLineCls(idx: number) {
  if (props.status === 'done') return 'line-done'
  if (idx < stageIdx.value) return 'line-done'
  return ''
}

const stageLabel = computed(() => {
  if (props.status === 'error') return '出错了'
  if (props.status === 'cancelled') return '已取消'
  if (props.status === 'done') return '生成完成'
  const found = stages.find((s) => s.key === props.stage)
  return found ? `${found.label}中` : '处理中'
})

const stageIcon = computed(() => {
  if (props.status === 'error') return CircleAlert
  if (props.status === 'cancelled') return CircleX
  if (props.status === 'done') return CircleCheck
  return Loader2
})

const stageIconCls = computed(() => {
  if (props.status === 'error') return 'icon-error'
  if (props.status === 'cancelled') return 'icon-neutral'
  if (props.status === 'done') return 'icon-done'
  return 'icon-active'
})

const barCls = computed(() => {
  if (props.status === 'error') return 'fill-error'
  if (props.status === 'cancelled') return 'fill-neutral'
  if (props.status === 'done') return 'fill-done'
  return 'fill-active'
})
</script>

<style scoped>
.progress-bar {
  padding: 14px 18px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.progress-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.icon-error {
  color: rgb(var(--danger-rgb));
}

.icon-neutral {
  color: rgb(var(--ink-3-rgb));
}

.icon-done {
  color: rgb(var(--success-rgb));
}

.icon-active {
  color: rgb(var(--ink-1-rgb));
  animation: spin 1s linear infinite;
}

.status-label {
  font-size: 13px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
}

.progress-pct {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  font-variant-numeric: tabular-nums;
}

.progress-track {
  height: 3px;
  background: rgb(var(--bg-subtle-rgb));
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 300ms ease;
}

.fill-error {
  background: rgb(var(--danger-rgb));
}

.fill-neutral {
  background: rgb(var(--ink-3-rgb));
}

.fill-done {
  background: rgb(var(--ink-1-rgb));
}

.fill-active {
  background: rgb(var(--ink-1-rgb));
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  margin-bottom: 12px;
}

.meta-message {
  color: rgb(var(--ink-3-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.meta-count {
  color: rgb(var(--ink-3-rgb));
  margin-left: 12px;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

/* Stage timeline */
.stage-row {
  display: flex;
  align-items: center;
  gap: 0;
}

.stage-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 200ms ease;
}

.dot-active {
  background: rgb(var(--ink-1-rgb));
}

.dot-done {
  background: rgb(var(--ink-1-rgb));
}

.dot-error {
  background: rgb(var(--danger-rgb));
}

.dot-pending {
  background: rgb(var(--bg-subtle-rgb));
  border: 1.5px solid rgb(var(--line-rgb));
  width: 6px;
  height: 6px;
}

.stage-label {
  font-size: 10px;
  color: rgb(var(--ink-4-rgb));
  white-space: nowrap;
  margin: 0 4px;
}

.stage-label.label-active {
  color: rgb(var(--ink-2-rgb));
  font-weight: 500;
}

.stage-label.label-done {
  color: rgb(var(--ink-2-rgb));
}

.stage-line {
  flex: 1;
  height: 1px;
  background: rgb(var(--line-rgb));
  margin: 0 2px;
  border-radius: 1px;
  transition: background 200ms ease;
}

.line-done {
  background: rgb(var(--ink-2-rgb));
}

.stage-hint {
  margin-top: 8px;
  font-size: 10.5px;
  color: rgb(var(--ink-4-rgb));
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
