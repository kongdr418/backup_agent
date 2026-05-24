<template>
  <div class="video-studio-layout">
    <!-- Mobile: overlay backdrop -->
    <div class="video-overlay" :class="{ open: drawerOpen }" @click="drawerOpen = false" />

    <!-- Mobile: slide-in drawer -->
    <div class="video-drawer" :class="{ open: drawerOpen }">
      <div class="video-drawer-header">
        <span class="video-drawer-title">新建微课</span>
        <button class="video-drawer-close" @click="drawerOpen = false">
          <X class="w-4 h-4" />
        </button>
      </div>
      <div class="video-drawer-body">
        <div class="config-section">
          <label class="section-label">上传 PPT</label>
          <div
            class="upload-zone"
            :class="{ 'has-file': uploadFile, 'is-dragover': isDragover }"
            @dragover.prevent="isDragover = true"
            @dragleave="isDragover = false"
            @drop.prevent="onDrop"
            @click="triggerUpload"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".pptx"
              class="hidden"
              @change="onFileSelect"
            />
            <div v-if="!uploadFile" class="upload-placeholder">
              <Upload class="upload-icon" />
              <span class="upload-text">拖拽 PPTX 文件到此处</span>
              <span class="upload-hint">或点击选择文件</span>
            </div>
            <div v-else class="file-info">
              <FileText class="file-icon" />
              <span class="file-name">{{ uploadFile.name }}</span>
              <button class="file-remove" @click.stop="clearFile">
                <X class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div class="config-section">
          <label class="section-label">音色选择</label>
          <NSelect
            v-model:value="selectedVoice"
            :options="voiceOptions"
            placeholder="选择音色"
            size="large"
          />
        </div>

        <button
          class="generate-btn"
          :disabled="!uploadFile || generating"
          @click="onGenerate"
        >
          <template v-if="generating">
            <Loader2 class="btn-icon animate-spin" />
            生成中... {{ Math.round(progress * 100) }}%
          </template>
          <template v-else>
            <Sparkles class="btn-icon" />
            生成微课视频
          </template>
        </button>

        <div v-if="generating" class="progress-wrap">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progress * 100}%` }" />
          </div>
          <span class="progress-text">{{ progressMessage }}</span>
        </div>
      </div>
    </div>

    <!-- Desktop: Sidebar -->
    <aside class="studio-sidebar">
      <div class="sidebar-header">
        <h2 class="header-title">微课视频生成</h2>
        <p class="header-desc">上传 PPT，一键生成微课视频</p>
      </div>

      <div class="sidebar-content">
        <div class="config-section">
          <label class="section-label">上传 PPT</label>
          <div
            class="upload-zone"
            :class="{ 'has-file': uploadFile, 'is-dragover': isDragover }"
            @dragover.prevent="isDragover = true"
            @dragleave="isDragover = false"
            @drop.prevent="onDrop"
            @click="triggerUpload"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".pptx"
              class="hidden"
              @change="onFileSelect"
            />
            <div v-if="!uploadFile" class="upload-placeholder">
              <Upload class="upload-icon" />
              <span class="upload-text">拖拽 PPTX 文件到此处</span>
              <span class="upload-hint">或点击选择文件</span>
            </div>
            <div v-else class="file-info">
              <FileText class="file-icon" />
              <span class="file-name">{{ uploadFile.name }}</span>
              <button class="file-remove" @click.stop="clearFile">
                <X class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div class="config-section">
          <label class="section-label">音色选择</label>
          <NSelect
            v-model:value="selectedVoice"
            :options="voiceOptions"
            placeholder="选择音色"
            size="large"
          />
        </div>
      </div>

      <div class="sidebar-footer">
        <button
          class="generate-btn"
          :disabled="!uploadFile || generating"
          @click="onGenerate"
        >
          <template v-if="generating">
            <Loader2 class="btn-icon animate-spin" />
            生成中... {{ Math.round(progress * 100) }}%
          </template>
          <template v-else>
            <Sparkles class="btn-icon" />
            生成微课视频
          </template>
        </button>

        <div v-if="generating" class="progress-wrap">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progress * 100}%` }" />
          </div>
          <span class="progress-text">{{ progressMessage }}</span>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="studio-main">
      <header class="content-header">
        <div class="header-left">
          <h1 class="content-title">已生成的视频</h1>
          <span class="video-count">{{ videos.length }} 个视频</span>
        </div>
        <div class="header-actions">
          <button
            class="video-mobile-create-btn md:hidden action-btn"
            title="新建"
            @click="drawerOpen = true"
          >
            <Plus class="w-4 h-4" />
          </button>
          <button class="action-btn" title="刷新" @click="refreshList">
            <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          </button>
          <button
            v-if="videos.length > 0"
            class="action-btn danger"
            title="清空全部"
            @click="askClearAll"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </header>

      <!-- Video Grid -->
      <div class="content-body">
        <div v-if="videos.length === 0 && !loading" class="empty-state">
          <div class="empty-icon">
            <Film class="w-10 h-10" />
          </div>
          <h3 class="empty-title">暂无生成的视频</h3>
          <p class="empty-desc">{{ emptyDesc }}</p>
        </div>

        <div v-else-if="loading" class="loading-state">
          <div class="loading-spinner" />
          <span>加载中...</span>
        </div>

        <div v-else class="video-grid">
          <div
            v-for="video in videos"
            :key="video.path"
            class="video-card"
          >
            <div class="video-thumbnail">
              <video
                :src="`/api/files/download?path=${encodeURIComponent(video.path)}`"
                class="thumbnail-video"
                preload="metadata"
                controls
              />
            </div>
            <div class="video-info">
              <div class="video-name" :title="video.name">{{ video.name }}</div>
              <div class="video-meta">
                <span>{{ video.created }}</span>
                <span class="meta-dot">·</span>
                <span>{{ formatSize(video.size) }}</span>
              </div>
            </div>
            <div class="video-actions">
              <a
                :href="`/api/files/download?path=${encodeURIComponent(video.path)}`"
                :download="`${video.name}.mp4`"
                class="card-action-btn"
                title="下载"
              >
                <Download class="w-4 h-4" />
              </a>
              <button
                class="card-action-btn danger"
                title="删除"
                @click="askDelete(video)"
              >
                <Trash2 class="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { NSelect, useDialog, useMessage } from 'naive-ui'
import {
  Upload,
  FileText,
  X,
  RefreshCw,
  Trash2,
  Download,
  Film,
  Loader2,
  Sparkles,
  Plus,
} from 'lucide-vue-next'
import { useVideoStore } from '@/stores/videoStore'
import { useSettingStore } from '@/stores/settingStore'
import { useRefreshGuard } from '@/composables/useRefreshGuard'
import { getUserId } from '@/composables/useUserId'

const videoStore = useVideoStore()
const settingStore = useSettingStore()
const { generating, progress, progressMessage } = storeToRefs(videoStore)
useRefreshGuard()

const loading = ref(false)
const drawerOpen = ref(false)
const isMobile = ref(window.innerWidth <= 767)
const emptyDesc = computed(() =>
  isMobile.value
    ? '点击上方 + 按钮开始创作'
    : '上传 PPT 后点击生成按钮开始创作',
)
const uploadFile = ref<File | null>(null)
const isDragover = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedVoice = ref(videoStore.voice || 'mimo_default')
const videos = ref<{ id: string; name: string; path: string; size: number; created: string }[]>([])
const dialog = useDialog()
const message = useMessage()

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
  window.addEventListener('resize', onResize)

  // 如果有未完成的任务，恢复轮询
  if (videoStore.activeJobId && videoStore.generating) {
    videoStore.startPolling(
      () => {
        message.success('视频生成完成')
        refreshList()
      },
      (errMsg) => {
        message.error('生成失败: ' + errMsg)
      },
    )
  }
})

onUnmounted(() => {
  videoStore.stopPolling()
  window.removeEventListener('resize', onResize)
})

function onResize() {
  isMobile.value = window.innerWidth <= 767
}

function triggerUpload() {
  fileInputRef.value?.click()
}

function onFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.[0]) {
    uploadFile.value = target.files[0]
  }
}

function onDrop(e: DragEvent) {
  isDragover.value = false
  const file = e.dataTransfer?.files[0]
  if (file && (file.name.endsWith('.pptx') || file.name.endsWith('.pdf'))) {
    uploadFile.value = file
  }
}

function clearFile() {
  uploadFile.value = null
  if (fileInputRef.value) {
    fileInputRef.value.value = ''
  }
}

function hoverVideo(e: Event) {
  const video = e.target as HTMLVideoElement
  video.play()
}

function leaveVideo(e: Event) {
  const video = e.target as HTMLVideoElement
  video.pause()
  video.currentTime = 0
}

async function refreshList() {
  loading.value = true
  try {
    const res = await fetch(`/api/ppt-video/list?user_id=${encodeURIComponent(getUserId())}`)
    const data = await res.json()
    videos.value = data.videos || []
  } catch (e) {
    console.error('Failed to load video list:', e)
  } finally {
    loading.value = false
  }
}

async function onGenerate() {
  if (!uploadFile.value) return

  const formData = new FormData()
  formData.append('file', uploadFile.value)
  formData.append('user_id', getUserId())

  progress.value = 0.05
  progressMessage.value = '上传文件中...'

  try {
    const res = await fetch('/api/files/upload', {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) throw new Error('文件上传失败')
    const data = await res.json()
    await doGenerate(data.path)
  } catch (e) {
    videoStore.clearActiveJob()
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
      body: JSON.stringify({
        pptx_path: pptxPath,
        voice: selectedVoice.value || settingStore.settings.tts_voice,
        tts_api_key: settingStore.getEffectiveTTSApiKey(),
        tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
        tts_model: settingStore.settings.tts_model,
        tts_provider: settingStore.settings.tts_provider,
        user_id: getUserId(),
      }),
    })
    const data = await res.json()

    if (!data.success || !data.job_id) {
      throw new Error(data.error || '启动生成失败')
    }

    // 持久化到 store，刷新后可恢复
    videoStore.setActiveJob(data.job_id, pptxPath, selectedVoice.value)

    // 开始轮询进度
    videoStore.startPolling(
      () => {
        message.success('视频生成完成')
        refreshList()
        uploadFile.value = null
      },
      (errMsg) => {
        message.error('生成失败: ' + errMsg)
      },
    )
  } catch {
    videoStore.clearActiveJob()
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
          body: JSON.stringify({ id: video.id, user_id: getUserId() }),
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
          body: JSON.stringify({ confirm: true, user_id: getUserId() }),
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
/* Layout */
.video-studio-layout {
  display: flex;
  height: 100%;
}

/* Sidebar */
.studio-sidebar {
  width: 320px;
  flex-shrink: 0;
  background: #ffffff;
  border-right: 1px solid #ececec;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  height: 74px;
  padding: 0 24px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.header-icon {
  display: none;
}

.header-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  color: #111;
  margin: 0 0 6px;
  line-height: 1.3;
  letter-spacing: -0.01em;
}

.header-desc {
  font-size: 13px;
  color: #777;
  margin: 0;
  line-height: 1.5;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.config-section {
  margin-bottom: 24px;
}

.section-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #111;
  margin-bottom: 10px;
  letter-spacing: 0.01em;
}

/* Upload Zone */
.upload-zone {
  border: 1.5px dashed #d4d4d4;
  border-radius: 14px;
  padding: 28px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 200ms ease;
  background: #fafafa;
}

.upload-zone:hover {
  border-color: #b4b4b4;
  background: #f5f5f5;
}

.upload-zone.has-file {
  border-style: solid;
  border-color: #111;
  background: #fff;
}

.upload-zone.is-dragover {
  border-color: #111;
  background: #f0f0f0;
  transform: scale(1.01);
}

.hidden {
  display: none;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  width: 28px;
  height: 28px;
  color: #777;
}

.upload-text {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.upload-hint {
  font-size: 12px;
  color: #999;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.file-icon {
  width: 20px;
  height: 20px;
  color: #111;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #111;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #777;
  cursor: pointer;
  border-radius: 6px;
  transition: all 150ms ease;
}

.file-remove:hover {
  background: #f0f0f0;
  color: #111;
}

/* Sidebar Footer */
.sidebar-footer {
  padding: 20px 24px 24px;
  border-top: 1px solid #f0f0f0;
}

.generate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 14px 20px;
  border: none;
  border-radius: 14px;
  background: #111;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms ease;
}

.generate-btn:hover:not(:disabled) {
  background: #333;
}

.generate-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

.progress-wrap {
  margin-top: 16px;
}

.progress-bar {
  height: 4px;
  background: #f0f0f0;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #111;
  border-radius: 2px;
  transition: width 300ms ease;
}

.progress-text {
  display: block;
  font-size: 11px;
  color: #999;
  margin-top: 8px;
  text-align: center;
}

/* Main Content */
.studio-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.content-header {
  height: 74px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f0f0f0;
  background: #ffffff;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.content-title {
  font-family: 'Playfair Display', Georgia, serif;
  font-size: 22px;
  font-weight: 600;
  color: #111;
  margin: 0;
  letter-spacing: -0.01em;
}

.video-count {
  font-size: 13px;
  color: #999;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid #e8e8e8;
  border-radius: 10px;
  background: #fff;
  color: #555;
  cursor: pointer;
  transition: all 150ms ease;
}

.action-btn:hover {
  border-color: #ccc;
  color: #111;
}

.action-btn.danger:hover {
  border-color: #ff4444;
  color: #ff4444;
  background: #fff5f5;
}

/* Content Body */
.content-body {
  flex: 1;
  overflow-y: auto;
  padding: 28px 32px;
}

/* Empty State */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px;
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  color: #bbb;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: #333;
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 13px;
  color: #999;
  margin: 0;
}

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: #999;
  font-size: 13px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e8e8e8;
  border-top-color: #111;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Video Grid */
.video-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.video-card {
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 16px;
  overflow: hidden;
  transition: all 200ms ease;
  position: relative;
}

.video-card:hover {
  border-color: #e0e0e0;
  transform: translateY(-2px);
  box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.08);
}

.video-thumbnail {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #f5f5f5;
  overflow: hidden;
}

.thumbnail-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-info {
  padding: 14px 16px;
}

.video-name {
  font-size: 13px;
  font-weight: 500;
  color: #111;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 6px;
}

.video-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #999;
}

.meta-dot {
  color: #ddd;
}

.video-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 6px;
  opacity: 0;
  transition: opacity 200ms ease;
}

.video-card:hover .video-actions {
  opacity: 1;
}

.card-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  color: #555;
  cursor: pointer;
  text-decoration: none;
  transition: all 150ms ease;
  backdrop-filter: blur(8px);
}

.card-action-btn:hover {
  background: #fff;
  color: #111;
}

.card-action-btn.danger:hover {
  background: #fff;
  color: #ff4444;
}

/* Responsive */
@media (max-width: 1200px) {
  .video-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .video-grid {
    grid-template-columns: 1fr;
  }
}

/* ============ Mobile ============ */
@media (min-width: 768px) {
  .video-overlay,
  .video-drawer,
  .video-mobile-create-btn {
    display: none !important;
  }
}

@media (max-width: 767px) {
  /* Hide desktop sidebar */
  .studio-sidebar {
    display: none !important;
  }

  /* Overlay backdrop */
  .video-overlay {
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
  .video-overlay.open {
    opacity: 1;
    pointer-events: auto;
  }

  /* Slide-in drawer */
  .video-drawer {
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
  .video-drawer.open {
    transform: translateX(0);
  }

  .video-drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--line);
    flex-shrink: 0;
  }

  .video-drawer-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--ink-primary);
  }

  .video-drawer-close {
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
  .video-drawer-close:active {
    background: var(--bg-subtle);
  }

  .video-drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  .video-drawer-body .generate-btn {
    margin-top: 12px;
  }

  .video-drawer-body .progress-wrap {
    margin-top: 12px;
  }

  .video-studio-layout {
    flex-direction: column;
  }

  .studio-main {
    flex: 1;
    min-height: 0;
  }

  .content-header {
    height: auto;
    padding: 12px 16px;
  }

  .content-title {
    font-size: 17px;
  }

  .content-body {
    padding: 16px 12px;
  }

  .video-grid {
    gap: 12px;
  }

  .video-card {
    border-radius: 12px;
  }

  .video-info {
    padding: 10px 12px;
  }

  .video-name {
    font-size: 12px;
  }

  .video-actions {
    opacity: 1;
  }

  .card-action-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
  }

  .empty-desc {
    font-size: 12px;
  }
}
</style>