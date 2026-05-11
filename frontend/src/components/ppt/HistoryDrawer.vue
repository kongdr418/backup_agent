<template>
  <n-drawer v-model:show="visible" :width="420" placement="right">
    <n-drawer-content title="历史记录" closable>
      <div class="space-y-2">
        <div v-if="loading" class="text-center text-[12px] text-ink-3 py-6">
          加载中...
        </div>

        <div
          v-else-if="jobs.length === 0"
          class="text-center text-[12px] text-ink-3 py-10"
        >
          <FolderOpen class="w-6 h-6 mx-auto mb-2 text-ink-4" />
          暂无历史
        </div>

        <button
          v-for="job in jobs"
          :key="job.job_id"
          class="w-full text-left p-3 rounded-lg border border-line bg-bg-surface hover:border-ink-4 hover:bg-bg-subtle/50 transition-all"
          @click="$emit('open', job.job_id)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="text-[13px] font-medium text-ink-1 truncate">{{ job.topic || '未命名' }}</div>
              <div class="flex items-center gap-2 mt-1 text-[11px] text-ink-3">
                <span>{{ job.created_at }}</span>
                <span v-if="job.num_slides">· {{ job.num_slides }} 页</span>
                <span v-if="job.style">· {{ job.style }}</span>
              </div>
              <div class="mt-1.5 text-[10.5px] text-ink-4 font-mono truncate">{{ job.job_id }}</div>
            </div>
            <div class="shrink-0 flex items-center gap-1">
              <a
                v-if="job.has_pptx"
                :href="downloadUrl(job.job_id)"
                :download="job.pptx_filename"
                target="_blank"
                rel="noopener"
                class="px-2 h-7 rounded-md text-[11px] border border-line text-ink-2 hover:bg-bg-base inline-flex items-center gap-1 transition-colors"
                @click.stop
              >
                <Download class="w-3 h-3" />
                下载
              </a>
              <button
                class="w-7 h-7 rounded-md border border-line text-ink-3 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 inline-flex items-center justify-center transition-colors"
                title="删除"
                @click.stop="$emit('delete', job.job_id)"
              >
                <Trash2 class="w-3 h-3" />
              </button>
            </div>
          </div>
        </button>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NDrawer, NDrawerContent } from 'naive-ui'
import { FolderOpen, Download, Trash2 } from 'lucide-vue-next'
import type { PptJob } from '@/types'
import { pptDownloadUrl } from '@/api/pptSvg'

const props = defineProps<{
  show: boolean
  jobs: PptJob[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:show': [v: boolean]
  open: [jobId: string]
  delete: [jobId: string]
}>()

const visible = computed({
  get: () => props.show,
  set: (v: boolean) => emit('update:show', v),
})

function downloadUrl(jobId: string) {
  return pptDownloadUrl(jobId)
}
</script>
