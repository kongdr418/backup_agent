<template>
  <div class="h-full flex flex-col">
    <PageHeader
      title="文件库"
      description="管理所有 AI 生成的文件 — PPT / 讲义 / 习题 / 卡片 / 图片 / 音频"
    >
      <template #actions>
        <n-button quaternary size="small" @click="refresh">
          <RefreshCw class="w-3.5 h-3.5 mr-1" />
          刷新
        </n-button>
        <n-button
          v-if="allFiles.length > 0"
          quaternary
          type="error"
          size="small"
          @click="askClearAll"
        >
          <Trash2 class="w-3.5 h-3.5 mr-1" />
          清空全部
        </n-button>
      </template>
    </PageHeader>

    <div class="px-6 py-3 border-b border-line bg-bg-surface shrink-0 overflow-x-auto">
      <div class="flex gap-1.5 min-w-max">
        <button
          v-for="cat in categories"
          :key="cat.value"
          class="px-3 h-7 rounded-full text-[12.5px] transition-colors whitespace-nowrap"
          :class="
            activeCat === cat.value
              ? 'bg-accent text-white'
              : 'bg-bg-base text-ink-2 hover:bg-bg-subtle border border-line'
          "
          @click="activeCat = cat.value"
        >
          {{ cat.label }}
          <span class="ml-1 opacity-70">({{ countByCat(cat.value) }})</span>
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto p-6">
      <div v-if="loading" class="text-center text-[12px] text-ink-3 py-12">加载中...</div>

      <EmptyState
        v-else-if="filtered.length === 0"
        :icon="FolderOpen"
        title="暂无文件"
        description="生成内容后会出现在这里"
      />

      <FileGrid
        v-else
        :files="filtered"
        @open="onOpen"
        @delete="askDelete"
        @rename="startRename"
      />
    </div>

    <PreviewDrawer v-model:show="previewOpen" :file="previewFile" />

    <n-modal
      v-model:show="renameShow"
      preset="dialog"
      title="重命名文件"
      positive-text="确认"
      negative-text="取消"
      @positive-click="confirmRename"
    >
      <n-input v-model:value="renameValue" placeholder="新文件名" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NModal, NInput, useDialog, useMessage } from 'naive-ui'
import { FolderOpen, RefreshCw, Trash2 } from 'lucide-vue-next'

import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import FileGrid from '@/components/library/FileGrid.vue'
import PreviewDrawer from '@/components/library/PreviewDrawer.vue'

import type { GeneratedFile } from '@/types'
import { useFileStore } from '@/stores/fileStore'
import { deletePptJob } from '@/api/pptSvg'

const route = useRoute()
const fileStore = useFileStore()
const dialog = useDialog()
const message = useMessage()

const loading = ref(false)

const allFiles = computed<GeneratedFile[]>(() => fileStore.files)

const categories = [
  { value: 'all', label: '全部' },
  { value: 'ppt', label: 'PPT' },
  { value: 'video', label: '微课视频' },
  { value: 'lecture', label: '讲义' },
  { value: 'outline', label: '课程大纲' },
  { value: 'speech', label: '讲稿' },
  { value: 'exercise', label: '习题集' },
  { value: 'quiz', label: '课堂测验' },
  { value: 'card', label: '知识卡片' },
  { value: 'mindmap', label: '思维导图' },
  { value: 'content_text', label: '文案' },
  { value: 'content_audio', label: '音频' },
  { value: 'content_image', label: '图片' },
]

const activeCat = ref('all')

const filtered = computed(() => {
  if (activeCat.value === 'all') return allFiles.value
  return allFiles.value.filter((f) => f.type === activeCat.value)
})

function countByCat(v: string) {
  if (v === 'all') return allFiles.value.length
  return allFiles.value.filter((f) => f.type === v).length
}

const previewOpen = ref(false)
const previewFile = ref<GeneratedFile | null>(null)

function onOpen(f: GeneratedFile) {
  previewFile.value = f
  previewOpen.value = true
}

const renameShow = ref(false)
const renameValue = ref('')
const renameTarget = ref<GeneratedFile | null>(null)

function startRename(f: GeneratedFile) {
  renameTarget.value = f
  renameValue.value = f.name
  renameShow.value = true
}

async function confirmRename() {
  if (!renameTarget.value) return
  const v = renameValue.value.trim()
  if (!v) return
  try {
    await fileStore.renameFile(renameTarget.value.path, v)
    message.success('重命名成功')
  } catch (e) {
    message.error(e instanceof Error ? e.message : '重命名失败')
  }
  renameShow.value = false
}

function askDelete(f: GeneratedFile) {
  dialog.warning({
    title: '删除文件',
    content: `确定删除「${f.name}」?该操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        if (f.id.startsWith('svg_ppt_')) {
          const jobId = f.id.replace(/^svg_ppt_/, '')
          await deletePptJob(jobId)
          fileStore.files = fileStore.files.filter((x) => x.id !== f.id)
        } else {
          await fileStore.deleteFile(f.path)
        }
        message.success('已删除')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

function askClearAll() {
  dialog.warning({
    title: '清空全部',
    content: '将删除全部生成的文件（含微课视频），操作不可恢复。',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await fileStore.clearAllFiles()
        message.success('已清空')
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}

async function refresh() {
  loading.value = true
  try {
    await fileStore.fetchFiles()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await refresh()
  const openId = route.query.open as string
  if (openId) {
    const file = allFiles.value.find((f) => f.id === openId)
    if (file) onOpen(file)
  }
})
</script>
