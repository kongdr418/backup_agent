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
        description="左侧填写主题与参数,点击「开始生成」启动多 Agent 流水线;每页 SVG 会在生成完后立即显示在此处。"
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
      <div class="text-[12px] text-ink-3 truncate">
        <span v-if="status === 'done'">
          ✓ 生成完成
          <span v-if="finishedAt && startedAt">
            · 用时 {{ duration }}
          </span>
          <span v-if="pptxFilename" class="ml-1.5 text-ink-4 truncate">
            · {{ pptxFilename }}
          </span>
        </span>
        <span v-else-if="status === 'error'" class="text-rose-600">{{ message || '生成失败' }}</span>
        <span v-else>已取消</span>
      </div>
      <div class="flex items-center gap-2 shrink-0 ml-3">
        <button
          v-if="canDownload"
          class="px-3 h-7 rounded-md text-[12px] bg-brand text-white hover:bg-brand-hover inline-flex items-center gap-1.5 transition-colors"
          @click="$emit('download')"
        >
          <Download class="w-3.5 h-3.5" />
          下载 PPTX
        </button>
        <button
          class="px-3 h-7 rounded-md text-[12px] border border-line text-ink-2 hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
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
  margin: 16px 20px 0;
}
.preview-main {
  flex: 1;
  min-height: 0;
  padding: 12px 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 20px 16px;
  padding: 10px 16px;
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
}
</style>
