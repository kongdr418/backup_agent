<template>
  <div class="ppt-studio-layout">
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

    <!-- Desktop: Sidebar -->
    <aside class="studio-sidebar">
      <div class="sidebar-header">
        <h2 class="header-title">PPT 工作台</h2>
        <p class="header-desc">多 Agent SVG 流水线生成</p>
      </div>
      <div class="sidebar-content">
        <ParamPanel
          v-model="store.params"
          :disabled="store.isGenerating"
          @generate="onGenerate"
          @cancel="store.cancel()"
        />
      </div>
    </aside>

    <!-- Main Content -->
    <main class="studio-main">
      <header class="content-header">
        <div class="header-left">
          <h1 class="content-title">SVG 预览</h1>
          <span class="text-[13px] text-ink-3 hidden md:inline">{{ pptModelLabel }}</span>
          <StatusPill :tone="statusTone">{{ statusText }}</StatusPill>
        </div>
        <div class="header-actions">
          <button
            class="action-btn"
            :disabled="creatingClassroom"
            title="生成交互式课堂"
            @click="onCreateClassroom"
          >
            <span class="btn-label">{{ creatingClassroom ? '生成中' : '转课堂' }}</span>
          </button>
          <button
            class="video-mobile-create-btn md:hidden action-btn"
            title="参数"
            @click="drawerOpen = true"
          >
            <SlidersHorizontal class="w-4 h-4" />
          </button>
          <button
            class="action-btn history-btn"
            title="历史记录"
            @click="openHistory"
          >
            <History class="w-4 h-4" />
            <span class="btn-label">历史</span>
            <span v-if="store.jobs.length" class="btn-badge">{{ store.jobs.length }}</span>
          </button>
        </div>
      </header>

      <section v-if="creatingClassroom" class="studio-progress-panel" role="status" aria-live="polite">
        <div class="studio-progress-head">
          <div>
            <div class="studio-progress-title">课堂生成中</div>
            <div class="studio-progress-desc">
              正在生成课堂内容、语音和学习记录，完成后会自动进入播放器。当前：{{ activeClassroomProgressStep.title }}
            </div>
          </div>
          <div class="studio-progress-side">
            <div class="studio-progress-meta">
              {{ classroomElapsedSeconds }}s<span v-if="store.gen.totalSlides"> · {{ store.gen.totalSlides }} 页课件</span>
            </div>
            <button class="studio-progress-stop" @click="cancelCreateClassroom">
              停止
            </button>
          </div>
        </div>
        <div class="studio-progress-track">
          <div class="studio-progress-fill" :style="{ width: classroomProgressPercent + '%' }"></div>
        </div>
      </section>

      <!-- Content Body -->
      <div class="content-body">
        <div v-if="store.gen.status === 'idle' && templatePreview.pages && Object.keys(templatePreview.pages).length && !store.gen.slides.length" class="template-preview-wrap">
          <div class="template-preview-header">
            <span class="template-preview-label">模板预览：{{ templatePreview.label }}</span>
            <span class="template-preview-counter">{{ templatePreview.pageOrder[previewPageIdx + 1] ? (previewPageIdx + 1) + '/' + templatePreview.pageOrder.length : '' }}</span>
          </div>
          <div class="template-preview-svg" v-html="templatePreview.pages[templatePreview.pageOrder[previewPageIdx]]"></div>
          <div v-if="templatePreview.pageOrder.length > 1" class="template-preview-nav">
            <button class="preview-nav-btn" :disabled="previewPageIdx === 0" @click="previewPageIdx--">‹</button>
            <span class="preview-nav-label">{{ templatePreview.getLabel ? templatePreview.getLabel(templatePreview.pageOrder[previewPageIdx]) : templatePreview.pageOrder[previewPageIdx] }}</span>
            <button class="preview-nav-btn" :disabled="previewPageIdx >= templatePreview.pageOrder.length - 1" @click="previewPageIdx++">›</button>
          </div>
        </div>
        <PreviewStage
          v-else
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
          :job-id="store.gen.jobId"
          @select-slide="(i) => (activeIdx = i)"
          @download="onDownload"
          @reset="onReset"
        />
      </div>
    </main>

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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { History, SlidersHorizontal, X } from 'lucide-vue-next'
import { useMessage, useDialog } from 'naive-ui'

import ParamPanel from '@/components/ppt/ParamPanel.vue'
import PreviewStage from '@/components/ppt/PreviewStage.vue'
import HistoryDrawer from '@/components/ppt/HistoryDrawer.vue'
import StatusPill from '@/components/common/StatusPill.vue'

import { usePptStore } from '@/stores/pptStore'
import { usePptStream } from '@/composables/usePptStream'
import { useRefreshGuard } from '@/composables/useRefreshGuard'
import { getUserId } from '@/composables/useUserId'
import { getPptAllSlides, pptDownloadUrl } from '@/api/pptSvg'
import { fetchTemplatePreview, type TemplatePreview } from '@/api/templates'
import {
  cancelInteractiveClassroomGeneration,
  getInteractiveClassroomGenerationStatus,
  startInteractiveClassroomGeneration,
} from '@/api/interactiveClassroom'
import { useSettingStore } from '@/stores/settingStore'
import { useStudentProfile } from '@/composables/useStudentProfile'
import { buildClassroomPptNotes, type ClassroomLearnerProfile } from '@/utils/classroomPptNotes'
import { isClassroomCancelError, isClassroomGenerationMissingError } from '@/utils/classroomCancel'
import {
  clearPersistedClassroomGeneration,
  loadPersistedClassroomGeneration,
  savePersistedClassroomGeneration,
} from '@/utils/classroomGenerationState'

const store = usePptStore()
const settingStore = useSettingStore()
const router = useRouter()
const route = useRoute()
const { profile: studentProfile } = useStudentProfile()
useRefreshGuard()

const pptModelLabel = computed(() => {
  const providerId = settingStore.settings.ppt_provider
  const modelId = settingStore.settings.ppt_model
  const provider = settingStore.providers[providerId]
  const model = provider?.models.find((m) => m.id === modelId)
  if (model) return `${model.name}`
  return modelId || '默认模型'
})
const { generate } = usePptStream()

const templatePreview = ref<TemplatePreview>({ pages: {}, label: "", pageOrder: [] })
const previewPageIdx = ref(0)

watch(() => store.params.template_id, async (tid) => {
  previewPageIdx.value = 0
  if (tid) {
    try {
      templatePreview.value = await fetchTemplatePreview(tid)
    } catch {
      templatePreview.value = { pages: {}, label: "", pageOrder: [] }
    }
  } else {
    templatePreview.value = { pages: {}, label: "", pageOrder: [] }
  }
}, { immediate: true })
const message = useMessage()
const dialog = useDialog()

const activeIdx = ref(0)
const historyOpen = ref(false)
const drawerOpen = ref(false)
const creatingClassroom = ref(false)
const classroomCourse = ref('Python 程序设计')
const classroomElapsedSeconds = ref(0)
const classroomProgressTimer = ref<number | null>(null)
const classroomPollTimer = ref<number | null>(null)
const classroomRequestId = ref('')
const classroomStartedAt = ref(0)

const classroomProgressSteps = [
  { title: '读取课件', desc: '读取当前 PPT job 的 SVG 页面、标题和页面文本。' },
  { title: '组织课堂', desc: '把课件页面编排成讲解场景，并插入随堂测验位置。' },
  { title: '生成互动', desc: '根据页面内容生成讲解词、测验题和答题反馈。' },
  { title: '合成音频', desc: '调用当前 TTS 配置，为课堂讲解和反馈生成音频。' },
  { title: '保存跳转', desc: '保存课堂数据，生成完成后自动进入智慧课堂播放器。' },
]

const activeClassroomProgressIndex = computed(() => {
  if (!creatingClassroom.value) return 0
  if (classroomElapsedSeconds.value < 2) return 0
  if (classroomElapsedSeconds.value < 5) return 1
  if (classroomElapsedSeconds.value < 10) return 2
  if (classroomElapsedSeconds.value < 20) return 3
  return 4
})

const activeClassroomProgressStep = computed(() => classroomProgressSteps[activeClassroomProgressIndex.value])
const classroomProgressPercent = computed(() => {
  if (!creatingClassroom.value) return 0
  const elapsed = classroomElapsedSeconds.value
  if (elapsed < 3) return 18 + elapsed * 8
  if (elapsed < 20) return 42 + Math.floor((elapsed - 3) * 1.8)
  return Math.min(88, 72 + Math.floor((elapsed - 20) / 8))
})

function startClassroomProgressTimer(startedAt = Date.now()) {
  stopClassroomProgressTimer()
  classroomStartedAt.value = startedAt
  classroomElapsedSeconds.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  classroomProgressTimer.value = window.setInterval(() => {
    classroomElapsedSeconds.value = Math.max(0, Math.floor((Date.now() - classroomStartedAt.value) / 1000))
  }, 1000)
}

function stopClassroomProgressTimer() {
  if (classroomProgressTimer.value !== null) {
    window.clearInterval(classroomProgressTimer.value)
    classroomProgressTimer.value = null
  }
}

function stopClassroomPolling() {
  if (classroomPollTimer.value !== null) {
    window.clearInterval(classroomPollTimer.value)
    classroomPollTimer.value = null
  }
}

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
  applyClassroomDraft()
  restoreClassroomGeneration()
  store.refreshJobs().catch(() => undefined)
})

onBeforeUnmount(() => {
  stopClassroomProgressTimer()
  stopClassroomPolling()
})

function firstQueryValue(value: unknown) {
  if (Array.isArray(value)) return value[0] || ''
  return typeof value === 'string' ? value : ''
}

function applyClassroomDraft() {
  if (firstQueryValue(route.query.from) !== 'interactive-classroom') return

  const topic = firstQueryValue(route.query.topic).trim()
  const course = firstQueryValue(route.query.course).trim()
  const classroomProfile = getClassroomProfileFromQuery()
  if (topic) {
    store.params = {
      ...store.params,
      topic,
      notes: buildClassroomPptNotes(classroomProfile, store.params.notes),
      deep_research: false,
      visual_critic: false,
    }
    store.resetGen()
  }
  if (course) {
    classroomCourse.value = course
  }
  studentProfile.value = {
    ...studentProfile.value,
    ...classroomProfile,
  }
}

function getClassroomProfileFromQuery(): ClassroomLearnerProfile {
  return {
    basis: firstQueryValue(route.query.basis).trim() || studentProfile.value.basis,
    goal: firstQueryValue(route.query.goal).trim() || studentProfile.value.goal,
    style: firstQueryValue(route.query.style).trim() || studentProfile.value.style,
    difficulty: firstQueryValue(route.query.difficulty).trim() || studentProfile.value.difficulty,
  }
}

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
    // 注入设置中的 PPT 模型、API Key 和 Base URL（设置优先）
    const paramsWithModel = {
      ...store.params,
      model: settingStore.settings.ppt_model || store.params.model,
      api_key: settingStore.getEffectivePptApiKey() || store.params.api_key,
      base_url: settingStore.getEffectivePptBaseUrl() || store.params.base_url,
    }
    await generate(paramsWithModel)
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
  const url = `${pptDownloadUrl(store.gen.jobId)}?user_id=${encodeURIComponent(getUserId())}`
  window.open(url, '_blank', 'noopener')
}

async function onCreateClassroom() {
  if (!store.params.topic?.trim()) {
    message.warning('请先填写课程主题')
    return
  }
  const requestId = createClassroomRequestId()
  const startedAt = Date.now()
  classroomRequestId.value = requestId
  creatingClassroom.value = true
  startClassroomProgressTimer(startedAt)
  savePersistedClassroomGeneration({
    requestId,
    surface: 'ppt-studio',
    topic: store.params.topic,
    startedAt,
  })
  try {
    await startInteractiveClassroomGeneration({
      topic: store.params.topic,
      request_id: requestId,
      course: classroomCourse.value || store.params.topic,
      ppt_job_id: store.gen.jobId || undefined,
      student_profile: studentProfile.value,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
      content_model: settingStore.settings.content_model,
      content_api_key: settingStore.getEffectiveContentApiKey(),
      content_base_url: settingStore.getEffectiveContentBaseUrl(),
      content_provider_type: settingStore.getContentProviderType(),
    })
    startClassroomPolling(requestId)
  } catch (e) {
    if (isClassroomCancelError(e)) {
      message.info('已停止转课堂生成')
      return
    }
    message.error(e instanceof Error ? e.message : '课堂生成失败')
    finishClassroomGeneration()
  }
}

function cancelCreateClassroom() {
  const requestId = classroomRequestId.value
  if (requestId) {
    cancelInteractiveClassroomGeneration(requestId).catch(() => undefined)
  }
  finishClassroomGeneration()
  message.info('已停止转课堂生成')
}

function startClassroomPolling(requestId: string) {
  stopClassroomPolling()
  const poll = () => {
    void checkClassroomGenerationStatus(requestId)
  }
  poll()
  classroomPollTimer.value = window.setInterval(poll, 1500)
}

async function checkClassroomGenerationStatus(requestId: string) {
  try {
    const job = await getInteractiveClassroomGenerationStatus(requestId)
    if (job.status === 'done' && job.classroom_id) {
      finishClassroomGeneration()
      message.success('交互式课堂已生成')
      router.push(`/interactive-classroom/${job.classroom_id}`)
      return
    }
    if (job.status === 'cancelled') {
      finishClassroomGeneration()
      message.info('已停止转课堂生成')
      return
    }
    if (job.status === 'error') {
      finishClassroomGeneration()
      message.error(job.error || '课堂生成失败')
    }
  } catch (e) {
    if (isClassroomCancelError(e)) return
    if (isClassroomGenerationMissingError(e)) {
      finishClassroomGeneration()
      message.warning('转课堂生成状态已失效，请重新生成')
      return
    }
    message.error(e instanceof Error ? e.message : '课堂生成状态加载失败')
  }
}

function finishClassroomGeneration() {
  classroomRequestId.value = ''
  creatingClassroom.value = false
  stopClassroomProgressTimer()
  stopClassroomPolling()
  clearPersistedClassroomGeneration()
}

function restoreClassroomGeneration() {
  const persisted = loadPersistedClassroomGeneration()
  if (!persisted || persisted.surface !== 'ppt-studio') return
  classroomRequestId.value = persisted.requestId
  creatingClassroom.value = true
  startClassroomProgressTimer(persisted.startedAt)
  startClassroomPolling(persisted.requestId)
}

function createClassroomRequestId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `classroom:${crypto.randomUUID()}`
  }
  return `classroom:${Date.now()}:${Math.random().toString(16).slice(2)}`
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
    // 从 jobs 列表中获取 pptxFilename，使编辑按钮可用
    const job = store.jobs.find(j => j.job_id === jobId)
    store.gen.pptxFilename = job?.pptx_filename
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
/* ============ Layout ============ */
.ppt-studio-layout {
  display: flex;
  height: 100%;
}

/* ============ Sidebar ============ */
.studio-sidebar {
  width: 340px;
  flex-shrink: 0;
  background: rgb(var(--bg-surface-rgb));
  border-right: 1px solid rgb(var(--line-rgb));
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  height: 74px;
  padding: 0 24px;
  border-bottom: 1px solid rgb(var(--line-rgb));
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex-shrink: 0;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0 0 4px;
  line-height: 1.3;
  letter-spacing: -0.01em;
}

.header-desc {
  font-size: 13px;
  color: rgb(var(--ink-3-rgb));
  margin: 0;
  line-height: 1.5;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* ============ Main Content ============ */
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
  border-bottom: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  flex-shrink: 0;
}

.studio-progress-panel {
  flex-shrink: 0;
  margin: 14px 24px 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: 16px;
}

.studio-progress-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.studio-progress-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-primary);
}

.studio-progress-desc {
  margin-top: 4px;
  color: var(--ink-tertiary);
  font-size: 12px;
  line-height: 1.5;
}

.studio-progress-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.studio-progress-meta {
  min-width: 42px;
  text-align: right;
  color: var(--ink-tertiary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.studio-progress-stop {
  height: 30px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  background: var(--bg-surface);
  color: var(--ink-secondary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out);
}

.studio-progress-stop:hover {
  border-color: rgba(184, 74, 43, 0.35);
  color: var(--terra);
  background: rgba(245, 232, 226, 0.56);
}

.studio-progress-track {
  margin-top: 12px;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--line);
}

.studio-progress-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--forest);
  transition: width 0.3s ease;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-title {
  font-size: 20px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin: 0;
  line-height: 1.3;
  letter-spacing: -0.01em;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  cursor: pointer;
  transition: all 150ms ease;
}

.action-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--line-strong-rgb));
}

.btn-label {
  font-size: 13px;
  font-weight: 500;
}

.btn-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  font-size: 11px;
  font-weight: 600;
  margin-left: 2px;
}

/* Mobile-only param button stays icon-only */
.video-mobile-create-btn {
  width: 38px;
  padding: 0;
}

.content-body {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

/* ============ Mobile drawer elements — hidden on desktop ============ */
@media (min-width: 768px) {
  .ppt-overlay,
  .ppt-drawer,
  .video-mobile-create-btn {
    display: none !important;
  }
}

@media (max-width: 767px) {
  .studio-sidebar {
    display: none !important;
  }

  .ppt-studio-layout {
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

  .studio-progress-panel {
    margin: 12px 16px 0;
  }

  .studio-progress-head {
    flex-direction: column;
    gap: 8px;
  }

  .studio-progress-side {
    width: 100%;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .studio-progress-meta {
    text-align: left;
  }

  .content-title {
    font-size: 17px;
  }

  .content-body {
    padding: 0;
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
    background: rgb(var(--bg-surface-rgb));
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
    border-bottom: 1px solid rgb(var(--line-rgb));
    flex-shrink: 0;
  }

  .ppt-drawer-title {
    font-size: 15px;
    font-weight: 600;
    color: rgb(var(--ink-1-rgb));
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
    color: rgb(var(--ink-2-rgb));
    cursor: pointer;
    -webkit-tap-highlight-color: transparent;
  }
  .ppt-drawer-close:active {
    background: rgb(var(--bg-subtle-rgb));
  }

  .ppt-drawer-body {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }
}

.template-preview-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12px 40px;
}
.template-preview-header {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.template-preview-label {
  font-size: 13px;
  color: #999;
}
.template-preview-counter {
  font-size: 12px;
  color: #bbb;
  margin-left: auto;
}
.template-preview-svg {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.08);
}
.template-preview-svg :deep(svg) {
  width: 100%;
  height: auto;
  max-height: 100%;
  display: block;
  object-fit: contain;
}
.template-preview-nav {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}
.preview-nav-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid #e0e0e0;
  background: #fff;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
  transition: all 150ms ease;
}
.preview-nav-btn:hover:not(:disabled) {
  background: #f5f5f5;
  border-color: #ccc;
}
.preview-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.preview-nav-label {
  font-size: 13px;
  color: #666;
  min-width: 40px;
  text-align: center;
}

</style>
