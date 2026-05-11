<template>
  <div class="h-full flex">
    <!-- Param panel (left) -->
    <div class="w-[340px] shrink-0 h-full">
      <ParamPanel
        v-model="store.params"
        :disabled="store.isGenerating"
        @generate="onGenerate"
        @cancel="store.cancel()"
      />
    </div>

    <!-- Preview area (right) -->
    <div class="flex-1 min-w-0 flex flex-col">
      <!-- Toolbar -->
      <div
        class="h-12 shrink-0 px-5 border-b border-line bg-bg-surface flex items-center justify-between"
      >
        <div class="flex items-center gap-2 text-[13px] text-ink-2">
          <Wand2 class="w-3.5 h-3.5 text-ink-3" />
          <span>多 Agent SVG 流水线</span>
          <StatusPill :tone="statusTone">{{ statusText }}</StatusPill>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="h-8 px-2.5 rounded-md text-[12.5px] text-ink-2 border border-line hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
            @click="openHistory"
          >
            <History class="w-3.5 h-3.5" />
            历史
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
import { Wand2, History } from 'lucide-vue-next'
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
