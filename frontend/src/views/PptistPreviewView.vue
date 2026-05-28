<template>
  <div class="pptist-preview-wrapper">
    <!-- 自定义顶部栏 -->
    <header class="pptist-topbar">
      <div class="topbar-left">
        <router-link to="/ppt-studio" class="topbar-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          <span>返回</span>
        </router-link>
        <div class="topbar-divider" />
        <span class="topbar-title">{{ title || '未命名演示文稿' }}</span>
      </div>

      <div class="topbar-right">
        <button
          class="topbar-btn topbar-btn-save"
          :disabled="saving"
          @click="handleSave"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <a
          v-if="downloadUrl"
          :href="downloadUrl"
          class="topbar-btn topbar-btn-download"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
          下载 PPTX
        </a>
      </div>
    </header>

    <!-- 加载状态 -->
    <div v-if="loading" class="pptist-loading">
      <div class="loading-spinner" />
      <div class="loading-text">{{ loadingText }}</div>
    </div>

    <!-- PPTist 编辑器容器 -->
    <div ref="containerRef" class="pptist-container" />
  </div>
</template>

<script lang="ts" setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getUserId } from '@/composables/useUserId'
import type { PptistStudioController } from '@pptist/paper-entry'

const route = useRoute()
const containerRef = ref<HTMLDivElement | null>(null)
const loading = ref(true)
const loadingText = ref('正在加载编辑器...')
const saving = ref(false)
const title = ref('')
const downloadUrl = ref('')

const jobId = route.params.jobId as string
let studioController: PptistStudioController | null = null

const handleSave = async () => {
  if (!studioController || saving.value) return
  saving.value = true
  try {
    await studioController.save()
  } catch (e) {
    console.error('[PPTist] save failed:', e)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  if (!containerRef.value) return

  try {
    const { mountPptistStudio } = await import('@pptist/paper-entry')

    studioController = mountPptistStudio(containerRef.value, {
      source: { kind: 'preview', jobId },
      locale: 'zh',
      userId: getUserId(),
      onStatus: (message: string) => {
        if (message) {
          loadingText.value = message
          loading.value = true
        } else {
          loading.value = false
        }
      },
      onSaved: () => {
        saving.value = false
      },
      onError: (message: string) => {
        console.error('[PPTist] error:', message)
        loadingText.value = `加载失败: ${message}`
      },
    })

    // 从 PPTist host 读取下载链接和标题
    setTimeout(() => {
      const host = (window as any).__PAPER_PPTIST_HOST__
      if (host?.downloadUrl) downloadUrl.value = host.downloadUrl
    }, 500)
  } catch (err) {
    console.error('[PPTist] init failed:', err)
    loadingText.value = `加载失败: ${err instanceof Error ? err.message : String(err)}`
  }
})

onBeforeUnmount(() => {
  studioController?.destroy()
  studioController = null
})
</script>

<style scoped>
.pptist-preview-wrapper {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: #f5f6f8;
  display: flex;
  flex-direction: column;
}

/* ── 顶部栏 ── */
.pptist-topbar {
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  z-index: 1001;
  user-select: none;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.topbar-back {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 8px;
  text-decoration: none;
  cursor: pointer;
  transition: all 150ms ease;
  white-space: nowrap;
}
.topbar-back:hover {
  color: #0f172a;
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.topbar-divider {
  width: 1px;
  height: 18px;
  background: #e5e7eb;
  flex-shrink: 0;
}

.topbar-title {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.topbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #334155;
  cursor: pointer;
  text-decoration: none;
  transition: all 150ms ease;
  white-space: nowrap;
}
.topbar-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #0f172a;
}
.topbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.topbar-btn-save {
  border-color: #e5e7eb;
}
.topbar-btn-save:hover:not(:disabled) {
  background: #f0fdf4;
  border-color: #86efac;
  color: #166534;
}

.topbar-btn-download {
  background: #0f172a;
  border-color: #0f172a;
  color: #fff;
}
.topbar-btn-download:hover {
  background: #1e293b;
  border-color: #1e293b;
  color: #fff;
}

/* ── PPTist 容器 ── */
.pptist-container {
  flex: 1;
  min-height: 0;
  position: relative;
}

/* 隐藏 topbar 已覆盖的重复元素，保留画布工具栏和放映按钮 */
.pptist-container :deep(.editor-header .left) {
  display: none !important;
}
.pptist-container :deep(.editor-header .paper-save) {
  display: none !important;
}
.pptist-container :deep(.editor-header .paper-export-menu) {
  display: none !important;
}
.pptist-container :deep(.editor-header .toolbar-toggle) {
  display: none !important;
}
.pptist-container :deep(.editor-header .github-link) {
  display: none !important;
}
.pptist-container :deep(.editor-header .menu-divider) {
  display: none !important;
}

/* 隐藏 PPTist 内部加载 UI，避免与自定义加载提示重复 */
.pptist-container :deep(.fullscreen-spin) {
  display: none !important;
}
.pptist-container :deep(.paper-pptist-status) {
  display: none !important;
}

/* ── 加载态 ── */
.pptist-loading {
  position: absolute;
  inset: 44px 0 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  z-index: 10;
  background: #f8fafc;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid #e2e8f0;
  border-top-color: #0f172a;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.loading-text {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
