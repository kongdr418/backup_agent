<template>
  <div class="ppt-studio-root h-full flex">
    <!-- Mobile: overlay backdrop -->
    <div class="ppt-overlay" :class="{ open: drawerOpen }" @click="drawerOpen = false" />

    <!-- Mobile: slide-in drawer -->
    <div class="ppt-drawer" :class="{ open: drawerOpen }">
      <div class="ppt-drawer-header">
        <span class="ppt-drawer-title">参数设置</span>
        <button class="ppt-drawer-close" @click="drawerOpen = false">
          <X class="w-4 h-4" />
        </button>
      </div>
      <div class="ppt-drawer-body">
        <ParamPanel
          v-model="store.params"
          :disabled="store.isGenerating"
          @generate="onGenerate(); drawerOpen = false"
          @cancel="store.cancel()"
        />
      </div>
    </div>

    <!-- Param panel (desktop) -->
    <div class="ppt-param-desktop w-[340px] shrink-0 h-full">
      <ParamPanel
        v-model="store.params"
        :disabled="store.isGenerating"
        @generate="onGenerate"
        @cancel="store.cancel()"
      />
    </div>

    <!-- Preview area -->
    <div class="flex-1 min-w-0 flex flex-col">
      <!-- Toolbar -->
      <div
        class="h-12 shrink-0 px-5 border-b border-line bg-bg-surface flex items-center justify-between"
      >
        <div class="flex items-center gap-2 text-[13px] text-ink-2">
          <Wand2 class="w-3.5 h-3.5 text-ink-3" />
          <span class="hidden md:inline">多 Agent SVG 流水线</span>
          <button
            class="ppt-mobile-param-btn md:hidden inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12.5px] text-ink-2 border border-line active:bg-bg-subtle transition-colors"
            @click="drawerOpen = true"
          >
            <SlidersHorizontal class="w-3.5 h-3.5" />
            参数
          </button>
          <StatusPill :tone="statusTone">{{ statusText }}</StatusPill>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="h-8 px-2.5 rounded-md text-[12.5px] text-ink-2 border border-line hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
            @click="openHistory"
          >
            <History class="w-3.5 h-3.5" />
            <span class="hidden md:inline">历史</span>
            <span v-if="store.jobs.length" class="text-ink-3">({{ store.jobs.length }})</span>
          </button>
        </div>
      </div>

      <PreviewStage
        :status="store.gen.status"
        :stage="store.gen.stage"
        :message="store.gen.message"
        :progress="store.gen.progress"
        :slides="store.gen.slides"
        :active-idx="activeIdx"
        :total-slides="store.gen.totalSlides"
        :pptx-filename="store.gen.pptxFilename"
        :can-download="store.canDownload"
        :started-at="store.gen.startedAt"
        :finished-at="store.gen.finishedAt"
        @select-slide="(i) => (activeIdx = i)"
        @download="onDownload"
        @reset="onReset"
      />
    </div>

    <HistoryDrawer
      v-model:show="historyOpen"
      :jobs="store.jobs"
      :loading="store.jobsLoading"
      @open="onOpenJob"
      @delete="onDeleteJob"
      @clear-all="onClearAllJobs"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Wand2, History, SlidersHorizontal, X } from 'lucide-vue-next'
import { useMessage, useDialog } from 'naive-ui'

import ParamPanel from '@/components/ppt/ParamPanel.vue'
import PreviewStage from '@/components/ppt/PreviewStage.vue'
import HistoryDrawer from '@/components/ppt/HistoryDrawer.vue'
import StatusPill from '@/components/common/StatusPill.vue'

import { usePptStore } from '@/stores/pptStore'
import { usePptStream } from '@/composables/usePptStream'
import { getPptAllSlides, pptDownloadUrl } from '@/api/pptSvg'

const store = usePptStore()
const { generate } = usePptStream()
const message = useMessage()
const dialog = useDialog()

const activeIdx = ref(0)
const historyOpen = ref(false)
const drawerOpen = ref(false)

// keep active idx valid when slides arrive
watch(
  () => store.gen.slides.length,
  (n) => {
    if (activeIdx.value >= n) activeIdx.value = Math.max(0, n - 1)
  },
)

// Auto-jump to latest slide while streaming
watch(
  () => store.gen.slides.length,
  (n, oldN) => {
    if (store.gen.status === 'streaming' && n > (oldN || 0)) {
      activeIdx.value = n - 1
    }
  },
)

onMounted(() => {
  store.refreshJobs().catch(() => undefined)
})

const statusTone = computed<'neutral' | 'success' | 'warning' | 'danger'>(() => {
  switch (store.gen.status) {
    case 'streaming':
      return 'warning'
    case 'done':
      return 'success'
    case 'error':
      return 'danger'
    default:
      return 'neutral'
  }
})

const statusText = computed(() => {
  switch (store.gen.status) {
    case 'streaming':
      return '生成中'
    case 'done':
      return '已完成'
    case 'error':
      return '失败'
    case 'cancelled':
      return '已取消'
    default:
      return '空闲'
  }
})

async function onGenerate() {
  if (!store.params.topic?.trim()) {
    message.warning('请填写课程主题')
    return
  }
  activeIdx.value = 0
  try {
    await generate({ ...store.params })
    if (store.gen.status === 'done') {
      message.success('PPT 生成完成')
    } else if (store.gen.status === 'error') {
      message.error(store.gen.message || '生成失败')
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : String(e))
  }
}

function onDownload() {
  if (!store.gen.jobId) return
  const url = pptDownloadUrl(store.gen.jobId)
  window.open(url, '_blank', 'noopener')
}

function onReset() {
  store.resetGen()
  activeIdx.value = 0
}

async function openHistory() {
  historyOpen.value = true
  if (store.jobs.length === 0) {
    await store.refreshJobs().catch(() => undefined)
  }
}

async function onOpenJob(jobId: string) {
  try {
    const data = await getPptAllSlides(jobId)
    store.gen.slides = data.slides.map((s) => ({ page: s.page, svg: s.svg }))
    store.gen.jobId = jobId
    store.gen.status = 'done'
    store.gen.message = '历史回看'
    store.gen.progress = 100
    store.gen.totalSlides = data.total_pages
    activeIdx.value = 0
    historyOpen.value = false
    message.success(`已加载 ${data.total_pages} 页`)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '加载失败')
  }
}

async function onDeleteJob(jobId: string) {
  try {
    await store.deleteJob(jobId)
    message.success('已删除')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '删除失败')
  }
}

function onClearAllJobs() {
  dialog.warning({
    title: '清空全部',
    content: '将删除全部 SVG PPT 历史，操作不可恢复。',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await store.clearAllJobs()
        message.success('已清空')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}
</script>

<style scoped>
/* Mobile drawer elements — hidden on desktop */
@media (min-width: 768px) {
  .ppt-overlay,
  .ppt-drawer,
  .ppt-mobile-param-btn {
    display: none !important;
  }
}

@media (max-width: 767px) {
  .ppt-param-desktop {
    display: none !important;
  }

  /* Overlay backdrop */
  .ppt-overlay {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 70;
    background: rgb(0 0 0 / 0.35);
    backdrop-filter: blur(2px);
    opacity: 0;
    pointer-events: none;
    transition: opacity 250ms ease;
  }
  .ppt-overlay.open {
    opacity: 1;
    pointer-events: auto;
  }

  /* Slide-in drawer */
  .ppt-drawer {
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: min(300px, 85vw);
    z-index: 80;
    background: var(--bg-surface);
    box-shadow: 4px 0 32px rgb(0 0 0 / 0.15);
    transform: translateX(-100%);
    transition: transform 300ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .ppt-drawer.open {
    transform: translateX(0);
  }

  .ppt-drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--line);
    flex-shrink: 0;
  }

  .ppt-drawer-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--ink-primary);
  }

  .ppt-drawer-close {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: transparent;
    color: var(--ink-secondary);
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .ppt-drawer-close:active {
    background: var(--bg-subtle);
  }

  .ppt-drawer-body {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }
}
</style>
