<template>
  <div class="preview-wrap">
    <!-- Top progress when not idle -->
    <ProgressBar
      v-if="status !== 'idle'"
      class="preview-progress"
      :status="status"
      :stage="stage"
      :message="message"
      :progress="progress"
      :total-slides="totalSlides"
      :done-slides="doneSlides"
    />

    <!-- Main preview / empty -->
    <div class="preview-main">
      <EmptyState
        v-if="status === 'idle' && slides.length === 0"
        :icon="Presentation"
        title="PPT 工作台"
        description="左侧填写主题与参数，点击「开始生成」启动多 Agent 流水线；每页 SVG 会在生成完后立即显示在此处。"
      />

      <SvgCarousel
        v-else
        :slides="slides"
        :active-idx="activeIdx"
        @select="$emit('select-slide', $event)"
      />
    </div>

    <!-- Action bar -->
    <div
      v-if="status === 'done' || status === 'error' || status === 'cancelled'"
      class="preview-action"
    >
      <div class="action-info">
        <span v-if="status === 'done'">
          <span class="status-done">生成完成</span>
          <span v-if="finishedAt && startedAt" class="meta-text">
            · 用时 {{ duration }}
          </span>
          <span v-if="pptxFilename" class="meta-text truncate">
            · {{ pptxFilename }}
          </span>
        </span>
        <span v-else-if="status === 'error'" class="status-error">{{ message || '生成失败' }}</span>
        <span v-else class="meta-text">已取消</span>
      </div>
      <div class="action-btns">
        <button
          v-if="canDownload"
          class="download-btn"
          @click="$emit('download')"
        >
          <Download class="w-3.5 h-3.5" />
          下载 PPTX
        </button>
        <button
          class="reset-btn"
          @click="$emit('reset')"
        >
          <RotateCcw class="w-3.5 h-3.5" />
          重置
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Presentation, Download, RotateCcw } from 'lucide-vue-next'
import EmptyState from '@/components/common/EmptyState.vue'
import ProgressBar from './ProgressBar.vue'
import SvgCarousel from './SvgCarousel.vue'
import type { PptSlide } from '@/types'

const props = defineProps<{
  status: 'idle' | 'streaming' | 'done' | 'error' | 'cancelled'
  stage: string
  message: string
  progress: number
  slides: PptSlide[]
  activeIdx: number
  totalSlides?: number
  pptxFilename?: string
  canDownload: boolean
  startedAt?: number
  finishedAt?: number
}>()

defineEmits<{
  download: []
  reset: []
  'select-slide': [idx: number]
}>()

const doneSlides = computed(() => props.slides.length)

const duration = computed(() => {
  if (!props.startedAt || !props.finishedAt) return ''
  const ms = props.finishedAt - props.startedAt
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
})
</script>

<style scoped>
.preview-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.preview-progress {
  flex-shrink: 0;
  margin: 16px 24px 0;
}
.preview-main {
  flex: 1;
  min-height: 0;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 24px 16px;
  padding: 10px 16px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  gap: 12px;
}

.action-info {
  font-size: 12px;
  truncate: true;
  min-width: 0;
  flex: 1;
}

.status-done {
  color: rgb(var(--ink-1-rgb));
  font-weight: 500;
}

.status-error {
  color: rgb(var(--danger-rgb));
}

.meta-text {
  color: rgb(var(--ink-3-rgb));
}

.action-btns {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px;
  height: 32px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  border: none;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  cursor: pointer;
  transition: all 150ms ease;
}

.download-btn:hover {
  background: rgb(var(--ink-2-rgb));
}

.reset-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  height: 32px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  cursor: pointer;
  transition: all 150ms ease;
}

.reset-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  border-color: rgb(var(--line-strong-rgb));
  color: rgb(var(--ink-1-rgb));
}
</style>
