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
          @clear-draft="clearPptDraft"
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
          @clear-draft="clearPptDraft"
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
      @classroom="onClassroomFromHistory"
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
  getCourseKnowledgeCourseMap,
  type CourseKnowledgeCourseSummary,
} from '@/api/courseKnowledge'
import {
  startInteractiveClassroomGeneration,
} from '@/api/interactiveClassroom'
import { useSettingStore } from '@/stores/settingStore'
import { useInteractiveClassroomStream } from '@/composables/useInteractiveClassroomStream'
import { buildClassroomPptNotes, type ClassroomLearningContext } from '@/utils/classroomPptNotes'
import { buildClassroomCriticPayload } from '@/utils/classroomCriticConfig'
import { clearNextLessonDraft, loadNextLessonDraft, type StoredNextLessonDraft } from '@/utils/classroomNextLessonDraft'
import { applyClassroomPptDraft, resetPptDraftFields } from '@/utils/pptParams'
import {
  clearPersistedClassroomGeneration,
  loadPersistedClassroomGeneration,
  savePersistedClassroomGeneration,
} from '@/utils/classroomGenerationState'

const store = usePptStore()
const settingStore = useSettingStore()
const router = useRouter()
const route = useRoute()
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

const isClassroomSourceRoute = computed(() =>
  firstQueryValue(route.query.from) === 'interactive-classroom',
)

const activeIdx = ref(0)
const historyOpen = ref(false)
const drawerOpen = ref(false)
const creatingClassroom = ref(false)
const knowledgeCourses = ref<CourseKnowledgeCourseSummary[]>([])
const classroomCourse = ref('')
const classroomElapsedSeconds = ref(0)
const classroomRequestId = ref('')
const classroomStartedAt = ref(0)
const lastAppliedClassroomDraft = ref('')
const classroomLineage = ref<{
  courseRootId?: string
  parentClassroomId?: string
  lessonDepth?: number
  lessonIndex?: number
  lessonKind?: string
}>({})

function activeStoredDraft(): StoredNextLessonDraft | null {
  return loadNextLessonDraft()
}

// SSE 流式进度
const classroomStream = useInteractiveClassroomStream()
classroomStream.onDone = (classroomId) => {
  finishClassroomGeneration()
  message.success('交互式课堂已生成')
  router.push(`/interactive-classroom/${classroomId}`)
}
classroomStream.onCancelled = () => {
  finishClassroomGeneration()
  message.info('已停止转课堂生成')
}
classroomStream.onError = (err) => {
  const isMissing = err.includes('404') || err.includes('生成任务不存在')
  if (isMissing) {
    finishClassroomGeneration()
    message.warning('转课堂生成状态已失效，请重新生成')
    return
  }
  finishClassroomGeneration()
  message.error(err || '课堂生成失败')
}

const classroomProgressSteps = [
  { title: '读取课件', desc: '读取当前 PPT job 的 SVG 页面、标题和页面文本。' },
  { title: '组织课堂', desc: '把课件页面编排成讲解场景，并插入随堂测验位置。' },
  { title: '生成互动', desc: '根据页面内容生成讲解词、测验题和答题反馈。' },
  { title: '合成音频', desc: '调用当前 TTS 配置，为课堂讲解和反馈生成音频。' },
  { title: '保存跳转', desc: '保存课堂数据，生成完成后自动进入智慧课堂播放器。' },
]

const activeClassroomProgressIndex = computed(() => {
  if (!creatingClassroom.value) return 0
  // 直接用服务器给的 stage_index（0-based）；clamp 到合法范围
  return Math.max(0, Math.min(classroomProgressSteps.length - 1, classroomStream.stageIndex.value))
})

const activeClassroomProgressStep = computed(() => classroomProgressSteps[activeClassroomProgressIndex.value])
const classroomProgressPercent = classroomStream.progressPercent

// 让顶栏显示一个合理的"已用秒数"：用本地计时器仍然滚动（方便用户感知），
// 进度条则完全由服务器真实阶段驱动。
let classroomElapsedInterval: number | null = null
function startClassroomElapsedTicker(startedAt: number) {
  stopClassroomElapsedTicker()
  classroomStartedAt.value = startedAt
  classroomElapsedSeconds.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  classroomElapsedInterval = window.setInterval(() => {
    classroomElapsedSeconds.value = Math.max(0, Math.floor((Date.now() - classroomStartedAt.value) / 1000))
  }, 1000)
}
function stopClassroomElapsedTicker() {
  if (classroomElapsedInterval !== null) {
    window.clearInterval(classroomElapsedInterval)
    classroomElapsedInterval = null
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

watch(
  () => route.fullPath,
  () => applyClassroomDraft(),
  { immediate: true },
)

onMounted(() => {
  restoreClassroomGeneration()
  store.refreshJobs().catch(() => undefined)
  loadKnowledgeCourses().catch(() => undefined)
})

onBeforeUnmount(() => {
  stopClassroomElapsedTicker()
  classroomStream.stop()
})

function firstQueryValue(value: unknown) {
  if (Array.isArray(value)) return value[0] || ''
  return typeof value === 'string' ? value : ''
}

function applyClassroomDraft() {
  if (!isClassroomSourceRoute.value) {
    clearNextLessonDraft()
    classroomLineage.value = {}
    classroomCourse.value = ''
    return
  }
  const storedDraft = activeStoredDraft()
  const signature = `${route.fullPath}|${storedDraft ? JSON.stringify(storedDraft) : ''}`
  if (signature === lastAppliedClassroomDraft.value) return
  lastAppliedClassroomDraft.value = signature

  const topic = firstQueryValue(route.query.topic).trim() || storedDraft?.topic || ''
  const course = firstQueryValue(route.query.course).trim() || storedDraft?.course || ''
  const learningContext = getLearningContextFromQuery()
  classroomLineage.value = getLineageFromQuery(storedDraft)
  if (topic) {
    store.params = {
      ...applyClassroomPptDraft(store.params, {
        topic,
        course: course || undefined,
        notes: buildClassroomPptNotes(store.params.notes, learningContext),
      }),
      deep_research: false,
      visual_critic: false,
      repair_enabled: store.params.repair_enabled ?? false,
    }
    store.resetGen()
  }
  if (course) {
    classroomCourse.value = course
  }
}

function getNumberQueryValue(value: unknown, fallback: number) {
  const parsed = Number(firstQueryValue(value))
  return Number.isFinite(parsed) ? parsed : fallback
}

function getLineageFromQuery(storedDraft: StoredNextLessonDraft | null = null) {
  const courseRootId = firstQueryValue(route.query.course_root_id).trim() || storedDraft?.courseRootId || ''
  const parentClassroomId = firstQueryValue(route.query.parent_classroom_id).trim() || storedDraft?.parentClassroomId || ''
  const lessonKind = firstQueryValue(route.query.lesson_kind).trim() || storedDraft?.lessonKind || ''
  return {
    courseRootId: courseRootId || undefined,
    parentClassroomId: parentClassroomId || undefined,
    lessonDepth: getNumberQueryValue(route.query.lesson_depth, storedDraft?.lessonDepth ?? 0),
    lessonIndex: getNumberQueryValue(route.query.lesson_index, storedDraft?.lessonIndex ?? 1),
    lessonKind: lessonKind || undefined,
  }
}

function splitQueryValues(value: unknown) {
  return firstQueryValue(value)
    .split('||')
    .map((item: string) => item.trim())
    .filter((item: string) => Boolean(item))
}

function getLearningContextFromQuery(): ClassroomLearningContext {
  const storedDraft = isClassroomSourceRoute.value ? activeStoredDraft() : null
  const weakPoints = splitQueryValues(route.query.weak_points)
  const strongPoints = splitQueryValues(route.query.strong_points)
  return {
    weakPoints: weakPoints.length ? weakPoints : storedDraft?.weakPoints || [],
    strongPoints: strongPoints.length ? strongPoints : storedDraft?.strongPoints || [],
    nextRecommendation: firstQueryValue(route.query.next_recommendation).trim() || storedDraft?.nextRecommendation || '',
    nextLessonNotes: firstQueryValue(route.query.next_lesson_notes).trim() || storedDraft?.nextLessonNotes || '',
  }
}

async function loadKnowledgeCourses() {
  try {
    knowledgeCourses.value = await getCourseKnowledgeCourseMap()
  } catch {
    knowledgeCourses.value = []
  }
}

function compactCourseText(value: string): string {
  return value.toLowerCase().replace(/[\s　:：\-—_、，,。.!！?？（）()《》"“”'‘’]+/g, '')
}

function resolvePptKnowledgeCourse(topic: string): string | undefined {
  const explicitCourse = (store.params.course || classroomCourse.value || '').trim()
  if (explicitCourse) return explicitCourse

  const courses = knowledgeCourses.value
  if (courses.length === 1) return courses[0].courseName

  const topicKey = compactCourseText(topic)
  if (!topicKey) return undefined
  const matched = courses.find((course) => {
    const courseKey = compactCourseText(course.courseName)
    return Boolean(courseKey && (topicKey.includes(courseKey) || courseKey.includes(topicKey)))
  })
  return matched?.courseName
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
    const resolvedCourse = resolvePptKnowledgeCourse(store.params.topic)
    const paramsWithModel = {
      ...store.params,
      course: resolvedCourse || store.params.course,
      provider_id: settingStore.settings.ppt_provider,
      provider_type: settingStore.getPptProviderType(),
      model: settingStore.settings.ppt_model || store.params.model,
      api_key: settingStore.getEffectivePptApiKey() || store.params.api_key,
      base_url: settingStore.getEffectivePptBaseUrl() || store.params.base_url,
      source: firstQueryValue(route.query.from) === 'interactive-classroom'
        ? 'interactive-classroom' as const
        : undefined,
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
  // 决定要转哪个 job 的课堂。用 store.gen.jobId（最近一次生成的 PPT，
  // 或用户在历史抽屉里打开的那个）。
  const pptJobId = store.gen.jobId || ''

  // 主题兜底：表单里没有就用历史 job 的 topic，再没有就给个默认值
  const fallbackTopic = (() => {
    if (pptJobId) {
      const fromJob = store.jobs.find((j) => j.job_id === pptJobId)
      if (fromJob?.topic) return fromJob.topic
      return `课堂-${pptJobId.slice(0, 8)}`
    }
    return ''
  })()
  const topic = (store.params.topic || '').trim() || fallbackTopic
  const storedDraft = isClassroomSourceRoute.value ? activeStoredDraft() : null
  const useNextLessonDraft = Boolean(
    storedDraft?.parentClassroomId &&
    (!storedDraft.topic || storedDraft.topic === topic),
  )
  const activeLineage = {
    courseRootId: useNextLessonDraft ? classroomLineage.value.courseRootId || storedDraft?.courseRootId : undefined,
    parentClassroomId: useNextLessonDraft ? classroomLineage.value.parentClassroomId || storedDraft?.parentClassroomId : undefined,
    lessonDepth: useNextLessonDraft ? classroomLineage.value.lessonDepth ?? storedDraft?.lessonDepth : undefined,
    lessonIndex: useNextLessonDraft ? classroomLineage.value.lessonIndex ?? storedDraft?.lessonIndex : undefined,
    lessonKind: useNextLessonDraft ? classroomLineage.value.lessonKind || storedDraft?.lessonKind : undefined,
  }
  const activeCourse = useNextLessonDraft ? classroomCourse.value || storedDraft?.course || topic : topic

  // 只有当既没有 ppt_job_id 又没有 topic 时才阻止（不可能从零生成）
  if (!pptJobId && !topic) {
    message.warning('请先填写课程主题或选择一个历史 PPT')
    return
  }

  const requestId = createClassroomRequestId()
  const startedAt = Date.now()
  classroomRequestId.value = requestId
  creatingClassroom.value = true
  startClassroomElapsedTicker(startedAt)
  savePersistedClassroomGeneration({
    requestId,
    surface: 'ppt-studio',
    topic,
    startedAt,
  })
  try {
    await startInteractiveClassroomGeneration({
      topic,
      request_id: requestId,
      course: activeCourse,
      ppt_job_id: pptJobId || undefined,
      course_root_id: activeLineage.courseRootId,
      parent_classroom_id: activeLineage.parentClassroomId,
      lesson_depth: activeLineage.lessonDepth,
      lesson_index: activeLineage.lessonIndex,
      lesson_kind: activeLineage.lessonKind,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
      content_model: settingStore.settings.content_model,
      content_api_key: settingStore.getEffectiveContentApiKey(),
      content_base_url: settingStore.getEffectiveContentBaseUrl(),
      content_provider_type: settingStore.getContentProviderType(),
      ...buildClassroomCriticPayload(settingStore.settings),
    })
    if (isClassroomSourceRoute.value) clearNextLessonDraft()
    await router.push({
      name: 'interactive-classroom-player',
      params: { classroomId: 'generating' },
      query: {
        request_id: requestId,
        topic,
        generating: '1',
      },
    })
  } catch (e) {
    const text = e instanceof Error ? e.message : '课堂生成失败'
    if (text.includes('课堂生成已停止')) {
      message.info('已停止转课堂生成')
      return
    }
    message.error(text)
    finishClassroomGeneration()
  }
}

function cancelCreateClassroom() {
  const requestId = classroomRequestId.value
  if (requestId) {
    void classroomStream.cancel(requestId)
  } else {
    classroomStream.stop()
  }
  finishClassroomGeneration()
  message.info('已停止转课堂生成')
}

function finishClassroomGeneration() {
  classroomRequestId.value = ''
  creatingClassroom.value = false
  stopClassroomElapsedTicker()
  classroomStream.stop()
  clearPersistedClassroomGeneration()
}

function restoreClassroomGeneration() {
  const persisted = loadPersistedClassroomGeneration()
  if (!persisted || persisted.surface !== 'ppt-studio') return
  classroomRequestId.value = persisted.requestId
  creatingClassroom.value = true
  startClassroomElapsedTicker(persisted.startedAt)
  void router.push({
    name: 'interactive-classroom-player',
    params: { classroomId: 'generating' },
    query: {
      request_id: persisted.requestId,
      topic: persisted.topic,
      generating: '1',
    },
  })
}

function createClassroomRequestId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `classroom:${crypto.randomUUID()}`
  }
  return `classroom:${Date.now()}:${Math.random().toString(16).slice(2)}`
}

function onReset() {
  store.resetGen()
  clearPptDraft({ silent: true })
  activeIdx.value = 0
}

function clearPptDraft(options: { silent?: boolean } = {}) {
  store.params = resetPptDraftFields(store.params)
  clearNextLessonDraft()
  classroomLineage.value = {}
  classroomCourse.value = ''
  lastAppliedClassroomDraft.value = ''
  if (isClassroomSourceRoute.value) {
    void router.replace({ path: route.path, query: {} })
  }
  if (!options.silent) {
    message.success('已清空课程主题和备注')
  }
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

async function onClassroomFromHistory(jobId: string) {
  // 关掉抽屉，把 jobId 绑到当前 store（与打开历史 PPT 行为一致），
  // 然后直接调 onCreateClassroom——它会用 store.gen.jobId 来找 SVG/讲稿。
  historyOpen.value = false
  if (store.gen.jobId !== jobId) {
    // 没在预览这个 job 的话，先拉一次让它在右侧预览，方便看到 PPT 内容
    try {
      await onOpenJob(jobId)
    } catch {
      // 即便加载预览失败，也允许继续转课堂（generator 自己会去 svg_final/ 找文件）
    }
  }
  await onCreateClassroom()
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
