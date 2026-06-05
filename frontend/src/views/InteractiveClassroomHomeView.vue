<template>
  <div class="classroom-home">
    <section class="top-panel">
      <header class="hero-row">
        <div class="hero-copy">
          <div class="hero-icon">
            <GraduationCap class="hero-icon-svg" />
          </div>
          <div>
            <h1 class="title">交互式课堂</h1>
            <p class="desc">生成一节可播放、可答题、可反馈的真实课堂。</p>
          </div>
        </div>
        <div class="hero-art" aria-hidden="true">
          <div class="art-panel art-left"></div>
          <div class="art-player">
            <PlayCircle class="art-play" />
          </div>
          <div class="art-panel art-right"></div>
          <span class="art-dot dot-one"></span>
          <span class="art-dot dot-two"></span>
        </div>
      </header>

      <div class="create-card">
        <div class="create-main">
          <h2 class="section-title">创建新课堂</h2>

          <div class="form-grid">
            <label class="line-field wide">
              <span>输入主题</span>
              <input v-model.trim="topic" class="field" placeholder="例如：Python 循环语句" />
            </label>
            <label class="line-field">
              <span>课程标题</span>
              <input v-model.trim="course" class="field" placeholder="例如：Python 程序设计" />
            </label>
          </div>

          <div class="profile-grid">
            <div class="profile-card">
              <div class="profile-icon forest">
                <BookOpen class="profile-icon-svg" />
              </div>
              <div class="profile-body">
                <span class="profile-label">学习基础</span>
                <n-select v-model:value="studentProfile.basis" :options="basisOptions" size="small" class="profile-select" />
              </div>
            </div>
            <div class="profile-card">
              <div class="profile-icon forest">
                <Target class="profile-icon-svg" />
              </div>
              <div class="profile-body">
                <span class="profile-label">学习目标</span>
                <n-select v-model:value="studentProfile.goal" :options="goalOptions" size="small" class="profile-select" />
              </div>
            </div>
            <div class="profile-card">
              <div class="profile-icon purple">
                <MessageSquare class="profile-icon-svg" />
              </div>
              <div class="profile-body">
                <span class="profile-label">讲解偏好</span>
                <n-select v-model:value="studentProfile.style" :options="styleOptions" size="small" class="profile-select" />
              </div>
            </div>
            <div class="profile-card">
              <div class="profile-icon amber">
                <BarChart3 class="profile-icon-svg" />
              </div>
              <div class="profile-body">
                <span class="profile-label">题目难度</span>
                <n-select v-model:value="studentProfile.difficulty" :options="difficultyOptions" size="small" class="profile-select" />
              </div>
            </div>
          </div>

          <button class="primary-btn" :disabled="loading" @click="goPptStudio">
            <Sparkles class="btn-icon" />
            <span>去 PPT 工作台生成课件</span>
            <ArrowRight class="btn-icon" />
          </button>
        </div>

        <aside class="reuse-panel">
          <div class="reuse-copy">
            <div class="reuse-title">已有课件转课堂</div>
            <div class="reuse-desc">如果文件库里已有 PPT Studio 课件，可以直接选择并生成课堂。</div>
          </div>
          <div class="reuse-actions">
            <n-select
              v-model:value="selectedPptJobId"
              :options="pptSelectOptions"
              size="small"
              class="reuse-select"
            />
            <button class="secondary-btn" :disabled="loading || !selectedPptJobId" @click="onGenerate">
              <span v-if="loading" class="btn-spinner dark" aria-hidden="true"></span>
              <span v-else class="folder-chip"><FolderOpen class="btn-icon" /></span>
              {{ loading ? '生成中' : '生成课堂' }}
            </button>
          </div>
        </aside>
      </div>

      <div v-if="loading" class="generation-progress" role="status" aria-live="polite">
        <div class="progress-head">
          <div>
            <div class="progress-title">课堂生成中 · {{ progressStageLabel }}</div>
            <div class="progress-desc">
              <template v-if="stream.lastScene.value">
                正在处理：{{ stream.lastScene.value.title }}
              </template>
              <template v-else>
                正在准备生成任务…
              </template>
            </div>
          </div>
          <div class="progress-side">
            <div class="progress-time">{{ elapsedSeconds }}s</div>
            <button class="progress-stop" @click="stopCurrentGeneration">停止</button>
          </div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
      </div>
    </section>

    <section class="history-panel">
      <div class="list-head">
        <div class="list-title-wrap">
          <Clock3 class="list-icon" />
          <h2>历史课堂</h2>
        </div>
        <button class="ghost-btn" :disabled="loadingList" @click="loadList">
          <RefreshCw class="mini-icon" :class="{ spinning: loadingList }" />
          刷新
        </button>
      </div>

      <div v-if="classrooms.length === 0" class="empty">暂无课堂记录</div>
      <div v-else class="list">
        <div
          v-for="item in classrooms"
          :key="item.id"
          class="list-item"
        >
          <button class="thumb-btn" :title="`打开 ${item.title}`" @click="openClassroom(item.id)">
            <span class="thumb-screen"></span>
            <PlayCircle class="thumb-play" />
            <span class="thumb-card small-one"></span>
            <span class="thumb-card small-two"></span>
          </button>
          <button class="item-main" @click="openClassroom(item.id)">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-meta">{{ item.topic }} · {{ item.scene_count }} scenes</div>
            <div class="detail-row">
              <span>
                <CalendarDays class="detail-icon" />
                创建于 {{ formatCreatedAt(item.created_at) }}
              </span>
              <span>
                <UserRound class="detail-icon" />
                创建者：当前用户
              </span>
              <span>
                <BookOpen class="detail-icon" />
                学习时长：约 {{ estimatedMinutes(item.scene_count) }} 分钟
              </span>
            </div>
          </button>
          <div class="item-actions">
            <button class="mini-btn" :disabled="reportLoading" @click="openReport(item)">
              <BookOpen class="mini-icon" />
              学习报告
            </button>
            <button class="mini-btn" :disabled="loading" @click="regenerateClassroom(item)">
              <RotateCcw class="mini-icon" />
              重新生成
            </button>
            <button class="mini-btn" @click="renameClassroom(item)">
              <Pencil class="mini-icon" />
              重命名
            </button>
            <button class="mini-btn danger" @click="deleteClassroom(item)">
              <Trash2 class="mini-icon" />
              删除
            </button>
          </div>
        </div>
      </div>
    </section>

    <n-modal
      v-model:show="renameShow"
      preset="dialog"
      title="重命名课堂"
      positive-text="确认"
      negative-text="取消"
      @positive-click="confirmRename"
    >
      <n-input v-model:value="renameValue" placeholder="新课堂名称" maxlength="80" show-count />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NInput, NModal, NSelect, useDialog, useMessage } from 'naive-ui'
import type { SelectOption } from 'naive-ui'
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  CalendarDays,
  Clock3,
  FolderOpen,
  GraduationCap,
  MessageSquare,
  Pencil,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Target,
  Trash2,
  UserRound,
} from 'lucide-vue-next'
import {
  deleteInteractiveClassroom,
  getInteractiveClassroom,
  getInteractiveClassroomReport,
  listInteractiveClassrooms,
  renameInteractiveClassroom,
  startInteractiveClassroomGeneration,
  type InteractiveClassroomListItem,
} from '@/api/interactiveClassroom'
import { listFiles } from '@/api/files'
import { useSettingStore } from '@/stores/settingStore'
import { useStudentProfile } from '@/composables/useStudentProfile'
import { useInteractiveClassroomStream } from '@/composables/useInteractiveClassroomStream'
import type { GeneratedFile } from '@/types'
import {
  clearPersistedClassroomGeneration,
  loadPersistedClassroomGeneration,
  savePersistedClassroomGeneration,
} from '@/utils/classroomGenerationState'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const settingStore = useSettingStore()

// 重命名弹窗状态
const renameShow = ref(false)
const renameValue = ref('')
const renameTargetId = ref('')
const renameTargetTitle = ref('')
const { profile: studentProfile } = useStudentProfile()

const basisOptions: SelectOption[] = [
  { label: '零基础', value: '零基础' },
  { label: '有基础', value: '有基础' },
  { label: '进阶学习', value: '进阶学习' },
]
const goalOptions: SelectOption[] = [
  { label: '考试通过', value: '考试通过' },
  { label: '项目实战', value: '项目实战' },
  { label: '概念理解', value: '概念理解' },
]
const styleOptions: SelectOption[] = [
  { label: '图解+案例', value: '图解+案例' },
  { label: '步骤推导', value: '步骤推导' },
  { label: '对比辨析', value: '对比辨析' },
]
const difficultyOptions: SelectOption[] = [
  { label: '基础', value: '基础' },
  { label: '中等', value: '中等' },
  { label: '挑战', value: '挑战' },
]

const pptSelectOptions = computed<SelectOption[]>(() => [
  { label: '选择已有课件', value: '' },
  ...pptCoursewareOptions.value.map((file) => ({
    label: `${file.name}${file.slide_count ? ` · ${file.slide_count} 页` : ''}`,
    value: getPptJobId(file),
  })),
])

const topic = ref('')
const course = ref('Python 程序设计')
const selectedPptJobId = ref('')
const loading = ref(false)
const loadingList = ref(false)
const reportLoading = ref(false)
const classrooms = ref<InteractiveClassroomListItem[]>([])
const files = ref<GeneratedFile[]>([])
const activeRequestId = ref('')
const activeStartedAt = ref(0)
const activeSuccessMessage = ref('课堂已生成')

// SSE 流式进度
const stream = useInteractiveClassroomStream()
stream.onDone = async (classroomId) => {
  finishGeneration()
  message.success(activeSuccessMessage.value)
  await loadList()
  router.push(`/interactive-classroom/${classroomId}`)
}
stream.onCancelled = () => {
  finishGeneration()
  message.info('已停止课堂生成')
}
stream.onError = (err) => {
  // 任务不存在（404）属于过期情况，特殊提示
  const isMissing = err.includes('404') || err.includes('生成任务不存在')
  if (isMissing) {
    finishGeneration()
    message.warning('课堂生成状态已失效，请重新生成')
    return
  }
  finishGeneration()
  message.error(err || '生成失败')
}
const progressPercent = stream.progressPercent

const pptCoursewareOptions = computed(() =>
  files.value.filter((file) => Boolean(getPptJobId(file))),
)

// 当前阶段的中文标签；还没收到 progress 事件时给个默认
const progressStageLabel = computed(
  () => stream.stageLabel.value || '准备中',
)

// elapsedSeconds：loading 期间每秒滚动一次
const elapsedSeconds = ref(0)
let elapsedTimer: number | null = null
function startElapsedTicker(startedAt: number) {
  stopElapsedTicker()
  activeStartedAt.value = startedAt
  elapsedSeconds.value = Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.max(0, Math.floor((Date.now() - activeStartedAt.value) / 1000))
  }, 1000)
}
function stopElapsedTicker() {
  if (elapsedTimer !== null) {
    window.clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

async function loadList() {
  loadingList.value = true
  try {
    const [classroomRows, fileRows] = await Promise.all([
      listInteractiveClassrooms(),
      listFiles(),
    ])
    classrooms.value = classroomRows
    files.value = fileRows
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载失败')
  } finally {
    loadingList.value = false
  }
}

function getPptJobId(file: GeneratedFile) {
  if (file.job_id) return file.job_id
  return file.id.startsWith('svg_ppt_') ? file.id.slice('svg_ppt_'.length) : ''
}

function goPptStudio() {
  if (!topic.value) {
    message.warning('请先输入主题')
    return
  }

  router.push({
    path: '/ppt-studio',
    query: {
      from: 'interactive-classroom',
      topic: topic.value,
      course: course.value || undefined,
      basis: studentProfile.value.basis,
      goal: studentProfile.value.goal,
      style: studentProfile.value.style,
      difficulty: studentProfile.value.difficulty,
    },
  })
}

async function onGenerate() {
  if (!selectedPptJobId.value) {
    message.warning('请先选择已有课件，或前往 PPT 工作台生成课件')
    return
  }

  // Topic 兜底：用户没填时，用选中的 PPT 文件名/job_id 拼一个
  const fallbackTopic = (() => {
    const jobId = selectedPptJobId.value
    const matched = files.value.find((f) => getPptJobId(f) === jobId)
    if (matched?.name) return matched.name.replace(/\.svg$/i, '')
    if (jobId) return `课堂-${jobId.slice(0, 8)}`
    return ''
  })()
  const finalTopic = (topic.value || '').trim() || fallbackTopic

  // 选了 PPT 之后 topic 不是必填；如果实在没法兜底才拦
  if (!finalTopic) {
    message.warning('请先输入主题或选择一个课件')
    return
  }

  try {
    await beginClassroomGeneration({
      topic: finalTopic,
      course: course.value || undefined,
      ppt_job_id: selectedPptJobId.value || undefined,
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
    }, '课堂已生成')
  } catch (err) {
    const text = err instanceof Error ? err.message : '生成失败'
    if (text.includes('课堂生成已停止')) return
    message.error(text)
  }
}

function openClassroom(classroomId: string) {
  router.push(`/interactive-classroom/${classroomId}`)
}

function formatCreatedAt(value: string) {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function estimatedMinutes(sceneCount: number) {
  return Math.max(8, Math.round((sceneCount || 0) * 0.7))
}

async function regenerateClassroom(item: InteractiveClassroomListItem) {
  try {
    const original = await getInteractiveClassroom(item.id)
    const source = original.source || {}
    await beginClassroomGeneration({
      topic: original.topic || item.topic,
      course: original.course || item.course || undefined,
      ppt_job_id: typeof source.job_id === 'string' ? source.job_id : undefined,
      student_profile: original.student_profile || studentProfile.value,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
      content_model: settingStore.settings.content_model,
      content_api_key: settingStore.getEffectiveContentApiKey(),
      content_base_url: settingStore.getEffectiveContentBaseUrl(),
      content_provider_type: settingStore.getContentProviderType(),
    }, '课堂已重新生成')
  } catch (err) {
    const text = err instanceof Error ? err.message : '重新生成失败'
    if (text.includes('课堂生成已停止')) return
    message.error(text)
  }
}

async function beginClassroomGeneration(
  body: Parameters<typeof startInteractiveClassroomGeneration>[0],
  successMessage: string,
) {
  const requestId = createClassroomRequestId()
  const startedAt = Date.now()
  activeRequestId.value = requestId
  activeSuccessMessage.value = successMessage
  loading.value = true
  startElapsedTicker(startedAt)
  savePersistedClassroomGeneration({
    requestId,
    surface: 'home',
    topic: body.topic,
    startedAt,
  })
  await startInteractiveClassroomGeneration({
    ...body,
    request_id: requestId,
  })
  // 启动 SSE 流（不再轮询）
  void stream.start(requestId)
}

function finishGeneration() {
  loading.value = false
  activeRequestId.value = ''
  stopElapsedTicker()
  stream.stop()
  clearPersistedClassroomGeneration()
}

async function stopCurrentGeneration() {
  const requestId = activeRequestId.value
  if (requestId) {
    await stream.cancel(requestId)
  } else {
    stream.stop()
  }
  finishGeneration()
  message.info('已停止课堂生成')
}

function restorePersistedGeneration() {
  const persisted = loadPersistedClassroomGeneration()
  if (!persisted || persisted.surface !== 'home') return
  activeRequestId.value = persisted.requestId
  activeSuccessMessage.value = '课堂已生成'
  loading.value = true
  startElapsedTicker(persisted.startedAt)
  // 直接连 SSE：服务器会先发 start，再发当前累计进度或 terminal
  void stream.start(persisted.requestId)
}

function createClassroomRequestId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `classroom:${crypto.randomUUID()}`
  }
  return `classroom:${Date.now()}:${Math.random().toString(16).slice(2)}`
}

function renameClassroom(item: InteractiveClassroomListItem) {
  renameTargetId.value = item.id
  renameTargetTitle.value = item.title
  renameValue.value = item.title
  renameShow.value = true
}

async function confirmRename() {
  const title = renameValue.value.trim()
  if (!title) {
    message.warning('课堂名称不能为空')
    return false
  }
  if (title === renameTargetTitle.value) {
    // 没改也直接关掉
    return true
  }
  try {
    await renameInteractiveClassroom(renameTargetId.value, title)
    message.success('已重命名')
    await loadList()
    return true
  } catch (err) {
    message.error(err instanceof Error ? err.message : '重命名失败')
    return false
  }
}

async function openReport(item: InteractiveClassroomListItem) {
  reportLoading.value = true
  try {
    const report = await getInteractiveClassroomReport(item.id)
    if (report.answered_quiz_count < 3) {
      message.warning('完成至少 3 次随堂测验后才能查看学习报告')
      return
    }
    router.push(`/interactive-classroom/${item.id}?scene=report`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '报告加载失败')
  } finally {
    reportLoading.value = false
  }
}

function deleteClassroom(item: InteractiveClassroomListItem) {
  dialog.warning({
    title: '删除课堂',
    content: `确定删除「${item.title}」？删除后无法恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteInteractiveClassroom(item.id)
        message.success('已删除')
        await loadList()
      } catch (err) {
        message.error(err instanceof Error ? err.message : '删除失败')
      }
    },
  })
}

onMounted(() => {
  loadList().catch(() => undefined)
  restorePersistedGeneration()
})

onBeforeUnmount(() => {
  stopElapsedTicker()
  stream.stop()
})
</script>

<style scoped>
.classroom-home {
  height: 100%;
  overflow: auto;
  padding: 24px 32px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
  background: var(--bg-base);
}

.top-panel,
.history-panel {
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--bg-surface);
  box-shadow: var(--shadow-md);
}

.top-panel {
  padding: 28px 30px;
}

.hero-row {
  min-height: 118px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.hero-copy {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.hero-icon {
  width: 74px;
  height: 74px;
  border-radius: 17px;
  display: grid;
  place-items: center;
  background: var(--forest-pale);
  color: var(--forest);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8), var(--shadow-sm);
}

.hero-icon-svg {
  width: 38px;
  height: 38px;
  stroke-width: 1.7;
}

.title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 32px;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--ink-primary);
}

.desc {
  margin: 10px 0 0;
  color: var(--ink-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.hero-art {
  position: relative;
  width: min(310px, 30vw);
  height: 112px;
  margin-right: 10px;
  opacity: 0.92;
}

.art-player,
.art-panel,
.art-dot {
  position: absolute;
  border: 1px solid rgba(28, 25, 23, 0.05);
  background: var(--bg-subtle);
  box-shadow: var(--shadow-sm);
}

.art-player {
  left: 112px;
  top: 8px;
  width: 82px;
  height: 76px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  color: var(--forest);
  background: var(--forest-pale);
}

.art-play {
  width: 40px;
  height: 40px;
  fill: rgba(45, 80, 22, 0.08);
}

.art-panel {
  border-radius: 12px;
  opacity: 0.68;
}

.art-left {
  left: 34px;
  top: 18px;
  width: 86px;
  height: 62px;
}

.art-left::before,
.art-left::after,
.art-right::before,
.art-right::after {
  content: "";
  position: absolute;
  left: 18px;
  height: 7px;
  border-radius: 999px;
  background: rgba(107, 124, 94, 0.18);
}

.art-left::before {
  top: 22px;
  width: 30px;
}

.art-left::after {
  top: 38px;
  width: 48px;
}

.art-right {
  right: 18px;
  top: 35px;
  width: 78px;
  height: 66px;
}

.art-right::before {
  top: 20px;
  width: 34px;
}

.art-right::after {
  top: 36px;
  width: 46px;
}

.art-dot {
  border-radius: 999px;
  background: rgba(201, 150, 60, 0.18);
}

.dot-one {
  right: 0;
  top: 14px;
  width: 14px;
  height: 14px;
}

.dot-two {
  left: 104px;
  bottom: 10px;
  width: 18px;
  height: 18px;
}

.create-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 28px 28px 24px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 32px;
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
}

.create-main {
  min-width: 0;
}

.section-title {
  margin: 0 0 24px;
  font-family: var(--font-body);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0;
  color: var(--ink-primary);
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(280px, 1.45fr) minmax(220px, 0.95fr);
  column-gap: 28px;
  row-gap: 16px;
  align-items: center;
}

.line-field {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.line-field span {
  color: var(--ink-secondary);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.field {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--bg-surface);
  color: var(--ink-primary);
  padding: 0 16px;
  font-size: 14px;
  outline: none;
  box-shadow: var(--shadow-sm);
  transition: border-color var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out);
}

.field::placeholder {
  color: var(--ink-tertiary);
}

.field:focus {
  border-color: rgba(45, 80, 22, 0.45);
  box-shadow: 0 0 0 3px rgba(45, 80, 22, 0.08);
}

.profile-grid {
  margin-top: 30px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.profile-card {
  height: 70px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  padding: 12px 14px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 14px;
  align-items: center;
  gap: 12px;
  min-width: 0;
  box-shadow: var(--shadow-sm);
}

.profile-icon {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  border-radius: 10px;
  display: grid;
  place-items: center;
}

.profile-icon.forest {
  background: rgba(232, 240, 226, 0.78);
  color: var(--forest);
}

.profile-icon.purple {
  background: rgba(240, 232, 245, 0.7);
  color: var(--nav-ppt);
}

.profile-icon.amber {
  background: rgba(251, 244, 230, 0.82);
  color: var(--amber);
}

.profile-icon-svg {
  width: 21px;
  height: 21px;
}

.profile-body {
  min-width: 0;
  display: grid;
  grid-template-rows: 18px 24px;
  align-items: center;
  row-gap: 1px;
}

.profile-label {
  display: block;
  margin-bottom: 0;
  color: var(--ink-tertiary);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
}

.profile-select :deep(.n-base-selection) {
  min-height: 24px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.profile-select :deep(.n-base-selection-label) {
  height: 24px;
  padding: 0;
  background: transparent;
  display: flex;
  align-items: center;
}

.profile-select :deep(.n-base-selection-input),
.profile-select :deep(.n-base-selection-placeholder) {
  height: 24px;
  line-height: 24px;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-primary);
  padding: 0;
}

.profile-select :deep(.n-base-selection__border),
.profile-select :deep(.n-base-selection__state-border) {
  display: none;
}

.profile-select :deep(.n-base-suffix) {
  right: -26px;
  height: 24px;
  display: flex;
  align-items: center;
  color: var(--ink-tertiary);
}

.primary-btn {
  margin-top: 30px;
  min-width: 278px;
  height: 56px;
  border: 0;
  border-radius: var(--radius-sm);
  padding: 0 22px;
  background: var(--forest);
  color: #fff;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 10px 18px -12px rgba(45, 80, 22, 0.62);
  transition: transform var(--duration-fast) var(--ease-out), box-shadow var(--duration-fast) var(--ease-out);
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  background: var(--forest-light);
  box-shadow: 0 12px 24px -14px rgba(45, 80, 22, 0.68);
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-icon,
.mini-icon {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: rgb(var(--bg-surface-rgb));
  border-radius: 999px;
  animation: spin 0.8s linear infinite;
}

.btn-spinner.dark {
  border-color: rgba(15, 23, 42, 0.18);
  border-top-color: var(--forest);
}

.secondary-btn {
  width: 100%;
  height: 48px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.68);
  color: var(--sage);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
  font-weight: 700;
  transition: border-color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out);
}

.secondary-btn:hover:not(:disabled) {
  border-color: rgba(45, 80, 22, 0.28);
  color: var(--forest);
  background: rgba(232, 240, 226, 0.34);
}

.secondary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reuse-panel {
  min-height: 210px;
  border: 1px solid var(--line-subtle);
  border-radius: var(--radius-lg);
  padding: 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: var(--bg-subtle);
  box-shadow: none;
}

.reuse-title {
  color: var(--ink-primary);
  font-size: 20px;
  font-weight: 700;
}

.reuse-desc {
  margin-top: 12px;
  color: var(--ink-secondary);
  font-size: 13px;
  line-height: 1.75;
}

.reuse-actions {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.reuse-select {
  width: 100%;
}

.reuse-select :deep(.n-base-selection) {
  min-height: 48px;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
}

.reuse-select :deep(.n-base-selection-label) {
  height: 48px;
  padding: 0 14px;
}

.reuse-select :deep(.n-base-selection-input),
.reuse-select :deep(.n-base-selection-placeholder) {
  height: 48px;
  line-height: 48px;
  font-size: 14px;
  color: var(--ink-secondary);
}

.folder-chip {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
}

.generation-progress {
  margin-top: 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: 16px;
}

.progress-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.progress-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.progress-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-primary);
}

.progress-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-tertiary);
}

.progress-time {
  min-width: 42px;
  text-align: right;
  font-size: 12px;
  color: var(--ink-tertiary);
  font-variant-numeric: tabular-nums;
}

.progress-stop {
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

.progress-stop:hover {
  border-color: rgba(184, 74, 43, 0.35);
  color: var(--terra);
  background: rgba(245, 232, 226, 0.56);
}

.progress-track {
  margin-top: 12px;
  height: 6px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--forest);
  transition: width 0.3s ease;
}

.history-panel {
  padding: 26px 30px 30px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.list-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.list-icon {
  width: 24px;
  height: 24px;
  color: var(--forest);
}

.list-head h2 {
  margin: 0;
  font-family: var(--font-body);
  font-size: 20px;
  letter-spacing: 0;
  color: var(--ink-primary);
}

.ghost-btn {
  height: 40px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--ink-secondary);
  padding: 0 14px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.empty {
  border: 1px dashed var(--line-strong);
  border-radius: 14px;
  padding: 34px 16px;
  color: var(--ink-tertiary);
  font-size: 13px;
  text-align: center;
}

.list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 13px;
}

.list-item {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  padding: 22px 22px;
  display: flex;
  align-items: center;
  gap: 26px;
  box-shadow: var(--shadow-sm);
}

.thumb-btn {
  position: relative;
  width: 198px;
  height: 92px;
  flex: 0 0 auto;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--bg-subtle), var(--amber-pale));
  color: var(--forest);
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.thumb-screen,
.thumb-card {
  position: absolute;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.36);
}

.thumb-screen {
  left: 46px;
  top: 18px;
  width: 46px;
  height: 34px;
}

.thumb-card.small-one {
  left: 24px;
  bottom: 14px;
  width: 34px;
  height: 28px;
  background: rgba(107, 124, 94, 0.16);
}

.thumb-card.small-two {
  right: 28px;
  bottom: 18px;
  width: 48px;
  height: 34px;
  background: rgba(201, 150, 60, 0.16);
}

.thumb-play {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 46px;
  height: 46px;
  transform: translate(-50%, -50%);
  color: var(--forest);
  fill: rgba(255, 255, 255, 0.72);
  filter: drop-shadow(0 6px 10px rgba(45, 80, 22, 0.18));
}

.item-main {
  min-width: 0;
  flex: 1;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.item-main:hover .item-title {
  color: var(--forest);
}

.item-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--ink-primary);
  line-height: 1.35;
}

.item-meta {
  margin-top: 7px;
  font-size: 12.5px;
  color: var(--ink-secondary);
}

.detail-row {
  margin-top: 15px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 18px;
  color: var(--ink-secondary);
  font-size: 12px;
}

.detail-row span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  white-space: nowrap;
}

.detail-icon {
  width: 15px;
  height: 15px;
  color: var(--ink-tertiary);
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.mini-btn {
  height: 44px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--ink-secondary);
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
  box-shadow: var(--shadow-sm);
  transition: border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out), background var(--duration-fast) var(--ease-out);
}

.mini-btn:hover:not(:disabled) {
  border-color: rgba(45, 80, 22, 0.32);
  color: var(--forest);
  background: rgba(232, 240, 226, 0.32);
}

.mini-btn.danger:hover:not(:disabled) {
  border-color: rgba(184, 74, 43, 0.35);
  color: var(--terra);
  background: rgba(245, 232, 226, 0.56);
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1240px) {
  .create-card {
    grid-template-columns: 1fr;
  }

  .reuse-panel {
    min-height: 0;
  }

  .item-actions {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 980px) {
  .hero-art {
    display: none;
  }

  .form-grid,
  .profile-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .line-field {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .list-item {
    align-items: stretch;
    flex-direction: column;
  }

  .thumb-btn {
    width: 100%;
    max-width: 260px;
  }

  .item-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .classroom-home {
    padding: 14px;
  }

  .top-panel,
  .history-panel {
    border-radius: 16px;
    padding: 18px;
  }

  .hero-copy {
    align-items: flex-start;
  }

  .hero-icon {
    width: 56px;
    height: 56px;
    border-radius: 14px;
  }

  .hero-icon-svg {
    width: 30px;
    height: 30px;
  }

  .title {
    font-size: 26px;
  }

  .desc {
    font-size: 13px;
  }

  .create-card {
    padding: 18px;
    border-radius: 14px;
  }

  .form-grid,
  .profile-grid {
    grid-template-columns: 1fr;
  }

  .primary-btn {
    width: 100%;
    min-width: 0;
    font-size: 14px;
  }

  .list-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .ghost-btn {
    width: 100%;
    justify-content: center;
  }

  .list-item {
    padding: 16px;
    gap: 16px;
  }

  .item-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .mini-btn {
    justify-content: center;
  }
}
</style>
