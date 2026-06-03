<template>
  <div class="classroom-home">
    <div class="panel">
      <h1 class="title">交互式课堂</h1>
      <p class="desc">先生成一节可播放、可答题、可反馈的真实课堂。</p>

      <div class="form-grid">
        <input v-model.trim="topic" class="field" placeholder="输入主题，例如：Python 循环语句" />
        <input v-model.trim="course" class="field" placeholder="课程名（可选）" />
      </div>

      <div class="profile-grid">
        <label class="profile-field">
          <span>学习基础</span>
          <select v-model="studentProfile.basis" class="field compact">
            <option value="零基础">零基础</option>
            <option value="有基础">有基础</option>
            <option value="进阶学习">进阶学习</option>
          </select>
        </label>
        <label class="profile-field">
          <span>学习目标</span>
          <select v-model="studentProfile.goal" class="field compact">
            <option value="考试通过">考试通过</option>
            <option value="项目实战">项目实战</option>
            <option value="概念理解">概念理解</option>
          </select>
        </label>
        <label class="profile-field">
          <span>讲解偏好</span>
          <select v-model="studentProfile.style" class="field compact">
            <option value="图解+案例">图解+案例</option>
            <option value="步骤推导">步骤推导</option>
            <option value="对比辨析">对比辨析</option>
          </select>
        </label>
        <label class="profile-field">
          <span>题目难度</span>
          <select v-model="studentProfile.difficulty" class="field compact">
            <option value="基础">基础</option>
            <option value="中等">中等</option>
            <option value="挑战">挑战</option>
          </select>
        </label>
      </div>

      <button class="primary-btn" :disabled="loading" @click="goPptStudio">
        去 PPT 工作台生成课件
      </button>

      <div v-if="pptCoursewareOptions.length" class="reuse-panel">
        <div class="reuse-copy">
          <div class="reuse-title">已有课件转课堂</div>
          <div class="reuse-desc">如果文件库里已有 PPT Studio 课件，可以直接选择并生成课堂。</div>
        </div>
        <div class="reuse-actions">
          <select v-model="selectedPptJobId" class="field reuse-select">
            <option value="">选择已有课件</option>
            <option v-for="file in pptCoursewareOptions" :key="file.id" :value="getPptJobId(file)">
              {{ file.name }}{{ file.slide_count ? ` · ${file.slide_count} 页` : '' }}
            </option>
          </select>
          <button class="secondary-btn" :disabled="loading || !selectedPptJobId" @click="onGenerate">
            <span v-if="loading" class="btn-spinner dark" aria-hidden="true"></span>
            {{ loading ? '生成中' : '生成课堂' }}
          </button>
        </div>
      </div>

      <div v-if="loading" class="generation-progress" role="status" aria-live="polite">
        <div class="progress-head">
          <div>
            <div class="progress-title">{{ activeProgressStep.title }}</div>
            <div class="progress-desc">{{ activeProgressStep.desc }}</div>
          </div>
          <div class="progress-time">{{ elapsedSeconds }}s</div>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
        <div class="step-list">
          <div
            v-for="(step, index) in progressSteps"
            :key="step.title"
            class="step-item"
            :class="{ done: index < activeProgressIndex, active: index === activeProgressIndex }"
          >
            <span class="step-dot"></span>
            <span>{{ step.title }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="list-head">
        <h2>历史课堂</h2>
        <button class="ghost-btn" :disabled="loadingList" @click="loadList">刷新</button>
      </div>

      <div v-if="classrooms.length === 0" class="empty">暂无课堂记录</div>
      <div v-else class="list">
        <div
          v-for="item in classrooms"
          :key="item.id"
          class="list-item"
        >
          <button class="item-main" @click="openClassroom(item.id)">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-meta">{{ item.topic }} · {{ item.scene_count }} scenes</div>
          </button>
          <div class="item-actions">
            <button class="mini-btn" :disabled="loading" @click="regenerateClassroom(item)">重新生成</button>
            <button class="mini-btn" @click="renameClassroom(item)">重命名</button>
            <button class="mini-btn danger" @click="deleteClassroom(item)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  deleteInteractiveClassroom,
  generateInteractiveClassroom,
  getInteractiveClassroom,
  listInteractiveClassrooms,
  renameInteractiveClassroom,
  type InteractiveClassroomListItem,
} from '@/api/interactiveClassroom'
import { listFiles } from '@/api/files'
import { useSettingStore } from '@/stores/settingStore'
import { useStudentProfile } from '@/composables/useStudentProfile'
import type { GeneratedFile } from '@/types'

const router = useRouter()
const message = useMessage()
const settingStore = useSettingStore()
const { profile: studentProfile } = useStudentProfile()

const topic = ref('')
const course = ref('Python 程序设计')
const selectedPptJobId = ref('')
const loading = ref(false)
const loadingList = ref(false)
const classrooms = ref<InteractiveClassroomListItem[]>([])
const files = ref<GeneratedFile[]>([])
const elapsedSeconds = ref(0)
const progressTimer = ref<number | null>(null)

const progressSteps = [
  { title: '解析输入', desc: '读取主题、课程和可复用 PPT 信息。' },
  { title: '组织课堂场景', desc: '生成讲解页、测验页和课堂播放顺序。' },
  { title: '生成讲解与测验', desc: '提取页面要点，生成讲解词和随堂题。' },
  { title: '合成 TTS 音频', desc: '调用当前 TTS provider，为讲解和反馈准备音频。' },
  { title: '保存课堂数据', desc: '写入课堂 JSON、音频路径和学习记录目录。' },
]

const activeProgressIndex = computed(() => {
  if (!loading.value) return 0
  if (elapsedSeconds.value < 2) return 0
  if (elapsedSeconds.value < 5) return 1
  if (elapsedSeconds.value < 10) return 2
  if (elapsedSeconds.value < 20) return 3
  return 4
})

const activeProgressStep = computed(() => progressSteps[activeProgressIndex.value])
const pptCoursewareOptions = computed(() =>
  files.value.filter((file) => Boolean(getPptJobId(file))),
)
const progressPercent = computed(() => {
  if (!loading.value) return 0
  const base = [12, 32, 54, 76, 88][activeProgressIndex.value] || 12
  const drift = Math.min(8, Math.floor(elapsedSeconds.value / 6))
  return Math.min(92, base + drift)
})

function startProgressTimer() {
  stopProgressTimer()
  elapsedSeconds.value = 0
  progressTimer.value = window.setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

function stopProgressTimer() {
  if (progressTimer.value !== null) {
    window.clearInterval(progressTimer.value)
    progressTimer.value = null
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
    },
  })
}

async function onGenerate() {
  if (!topic.value) {
    message.warning('请先输入主题')
    return
  }
  if (!selectedPptJobId.value) {
    message.warning('请先选择已有课件，或前往 PPT 工作台生成课件')
    return
  }

  loading.value = true
  startProgressTimer()
  try {
    const res = await generateInteractiveClassroom({
      topic: topic.value,
      course: course.value || undefined,
      ppt_job_id: selectedPptJobId.value || undefined,
      student_profile: studentProfile.value,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
    })
    message.success('课堂已生成')
    await loadList()
    router.push(`/interactive-classroom/${res.classroom_id}`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '生成失败')
  } finally {
    loading.value = false
    stopProgressTimer()
  }
}

function openClassroom(classroomId: string) {
  router.push(`/interactive-classroom/${classroomId}`)
}

async function regenerateClassroom(item: InteractiveClassroomListItem) {
  loading.value = true
  startProgressTimer()
  try {
    const original = await getInteractiveClassroom(item.id)
    const source = original.source || {}
    const res = await generateInteractiveClassroom({
      topic: original.topic || item.topic,
      course: original.course || item.course || undefined,
      ppt_job_id: typeof source.job_id === 'string' ? source.job_id : undefined,
      student_profile: original.student_profile || studentProfile.value,
      tts_provider: settingStore.settings.tts_provider,
      tts_model: settingStore.settings.tts_model,
      tts_voice: settingStore.settings.tts_voice,
      tts_api_key: settingStore.getEffectiveTTSApiKey(),
      tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
    })
    message.success('课堂已重新生成')
    await loadList()
    router.push(`/interactive-classroom/${res.classroom_id}`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '重新生成失败')
  } finally {
    loading.value = false
    stopProgressTimer()
  }
}

async function renameClassroom(item: InteractiveClassroomListItem) {
  const nextTitle = window.prompt('输入新的课堂名称', item.title)
  if (nextTitle === null) return
  const title = nextTitle.trim()
  if (!title) {
    message.warning('课堂名称不能为空')
    return
  }
  try {
    await renameInteractiveClassroom(item.id, title)
    message.success('已重命名')
    await loadList()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '重命名失败')
  }
}

async function deleteClassroom(item: InteractiveClassroomListItem) {
  if (!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`)) return
  try {
    await deleteInteractiveClassroom(item.id)
    message.success('已删除')
    await loadList()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败')
  }
}

onMounted(() => {
  loadList().catch(() => undefined)
})

onBeforeUnmount(() => {
  stopProgressTimer()
})
</script>

<style scoped>
.classroom-home {
  height: 100%;
  overflow: auto;
  padding: 20px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.panel {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  background: rgb(var(--bg-surface-rgb));
  padding: 16px;
}

.title {
  margin: 0;
  font-size: 22px;
}

.desc {
  margin: 8px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 14px;
}

.field {
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-base-rgb));
  padding: 0 12px;
  font-size: 14px;
}

.field.compact {
  height: 36px;
  font-size: 13px;
}

.profile-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.profile-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.profile-field span {
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.primary-btn {
  margin-top: 12px;
  height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 14px;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
  border-top-color: rgb(var(--ink-1-rgb));
}

.secondary-btn {
  height: 40px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  padding: 0 14px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-1-rgb));
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.secondary-btn:hover:not(:disabled) {
  border-color: rgb(15 118 110 / 0.35);
  color: #0f766e;
}

.secondary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reuse-panel {
  margin-top: 14px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-base-rgb));
  padding: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
  gap: 14px;
  align-items: center;
}

.reuse-title {
  color: rgb(var(--ink-1-rgb));
  font-size: 13px;
  font-weight: 700;
}

.reuse-desc {
  margin-top: 4px;
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.reuse-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reuse-select {
  min-width: 0;
  flex: 1;
}

.generation-progress {
  margin-top: 14px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 10px;
  background: rgb(var(--bg-base-rgb));
  padding: 12px;
}

.progress-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.progress-title {
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--ink-1-rgb));
}

.progress-desc {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.progress-time {
  min-width: 42px;
  text-align: right;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  font-variant-numeric: tabular-nums;
}

.progress-track {
  margin-top: 12px;
  height: 6px;
  border-radius: 999px;
  background: rgb(var(--line-rgb));
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: #10b981;
  transition: width 0.3s ease;
}

.step-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 999px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
}

.step-item.done,
.step-item.active {
  color: rgb(var(--ink-1-rgb));
}

.step-item.done .step-dot {
  border-color: #10b981;
  background: #10b981;
}

.step-item.active .step-dot {
  border-color: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.14);
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.list-head h2 {
  margin: 0;
  font-size: 16px;
}

.ghost-btn {
  height: 32px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: transparent;
  padding: 0 10px;
  cursor: pointer;
}

.empty {
  margin-top: 10px;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.list {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.list-item {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  padding: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.item-main {
  min-width: 0;
  flex: 1;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 2px 4px;
  cursor: pointer;
}

.item-main:hover .item-title {
  color: #0f766e;
}

.item-title {
  font-size: 14px;
  color: rgb(var(--ink-1-rgb));
}

.item-meta {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.mini-btn {
  height: 30px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 7px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  padding: 0 9px;
  font-size: 12px;
  cursor: pointer;
}

.mini-btn:hover:not(:disabled) {
  border-color: rgb(15 118 110 / 0.35);
  color: #0f766e;
}

.mini-btn.danger:hover:not(:disabled) {
  border-color: rgb(220 38 38 / 0.35);
  color: #dc2626;
}

.mini-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 720px) {
  .profile-grid,
  .step-list {
    grid-template-columns: 1fr;
  }

  .reuse-panel {
    grid-template-columns: 1fr;
  }

  .reuse-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .list-item {
    align-items: stretch;
    flex-direction: column;
  }

  .item-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
