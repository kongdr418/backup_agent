<template>
  <div class="h-full flex">
    <!-- Param panel (left) -->
    <div class="w-[340px] shrink-0 h-full border-r border-line bg-bg-surface flex flex-col">
      <div class="h-12 shrink-0 px-4 flex items-center gap-2 border-b border-line">
        <Video class="w-3.5 h-3.5 text-ink-3" />
        <span class="text-[13px] font-medium text-ink-1">微课视频生成</span>
      </div>

      <div class="flex-1 overflow-auto p-4">
        <!-- Upload PPT -->
        <div class="mb-5">
          <label class="block text-[12.5px] text-ink-2 mb-2">上传 PPT</label>
          <NUpload
            ref="uploadRef"
            :max="1"
            accept=".pptx"
            :show-file-list="false"
            @change="onUploadChange"
          >
            <NButton block>选择 PPTX 文件</NButton>
          </NUpload>
          <div v-if="uploadFile" class="mt-2 flex items-center gap-2">
            <span class="text-[12px] text-ink-2 truncate flex-1">{{ uploadFile.name }}</span>
            <button
              class="shrink-0 text-ink-3 hover:text-ink-1 transition-colors"
              title="清除"
              @click="clearFile"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <!-- Voice selection -->
        <div class="mb-5">
          <label class="block text-[12.5px] text-ink-2 mb-2">音色选择</label>
          <NSelect
            v-model:value="selectedVoice"
            :options="voiceOptions"
            placeholder="选择音色"
          />
        </div>

        <!-- Generate button -->
        <NButton
          color="#000000"
          text-color="#ffffff"
          :disabled="!uploadFile || generating"
          :loading="generating"
          block
          @click="onGenerate"
        >
          <template #icon>
            <Video class="w-4 h-4" />
          </template>
          {{ generating ? '生成中...' : '生成视频' }}
        </NButton>

        <!-- Progress -->
        <div v-if="generating" class="mt-4">
          <div class="flex items-center justify-between text-[12px] text-ink-2 mb-2">
            <span>{{ progressMessage }}</span>
            <span>{{ Math.round(progress * 100) }}%</span>
          </div>
          <NProgress type="line" :percentage="Math.round(progress * 100)" :show-indicator="false" />
        </div>
      </div>
    </div>

    <!-- Preview area (right) -->
    <div class="flex-1 min-w-0 flex flex-col">
      <!-- Toolbar -->
      <div
        class="h-12 shrink-0 px-5 border-b border-line bg-bg-surface flex items-center justify-between"
      >
        <div class="flex items-center gap-2 text-[13px] text-ink-2">
          <MonitorPlay class="w-3.5 h-3.5 text-ink-3" />
          <span>已生成的微课视频</span>
          <StatusPill v-if="generating" tone="warning">生成中</StatusPill>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="h-8 px-2.5 rounded-md text-[12.5px] text-ink-2 border border-line hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
            @click="refreshList"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
            刷新
          </button>
          <button
            v-if="videos.length > 0"
            class="h-8 px-2.5 rounded-md text-[12.5px] text-ink-2 border border-line hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
            @click="askClearAll"
          >
            <Trash2 class="w-3.5 h-3.5" />
            清空
          </button>
        </div>
      </div>

      <!-- Video list -->
      <div class="flex-1 overflow-auto p-5">
        <div v-if="videos.length === 0" class="h-full flex items-center justify-center">
          <div class="text-center text-ink-3">
            <Video class="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p class="text-[13px]">暂无生成的视频</p>
            <p class="text-[12px] mt-1">上传 PPT 后点击生成按钮</p>
          </div>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="video in videos"
            :key="video.path"
            class="video-card border border-line rounded-lg overflow-hidden hover:border-accent transition-colors"
          >
            <div class="aspect-video bg-bg-subtle flex items-center justify-center">
              <video
                :src="`/api/files/download?path=${encodeURIComponent(video.path)}`"
                class="w-full h-full object-contain"
                controls
                preload="metadata"
              />
            </div>
            <div class="p-3">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                  <div class="text-[13px] font-medium text-ink-1 truncate" :title="video.name">
                    {{ video.name }}
                  </div>
                  <div class="text-[11px] text-ink-3 mt-1">
                    {{ video.created }} · {{ formatSize(video.size) }}
                  </div>
                </div>
                <div class="flex items-center gap-1 shrink-0 video-actions">
                  <a
                    :href="`/api/files/download?path=${encodeURIComponent(video.path)}`"
                    :download="`${video.name}.mp4`"
                    class="action-btn"
                    title="下载"
                  >
                    <Download class="w-3.5 h-3.5" />
                  </a>
                  <button
                    class="action-btn danger"
                    title="删除"
                    @click="askDelete(video)"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NSelect, NProgress, NUpload, useDialog, useMessage } from 'naive-ui'
import { Video, MonitorPlay, RefreshCw, Trash2, Download, X } from 'lucide-vue-next'
import StatusPill from '@/components/common/StatusPill.vue'

const message = useMessage()
const dialog = useDialog()

const uploadRef = ref()
const loading = ref(false)
const generating = ref(false)
const progress = ref(0)
const progressMessage = ref('')
const uploadFile = ref<File | null>(null)
const selectedVoice = ref('mimo_default')
const videos = ref<{ id: string; name: string; path: string; size: number; created: string }[]>([])

const voiceOptions = [
  { label: '默认', value: 'mimo_default' },
  { label: '冰糖', value: '冰糖' },
  { label: '茉莉', value: '茉莉' },
  { label: '苏打', value: '苏打' },
  { label: '白桦', value: '白桦' },
  { label: 'Mia', value: 'Mia' },
  { label: 'Chloe', value: 'Chloe' },
  { label: 'Milo', value: 'Milo' },
  { label: 'Dean', value: 'Dean' },
]

onMounted(() => {
  refreshList()
})

async function refreshList() {
  loading.value = true
  try {
    const res = await fetch('/api/ppt-video/list')
    const data = await res.json()
    videos.value = data.videos || []
  } catch (e) {
    console.error('Failed to load video list:', e)
  } finally {
    loading.value = false
  }
}

function onUploadChange(options: { file: any }) {
  if (options.file.file) {
    uploadFile.value = options.file.file
  }
}

function clearFile() {
  uploadFile.value = null
  uploadRef.value?.clear(null)
}

async function onGenerate() {
  if (!uploadFile.value) {
    message.warning('请先上传 PPT 文件')
    return
  }

  const formData = new FormData()
  formData.append('file', uploadFile.value)

  progress.value = 0.05
  progressMessage.value = '上传文件中...'

  try {
    const res = await fetch('/api/files/upload', {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      throw new Error('文件上传失败')
    }

    const data = await res.json()
    const uploadedPath = data.path

    await doGenerate(uploadedPath)
  } catch (e) {
    message.error(e instanceof Error ? e.message : '上传失败')
    generating.value = false
  }
}

async function doGenerate(pptxPath: string) {
  generating.value = true
  progress.value = 0.1
  progressMessage.value = '准备开始...'

  try {
    const res = await fetch('/api/ppt-video/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pptx_path: pptxPath, voice: selectedVoice.value }),
    })

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()

    while (reader) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      const lines = text.split('\n')

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.done) {
              if (data.success) {
                message.success('视频生成完成')
                refreshList()
                uploadFile.value = null
              } else {
                message.error(data.error || '生成失败')
              }
              generating.value = false
            } else {
              progress.value = data.progress || 0
              progressMessage.value = data.message || ''
            }
          } catch (e) {
            // ignore parse error
          }
        }
      }
    }
  } catch (e) {
    message.error(e instanceof Error ? e.message : '生成失败')
    generating.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function askDelete(video: { id: string; name: string }) {
  dialog.warning({
    title: '删除视频',
    content: `确定删除视频「${video.name}」?该操作不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await fetch('/api/ppt-video/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: video.id }),
        })
        const data = await res.json()
        if (data.success) {
          message.success('视频已删除')
          await refreshList()
        } else {
          message.error(data.error || '删除失败')
        }
      } catch (e) {
        message.error(e instanceof Error ? e.message : '删除失败')
      }
    },
  })
}

function askClearAll() {
  dialog.warning({
    title: '清空全部视频',
    content: `将删除全部 ${videos.value.length} 个微课视频(含中间产物),操作不可恢复。`,
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const res = await fetch('/api/ppt-video/clear', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ confirm: true }),
        })
        const data = await res.json()
        if (data.success) {
          message.success(`已清空 ${data.deleted_count} 个视频`)
          await refreshList()
        } else {
          message.error(data.error || '清空失败')
        }
      } catch (e) {
        message.error(e instanceof Error ? e.message : '清空失败')
      }
    },
  })
}
</script>

<style scoped>
.video-card {
  background: rgb(var(--bg-surface-rgb));
}

.video-actions {
  opacity: 0;
  transition: opacity 150ms;
}

.video-card:hover .video-actions {
  opacity: 1;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  transition: all 150ms;
  text-decoration: none;
}

.action-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
}

.action-btn.danger:hover {
  background: rgb(var(--terra-pale-rgb) / 0.6);
  color: rgb(var(--terra-rgb));
}
</style>