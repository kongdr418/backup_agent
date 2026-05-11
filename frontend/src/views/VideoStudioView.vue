<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div
      class="h-12 shrink-0 px-5 border-b border-line bg-bg-surface flex items-center justify-between"
    >
      <div class="flex items-center gap-2 text-[13px] text-ink-2">
        <Video class="w-3.5 h-3.5 text-ink-3" />
        <span>微课视频生成</span>
        <StatusPill v-if="status" :tone="statusTone">{{ statusText }}</StatusPill>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="h-8 px-2.5 rounded-md text-[12.5px] text-ink-2 border border-line hover:bg-bg-subtle inline-flex items-center gap-1.5 transition-colors"
          @click="refreshList"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-auto p-5">
      <!-- Upload PPT -->
      <div class="bg-bg-surface rounded-xl border border-line p-5 mb-5">
        <h3 class="text-[14px] font-medium text-ink-1 mb-4">上传 PPT</h3>

        <div class="flex gap-3">
          <NUpload
            ref="uploadRef"
            :max="1"
            accept=".pptx"
            :show-file-list="false"
            @change="onUploadChange"
          >
            <NButton>选择 PPTX 文件</NButton>
          </NUpload>
          <span v-if="uploadFile" class="text-[13px] text-ink-2 flex items-center">
            {{ uploadFile.name }}
          </span>
        </div>

        <!-- Progress -->
        <div v-if="generating" class="mt-4">
          <div class="flex items-center justify-between text-[12px] text-ink-2 mb-2">
            <span>{{ progressMessage }}</span>
            <span>{{ Math.round(progress * 100) }}%</span>
          </div>
          <NProgress type="line" :percentage="Math.round(progress * 100)" :show-indicator="false" />
        </div>

        <div v-if="!generating" class="mt-4">
          <NButton type="primary" :disabled="!uploadFile" @click="onGenerate">
            <template #icon>
              <Video class="w-4 h-4" />
            </template>
            生成视频
          </NButton>
        </div>
      </div>

      <!-- Select from library -->
      <div class="bg-bg-surface rounded-xl border border-line p-5 mb-5">
        <h3 class="text-[14px] font-medium text-ink-1 mb-4">或从文件库选择</h3>

        <div class="flex gap-3">
          <NSelect
            v-model:value="selectedPpt"
            :options="pptOptions"
            placeholder="选择要转换的 PPT"
            filterable
            class="flex-1"
            @update:value="onSelectPpt"
          />
          <NButton type="primary" :disabled="!selectedPpt" @click="onGenerateFromLibrary">
            <template #icon>
              <Video class="w-4 h-4" />
            </template>
            生成视频
          </NButton>
        </div>
      </div>

      <!-- Video List -->
      <div class="bg-bg-surface rounded-xl border border-line p-5">
        <h3 class="text-[14px] font-medium text-ink-1 mb-4">已生成的视频</h3>

        <div v-if="videos.length === 0" class="text-center py-10 text-[13px] text-ink-3">
          暂无生成的视频
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="video in videos"
            :key="video.path"
            class="border border-line rounded-lg overflow-hidden hover:border-accent transition-colors"
          >
            <div class="aspect-video bg-bg-subtle flex items-center justify-center">
              <video
                :src="`/api/files/download?path=${encodeURIComponent(video.path)}`"
                class="w-full h-full object-contain"
                controls
              />
            </div>
            <div class="p-3">
              <div class="text-[13px] font-medium text-ink-1 truncate">{{ video.name }}</div>
              <div class="text-[11px] text-ink-3 mt-1">
                {{ video.created }} · {{ formatSize(video.size) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NSelect, NProgress, NUpload, useMessage } from 'naive-ui'
import { Video, RefreshCw } from 'lucide-vue-next'
import StatusPill from '@/components/common/StatusPill.vue'

const message = useMessage()

const loading = ref(false)
const generating = ref(false)
const progress = ref(0)
const progressMessage = ref('')
const selectedPpt = ref<string | null>(null)
const uploadFile = ref<File | null>(null)
const videos = ref<{ name: string; path: string; size: number; created: string }[]>([])
const pptList = ref<{ id: string; name: string; path: string }[]>([])

const pptOptions = computed(() =>
  pptList.value.map((p) => ({ label: p.name, value: p.id }))
)

const status = computed(() => {
  if (generating.value) return 'generating'
  return null
})

const statusTone = computed<'neutral' | 'success' | 'warning' | 'danger'>(() => 'warning')

const statusText = computed(() => {
  if (generating.value) return '生成中'
  return ''
})

onMounted(() => {
  refreshList()
  loadPptList()
})

async function loadPptList() {
  try {
    const res = await fetch('/api/files')
    const data = await res.json()
    const files = data.files || []
    pptList.value = files
      .filter((f: { type: string }) => f.type === 'ppt')
      .map((f: { id: string; name: string; path: string }) => ({
        id: f.path,
        name: f.name,
        path: f.path,
      }))
  } catch (e) {
    console.error('Failed to load PPT list:', e)
  }
}

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

function onSelectPpt(value: string) {
  selectedPpt.value = value
}

function onUploadChange(options: { file: any }) {
  if (options.file.file) {
    uploadFile.value = options.file.file
    selectedPpt.value = null
  }
}

async function onGenerateFromLibrary() {
  if (!selectedPpt.value) {
    message.warning('请先选择 PPT')
    return
  }

  await doGenerate(selectedPpt.value)
}

async function onGenerate() {
  if (!uploadFile.value) {
    message.warning('请先上传 PPT 文件')
    return
  }

  // 上传文件到后端
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
      body: JSON.stringify({ pptx_path: pptxPath }),
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
</script>
