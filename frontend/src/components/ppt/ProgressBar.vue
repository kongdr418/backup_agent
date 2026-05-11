<template>
  <div class="progress-bar">
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <component :is="stageIcon" class="w-3.5 h-3.5" :class="stageIconCls" />
        <span class="text-[13px] font-medium text-ink-1">{{ stageLabel }}</span>
      </div>
      <span class="text-[12px] text-ink-3 tabular-nums">{{ Math.round(progress) }}%</span>
    </div>

    <!-- Bar -->
    <div class="h-1.5 bg-bg-subtle rounded-full overflow-hidden mb-2">
      <div
        class="h-full transition-all duration-300 rounded-full"
        :class="barCls"
        :style="{ width: `${Math.max(2, Math.min(progress, 100))}%` }"
      />
    </div>

    <!-- Message + page count -->
    <div class="flex items-center justify-between text-[11.5px] text-ink-3 mb-2.5">
      <span class="truncate flex-1">{{ message || '准备中...' }}</span>
      <span v-if="totalSlides" class="ml-3 shrink-0 tabular-nums">{{ doneSlides }} / {{ totalSlides }} 页</span>
    </div>

    <!-- Stage timeline — single row: dots + labels -->
    <div class="stage-row">
      <template v-for="(s, i) in stages" :key="s.key">
        <div class="stage-dot" :class="stageDotCls(s.key)" />
        <span class="stage-label" :class="stageLabelCls(s.key)">{{ s.label }}</span>
        <div v-if="i < stages.length - 1" class="stage-line" :class="stageLineCls(i)" />
      </template>
    </div>

    <div
      v-if="status === 'streaming' && stage === 'svg_generation' && (doneSlides || 0) > 0"
      class="mt-2 text-[10.5px] text-ink-4"
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
  if (props.status === 'error') return 'text-rose-500'
  if (props.status === 'cancelled') return 'text-ink-3'
  if (props.status === 'done') return 'text-emerald-500'
  return 'text-brand animate-spin'
})

const barCls = computed(() => {
  if (props.status === 'error') return 'bg-rose-400'
  if (props.status === 'cancelled') return 'bg-ink-3'
  if (props.status === 'done') return 'bg-emerald-500'
  return 'bg-brand'
})
</script>

<style scoped>
.progress-bar {
  padding: 12px 16px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
}

/* Stage timeline */
.stage-row {
  display: flex;
  align-items: center;
  gap: 0;
}
.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 200ms ease;
}
.dot-active {
  background: rgb(var(--accent-rgb));
  box-shadow: 0 0 0 3px rgb(var(--accent-rgb) / 0.2);
}
.dot-done {
  background: rgb(var(--emerald-500, #10b981));
}
.dot-error {
  background: rgb(var(--rose-400, #fb7185));
}
.dot-pending {
  background: rgb(var(--bg-subtle-rgb));
  border: 1.5px solid rgb(var(--line-rgb));
}
.stage-label {
  font-size: 10px;
  color: rgb(var(--ink-4-rgb));
  white-space: nowrap;
  margin: 0 4px;
}
.stage-label.label-active {
  color: rgb(var(--ink-1-rgb));
  font-weight: 500;
}
.stage-label.label-done {
  color: rgb(var(--ink-2-rgb));
}
.stage-line {
  flex: 1;
  height: 1.5px;
  background: rgb(var(--line-rgb));
  margin: 0 2px;
  border-radius: 1px;
  transition: background 200ms ease;
}
.line-done {
  background: rgb(var(--emerald-500, #10b981));
}
</style>
