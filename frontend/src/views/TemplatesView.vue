<template>
  <div class="templates-page">
    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">模板管理</h1>
        <p class="page-subtitle">上传 PPTX 模板，AI 自动分析并生成可复用的 SVG 布局模板</p>
      </div>
    </div>

    <!-- Upload Area -->
    <div
      class="upload-zone"
      :class="{ dragging: isDragging, uploading: importing }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".pptx"
        class="hidden"
        @change="onFileSelect"
      />
      <div v-if="importing" class="upload-progress">
        <div class="progress-icon">
          <Loader2 class="w-8 h-8 animate-spin text-blue-500" />
        </div>
        <p class="progress-title">{{ importStatus.message || '正在处理...' }}</p>
        <div class="progress-bar-wrap">
          <div class="progress-bar" :style="{ width: `${(importStatus.progress || 0) * 100}%` }" />
        </div>
        <p class="progress-stage">{{ stageLabel(importStatus.stage) }}</p>
      </div>
      <div v-else class="upload-prompt">
        <Upload class="w-10 h-10 text-gray-400" />
        <p class="upload-text">拖拽 PPTX 文件到此处，或点击选择</p>
        <p class="upload-hint">支持 .pptx 格式，建议 5-15 页的模板文件</p>
      </div>
    </div>

    <!-- Import Error -->
    <div v-if="importError" class="error-banner">
      <AlertCircle class="w-4 h-4 text-rose-500 flex-shrink-0" />
      <span>{{ importError }}</span>
      <button class="error-dismiss" @click="importError = ''">
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Review Section -->
    <div v-if="reviewData" class="review-section">
      <div class="review-header">
        <h2 class="review-title">模板预览</h2>
        <div class="review-actions">
          <button class="btn-secondary" @click="reviewData = null">取消</button>
          <button class="btn-primary" @click="onConfirm" :disabled="confirming">
            <Check class="w-4 h-4" />
            {{ confirming ? '安装中...' : '确认安装' }}
          </button>
        </div>
      </div>

      <div v-if="reviewData.pages?.length" class="review-grid">
        <div
          v-for="(page, i) in reviewData.pages"
          :key="i"
          class="review-card"
        >
          <div class="review-card-preview">
            <span class="page-badge">{{ page.page_type }}</span>
            <span class="page-num">{{ i + 1 }}</span>
          </div>
          <p class="review-card-title">{{ page.title || `第 ${i + 1} 页` }}</p>
          <div v-if="page.placeholder_tokens?.length" class="review-card-tokens">
            <span v-for="tok in page.placeholder_tokens" :key="tok" class="token-chip">
              {{ tok }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Template List -->
    <div class="template-list-section">
      <div class="list-header">
        <h2 class="list-title">已安装模板</h2>
        <span class="list-count">{{ templates.length }} 个</span>
      </div>

      <div v-if="loadingTemplates" class="list-loading">
        <Loader2 class="w-5 h-5 animate-spin text-gray-400" />
      </div>

      <div v-else-if="templates.length === 0" class="list-empty">
        <LayoutTemplate class="w-12 h-12 text-gray-300" />
        <p>还没有模板，上传一个 PPTX 开始吧</p>
      </div>

      <div v-else class="template-grid">
        <div v-for="tpl in templates" :key="tpl.template_id" class="template-card">
          <div class="template-card-header">
            <div>
              <p class="template-name">{{ tpl.label || tpl.template_id }}</p>
              <p class="template-meta">{{ tpl.slide_count }} 页 · {{ formatDate(tpl.created_at) }}</p>
            </div>
            <button
              class="delete-btn"
              @click="onDelete(tpl.template_id)"
              title="删除模板"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
          <div v-if="tpl.page_types?.length" class="template-types">
            <span v-for="t in tpl.page_types" :key="t" class="type-chip">{{ t }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Upload, Loader2, AlertCircle, X, Check, Trash2, LayoutTemplate } from 'lucide-vue-next'
import {
  uploadTemplate,
  getImportStatus,
  getImportReview,
  confirmImport,
  listTemplates,
  deleteTemplate,
  type TemplateItem,
  type TemplateReview,
  type TemplateImportResult,
} from '@/api/templates'

const fileInput = ref<HTMLInputElement>()
const isDragging = ref(false)
const importing = ref(false)
const importError = ref('')
const importStatus = ref<TemplateImportResult>({})
const reviewData = ref<TemplateReview | null>(null)
const confirming = ref(false)
const templates = ref<TemplateItem[]>([])
const loadingTemplates = ref(true)

let currentImportId = ''

async function loadTemplates() {
  loadingTemplates.value = true
  try {
    templates.value = await listTemplates()
  } catch (e: any) {
    console.error('Failed to load templates:', e)
  } finally {
    loadingTemplates.value = false
  }
}

onMounted(loadTemplates)

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) startImport(file)
  input.value = ''
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && file.name.toLowerCase().endsWith('.pptx')) {
    startImport(file)
  } else {
    importError.value = '请上传 .pptx 文件'
  }
}

async function startImport(file: File) {
  importing.value = true
  importError.value = ''
  reviewData.value = null

  try {
    const result = await uploadTemplate(file, file.name.replace(/\.pptx$/i, ''))
    importStatus.value = result

    if (!result.success) {
      importError.value = result.error || '上传失败'
      return
    }

    currentImportId = result.import_id || ''

    // Poll for status if not already complete
    if (result.status !== 'review' && result.status !== 'completed') {
      await pollStatus(currentImportId)
    }

    // Load review if available
    if (result.review_required || result.status === 'review') {
      try {
        reviewData.value = await getImportReview(currentImportId)
      } catch {
        // Review not available
      }
    }
  } catch (e: any) {
    importError.value = e.message || '导入失败'
  } finally {
    importing.value = false
    importStatus.value = {}
  }
}

async function pollStatus(importId: string) {
  const maxAttempts = 60
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      const status = await getImportStatus(importId)
      importStatus.value = status
      if (status.status === 'review' || status.status === 'completed' || status.status === 'error') {
        if (status.status === 'error') {
          importError.value = status.message || '导入失败'
        }
        return
      }
    } catch {
      return
    }
  }
}

async function onConfirm() {
  confirming.value = true
  try {
    const result = await confirmImport(currentImportId)
    if (result.success) {
      reviewData.value = null
      await loadTemplates()
    } else {
      importError.value = result.error || '确认失败'
    }
  } catch (e: any) {
    importError.value = e.message || '确认失败'
  } finally {
    confirming.value = false
  }
}

async function onDelete(templateId: string) {
  if (!confirm('确定要删除这个模板吗？')) return
  try {
    await deleteTemplate(templateId)
    templates.value = templates.value.filter(t => t.template_id !== templateId)
  } catch (e: any) {
    importError.value = e.message || '删除失败'
  }
}

function stageLabel(stage?: string): string {
  const map: Record<string, string> = {
    uploaded: '已上传',
    analyzing: '分析 PPTX 结构...',
    rendering: '渲染幻灯片...',
    detecting_assets: '检测资源...',
    llm_review: 'AI 审查中...',
    review: '等待确认',
    completed: '完成',
  }
  return map[stage || ''] || stage || ''
}

function formatDate(s: string): string {
  try {
    return new Date(s).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  } catch {
    return s
  }
}
</script>

<style scoped>
.templates-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
}

.page-subtitle {
  font-size: 13px;
  color: rgb(var(--ink-4-rgb));
  margin: 6px 0 0;
}

/* Upload Zone */
.upload-zone {
  border: 2px dashed rgb(var(--line-rgb));
  border-radius: 12px;
  padding: 40px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 200ms ease;
  background: rgb(var(--bg-surface-rgb));
}

.upload-zone:hover {
  border-color: rgb(var(--ink-3-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.upload-zone.dragging {
  border-color: rgb(59 130 246);
  background: rgb(239 246 255);
}

.upload-zone.uploading {
  cursor: default;
  border-style: solid;
  border-color: rgb(59 130 246);
}

.hidden {
  display: none;
}

.upload-prompt {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-text {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--ink-2-rgb));
  margin: 0;
}

.upload-hint {
  font-size: 12px;
  color: rgb(var(--ink-4-rgb));
  margin: 0;
}

.upload-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.progress-title {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
}

.progress-bar-wrap {
  width: 240px;
  height: 4px;
  border-radius: 2px;
  background: rgb(var(--line-rgb));
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 2px;
  background: rgb(59 130 246);
  transition: width 500ms ease;
}

.progress-stage {
  font-size: 12px;
  color: rgb(var(--ink-4-rgb));
  margin: 0;
}

/* Error */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 12px;
  border-radius: 8px;
  background: rgb(254 242 242);
  color: rgb(185 28 28);
  font-size: 13px;
}

.error-dismiss {
  margin-left: auto;
  background: none;
  border: none;
  cursor: pointer;
  color: rgb(185 28 28);
  opacity: 0.6;
}

.error-dismiss:hover {
  opacity: 1;
}

/* Review */
.review-section {
  margin-top: 24px;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.review-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
}

.review-actions {
  display: flex;
  gap: 8px;
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

.review-card {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.review-card-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.page-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgb(219 234 254);
  color: rgb(29 78 216);
  font-weight: 500;
  text-transform: uppercase;
}

.page-num {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
}

.review-card-title {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-2-rgb));
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-card-tokens {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.token-chip {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-3-rgb));
  border: 1px solid rgb(var(--line-rgb));
  font-family: 'JetBrains Mono', monospace;
}

/* Template List */
.template-list-section {
  margin-top: 32px;
}

.list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.list-title {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
}

.list-count {
  font-size: 12px;
  color: rgb(var(--ink-4-rgb));
  padding: 1px 6px;
  border-radius: 4px;
  background: rgb(var(--bg-subtle-rgb));
}

.list-loading {
  display: flex;
  justify-content: center;
  padding: 32px;
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px;
  color: rgb(var(--ink-4-rgb));
  font-size: 13px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.template-card {
  padding: 14px;
  border-radius: 10px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  transition: border-color 150ms ease;
}

.template-card:hover {
  border-color: rgb(var(--line-strong-rgb));
}

.template-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.template-name {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
}

.template-meta {
  font-size: 11px;
  color: rgb(var(--ink-4-rgb));
  margin: 4px 0 0;
}

.delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: rgb(var(--ink-4-rgb));
  padding: 4px;
  border-radius: 4px;
  transition: all 150ms ease;
}

.delete-btn:hover {
  color: rgb(185 28 28);
  background: rgb(254 242 242);
}

.template-types {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.type-chip {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-3-rgb));
}

/* Buttons */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 150ms ease;
}

.btn-primary:hover:not(:disabled) {
  background: rgb(var(--ink-2-rgb));
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  cursor: pointer;
  transition: border-color 150ms ease;
}

.btn-secondary:hover {
  border-color: rgb(var(--line-strong-rgb));
}
</style>
