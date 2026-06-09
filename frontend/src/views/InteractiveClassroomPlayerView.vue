<template>
  <div v-if="classroom && currentScene" class="player">
    <aside class="scene-list">
      <button class="back-btn" type="button" title="返回智慧课堂" @click="goBackToList">
        <ArrowLeft class="back-icon" />
        <span>返回智慧课堂</span>
      </button>
      <div class="scene-list-head">
        <div class="scene-list-title">课堂场景</div>
        <div class="scene-list-meta">{{ currentIndex + 1 }} / {{ orderedScenes.length }}</div>
      </div>

      <button
        v-for="(scene, idx) in orderedScenes"
        :key="scene.id"
        class="scene-btn"
        :class="{ active: idx === currentIndex, locked: scene.type === 'report' && !canOpenReportScene }"
        @click="selectScene(idx)"
      >
          <span class="scene-index">{{ idx + 1 }}</span>
          <span class="scene-copy">
          <span class="scene-title">{{ formatSceneTitle(scene) }}</span>
          <span class="scene-type">{{ sceneTypeLabel(scene.type) }}</span>
        </span>
      </button>
    </aside>

    <main class="stage">
      <section class="scene-body">
        <div v-if="currentScene.type === 'slide'" class="slide-wrap">
          <div v-if="sceneSvg" ref="svgStageRef" class="svg-stage">
            <div ref="svgBoxRef" class="svg-box" v-html="sceneSvg" />
            <div
              v-if="activeHighlight && highlightLayerStyle && highlightBoxStyle"
              class="highlight-layer"
              :style="highlightLayerStyle"
            >
              <Transition name="spotlight-mask">
                <div
                  v-if="activeHighlight.mode === 'spotlight'"
                  class="highlight-spotlight"
                  :style="highlightBoxStyle"
                />
              </Transition>
              <div
                class="highlight-box"
                :class="{ spotlight: activeHighlight.mode === 'spotlight' }"
                :style="highlightBoxStyle"
              />
            </div>
          </div>
          <pre v-else class="md-box">{{ sceneMarkdown || '本页暂无内容' }}</pre>
        </div>

        <div v-else-if="currentScene.type === 'mindmap'" class="mindmap-wrap">
          <MindmapScene
            :markdown="sceneMarkmapMd"
            :title="currentScene.title"
          />
        </div>

        <div v-else-if="currentScene.type === 'quiz'" class="quiz-wrap">
          <div v-for="(q, qIndex) in questions" :key="q.id" class="question-card">
            <div class="question-head">
              <span class="question-index">Q{{ qIndex + 1 }}</span>
              <div class="q-title">
                {{ q.question }}
                <span v-if="q.type === 'short_answer'" class="question-type-tag">简答题</span>
                <span v-else-if="q.type === 'multiple'" class="question-type-tag">多选题</span>
              </div>
            </div>

            <div v-if="q.type === 'short_answer'" class="short-answer-area">
              <textarea
                class="short-answer-input"
                :rows="5"
                :placeholder="currentQuizResult ? '已提交' : '请输入你的回答（提交后由 AI 评分）'"
                :value="(currentAnswers[q.id] && currentAnswers[q.id][0]) || ''"
                :disabled="!!currentQuizResult || submitting"
                @input="onShortAnswerInput(q.id, $event)"
              />
              <div v-if="!currentQuizResult" class="short-answer-hint">
                AI 会按准确性 / 完整性 / 表达 三个维度打分（0-100），80 分及以上视为掌握
              </div>
            </div>

            <div v-else class="option-list">
              <button
                v-for="opt in q.options"
                :key="opt.value"
                type="button"
                class="option-btn"
                :class="optionClass(q.id, opt.value)"
                @click="setAnswer(q.id, opt.value)"
              >
                <span class="option-key">{{ opt.value }}</span>
                <span class="option-text">{{ opt.label }}</span>
                <CheckCircle v-if="isCorrectOption(q.id, opt.value)" class="option-icon good" />
                <XCircle v-else-if="isWrongSelectedOption(q.id, opt.value)" class="option-icon bad" />
              </button>
            </div>

            <div v-if="resultByQuestion[q.id]" class="analysis-box">
              <template v-if="q.type === 'short_answer'">
                <div class="analysis-title analysis-row">
                  <span>
                    {{ resultByQuestion[q.id].correct ? '已掌握（≥80 分）' : '需要补强' }}
                  </span>
                  <span v-if="typeof resultByQuestion[q.id].score === 'number'" class="short-answer-score">
                    {{ resultByQuestion[q.id].score }} / 100
                  </span>
                </div>
                <div v-if="resultByQuestion[q.id].feedback" class="analysis-copy">
                  <strong>AI 评语：</strong>{{ resultByQuestion[q.id].feedback }}
                </div>
                <div v-if="resultByQuestion[q.id].analysis" class="analysis-copy analysis-muted">
                  参考要点：{{ resultByQuestion[q.id].analysis }}
                </div>
              </template>
              <template v-else>
                <div class="analysis-title">
                  {{ resultByQuestion[q.id].correct ? '回答正确' : '还需要巩固' }}
                </div>
                <div class="analysis-copy">{{ resultByQuestion[q.id].analysis || '暂无解析' }}</div>
              </template>
              <button
                type="button"
                class="analysis-to-discussion"
                @click="sendQuestionToDiscussion(q)"
              >
                <MessageSquare class="analysis-to-discussion-icon" />
                传至讨论
              </button>
            </div>
          </div>

          <div class="quiz-actions">
            <button class="primary-btn" :disabled="submitting || !allAnswered" @click="submitQuiz">
              {{ submitting ? '提交中...' : '提交答案' }}
            </button>
            <button class="secondary-btn" :disabled="submitting" @click="resetQuiz">重做</button>
            <button class="secondary-btn" :disabled="!currentQuizResult" @click="goNext">下一页</button>
          </div>

          <div v-if="currentQuizResult" class="result-box">
            <div class="score-ring">{{ currentQuizResult.score }}%</div>
            <div>
              <div class="result-summary">
                完成 {{ currentQuizResult.total }} 题，答对 {{ currentQuizResult.correct }} 题
              </div>
              <div class="result-tip">{{ feedbackText || '系统已记录本次答题结果。' }}</div>
            </div>
          </div>
        </div>

        <div v-else-if="currentScene.type === 'report'" class="report-page">
          <div v-if="reportLoading && !report" class="report-empty">
            <div class="report-kicker">课后学习报告</div>
            <h3>正在整理本节课堂表现...</h3>
          </div>

          <div v-else-if="report" class="report-sheet">
            <div class="report-hero">
              <div>
                <div class="report-kicker">课后学习报告</div>
                <h3>{{ report.topic }}</h3>
                <p>{{ report.next_recommendation }}</p>
              </div>
              <div class="report-score-card">
                <span>综合得分</span>
                <strong>{{ report.score }}%</strong>
              </div>
            </div>

            <div class="report-grid">
              <div class="report-metric">
                <span>答题进度</span>
                <strong>{{ report.answered_quiz_count }} / {{ report.quiz_scene_count }}</strong>
              </div>
              <div class="report-metric">
                <span>正确题数</span>
                <strong>{{ report.correct }} / {{ report.total }}</strong>
              </div>
              <div class="report-metric">
                <span>得分</span>
                <strong>{{ report.earned_points }} / {{ report.total_points }}</strong>
              </div>
            </div>

            <div class="report-columns">
              <section class="report-block">
                <div class="report-label">薄弱点</div>
                <div v-if="report.weak_points.length" class="tag-row">
                  <span v-for="point in report.weak_points" :key="point" class="tag weak">{{ point }}</span>
                </div>
                <p v-else class="muted-copy">本节暂无明显薄弱点，可以继续进入下一阶段学习。</p>
              </section>

              <section class="report-block">
                <div class="report-label">强项</div>
                <div v-if="report.strong_points.length" class="tag-row">
                  <span v-for="point in report.strong_points" :key="point" class="tag strong">{{ point }}</span>
                </div>
                <p v-else class="muted-copy">完成更多测验后，系统会沉淀更稳定的强项判断。</p>
              </section>
            </div>

            <section v-if="reportKnowledgeRows.length" class="report-block">
              <div class="report-label">知识点掌握度</div>
              <div class="mastery-list">
                <div v-for="row in reportKnowledgeRows" :key="row.name" class="mastery-row">
                  <span>{{ row.name }}</span>
                  <div class="mastery-bar"><i :style="{ width: row.mastery + '%' }" /></div>
                  <strong>{{ row.mastery }}%</strong>
                </div>
              </div>
            </section>

            <section v-if="reportRecommendedTasks.length" class="report-block">
              <div class="report-label">下一步学习任务</div>
              <div class="task-list">
                <article v-for="task in reportRecommendedTasks" :key="task.id" class="task-row">
                  <div class="task-priority" :class="task.priority">{{ taskPriorityLabel(task.priority) }}</div>
                  <div class="task-copy">
                    <div class="task-title">{{ task.title }}</div>
                    <p>{{ task.description }}</p>
                    <p v-if="task.reason" class="task-reason">依据：{{ task.reason }}</p>
                    <div v-if="task.knowledge_points.length" class="tag-row">
                      <span v-for="point in task.knowledge_points" :key="`${task.id}-${point}`" class="tag task-point">{{ point }}</span>
                    </div>
                  </div>
                  <button
                    class="task-action"
                    :disabled="!canRunTask(task) || runningTaskId === task.id"
                    @click="runTask(task)"
                  >
                    {{ taskButtonLabel(task) }}
                  </button>
                </article>
              </div>
            </section>
          </div>
        </div>
      </section>

      <footer v-if="currentScene.type !== 'report'" class="narrator">
        <div class="narrator-card">
          <div class="narrator-body">
            <div class="teacher-mark">
              <div class="teacher-avatar">
                <Volume2 v-if="isAudioPlaying" class="icon avatar-pulse" />
                <VolumeX v-else class="icon" />
              </div>
              <div class="teacher-meta">
                <div class="teacher-name">AI 教师</div>
                <div class="play-status">{{ playbackStatusText }}</div>
              </div>
            </div>
            <div ref="speechTextRef" class="speech-text">
              <template v-if="currentSpeechParagraphs.length">
                <span
                  v-for="(paragraph, idx) in currentSpeechParagraphs"
                  :key="`${idx}-${paragraph.start_ratio}`"
                  :data-speech-segment-index="idx"
                  class="speech-segment"
                  :class="{
                    active: idx === activeSpeechParagraphIdx,
                    inactive: activeSpeechParagraphIdx >= 0 && idx !== activeSpeechParagraphIdx,
                  }"
                >
                  {{ paragraph.text }}
                </span>
              </template>
              <template v-else>{{ currentSpeechText || '当前场景暂无讲解词' }}</template>
            </div>
          </div>

          <template v-if="currentAudioUrl">
            <audio
              ref="audioRef"
              :key="currentAudioUrl"
              :src="currentAudioUrl"
              :autoplay="autoPlayEnabled && currentScene.type !== 'quiz'"
              @ended="handleAudioEnded"
              @play="isAudioPlaying = true"
              @pause="isAudioPlaying = false"
              @loadedmetadata="onAudioLoaded"
              @timeupdate="onAudioTimeUpdate"
              @volumechange="onAudioVolumeChange"
              @ratechange="onAudioRateChange"
            />
            <div class="audio-bar">
              <div class="audio-controls">
                <button
                  type="button"
                  class="audio-tool-btn"
                  :disabled="currentIndex === 0"
                  title="上一页"
                  @click="goPrev"
                >
                  <ChevronLeft class="audio-tool-icon" />
                </button>
                <button
                  type="button"
                  class="audio-tool-btn"
                  :class="{ active: autoPlayEnabled }"
                  :title="autoPlayEnabled ? '关闭自动播放' : '开启自动播放'"
                  @click="toggleAutoPlay"
                >
                  <PauseCircle v-if="autoPlayEnabled" class="audio-tool-icon" />
                  <PlayCircle v-else class="audio-tool-icon" />
                </button>
                <button
                  type="button"
                  class="audio-tool-btn"
                  :disabled="currentIndex >= orderedScenes.length - 1"
                  title="下一页"
                  @click="goNext"
                >
                  <ChevronRight class="audio-tool-icon" />
                </button>

                <span class="audio-time">
                  <em>{{ formatAudioTime(currentAudioTime) }}</em>
                  <i>/</i>
                  <span>{{ formatAudioTime(audioDuration) }}</span>
                </span>

                <div class="audio-volume">
                  <button
                    type="button"
                    class="audio-tool-btn"
                    :title="audioVolume === 0 ? '取消静音' : '静音'"
                    @click="toggleAudioMute"
                  >
                    <VolumeX v-if="audioVolume === 0" class="audio-tool-icon" />
                    <Volume2 v-else class="audio-tool-icon" />
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    :value="audioVolume"
                    class="audio-slider"
                    @input="onAudioVolumeInput"
                  />
                </div>

                <button
                  type="button"
                  class="audio-rate"
                  :title="`倍速 ${audioPlaybackRate}x`"
                  @click="cyclePlaybackRate"
                >
                  {{ audioPlaybackRate }}x
                </button>
              </div>
            </div>
          </template>
        </div>
      </footer>
    </main>

    <DiscussionSidebar
      ref="discussionRef"
      :messages="discussionMessages"
      :submitting="discussionSubmitting"
      :auto-advance-paused="discussionActive"
      :multi-agent-enabled="multiAgentDiscussionEnabled"
      @submit="handleDiscussionSubmit"
      @quick-action="handleDiscussionQuickAction"
      @clear-history="confirmClearDiscussionHistory"
      @update:multi-agent-enabled="multiAgentDiscussionEnabled = $event"
    />
  </div>

  <div v-else class="loading">加载课堂中...</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import { ArrowLeft, CheckCircle, ChevronLeft, ChevronRight, MessageSquare, Pause, PauseCircle, Play, PlayCircle, Volume2, VolumeX, XCircle } from 'lucide-vue-next'
import { getUserId } from '@/composables/useUserId'
import {
  createClassroomPractice,
  discussInteractiveClassroom,
  discussInteractiveClassroomStream,
  type ClassroomRecommendedTask,
  type ClassroomDiscussionMessage,
  getInteractiveClassroom,
  getInteractiveClassroomReport,
  submitInteractiveClassroomAnswer,
  type ClassroomReport,
  type InteractiveClassroomAction,
  type InteractiveClassroomPayload,
  type InteractiveClassroomQuestion,
  type InteractiveClassroomScene,
  type QuizSubmitResult,
} from '@/api/interactiveClassroom'
import { resolveReportTaskAction } from '@/utils/classroomReportTask'
import { buildClassroomDiscussionLlmPayload } from '@/utils/classroomDiscussionLlmConfig'
import {
  clearPersistedDiscussionMessages,
  loadPersistedDiscussionMessages,
  savePersistedDiscussionMessages,
} from '@/utils/classroomDiscussionState'
import { applyDiscussionAgentEvent, scopeDiscussionMessageId, upsertDiscussionAssistantMessage } from '@/utils/classroomDiscussionStream'
import { buildPlayerAnswerState } from '@/utils/classroomAnswers'
import { emitSceneReviewed, emitRecommendedTaskOpened, emitClassroomCompleted } from '@/utils/classroomEvents'
import { activeSpeechParagraphIndex, buildSpeechParagraphs } from '@/utils/classroomSpeechHighlight'
import { computeSpeechAutoScrollTop } from '@/utils/classroomSpeechScroll'
import {
  activeHighlightCue,
  activeHighlightMode,
  fallbackHighlightTargetsFromSvgElement,
  normalizeHighlightCues,
  resolveHighlightTargetsFromSvgElement,
  type HighlightCue,
  type HighlightTarget,
} from '@/utils/classroomHighlight'
import DiscussionSidebar from '@/components/classroom/DiscussionSidebar.vue'
import MindmapScene from '@/components/classroom/MindmapScene.vue'
import { useSettingStore } from '@/stores/settingStore'

const route = useRoute()
const router = useRouter()
const dialog = useDialog()
const message = useMessage()
const settingStore = useSettingStore()

const classroom = ref<InteractiveClassroomPayload | null>(null)
const currentIndex = ref(0)
const answersByScene = ref<Record<string, Record<string, string[]>>>({})
const quizResultsByScene = ref<Record<string, QuizSubmitResult | null>>({})
let classroomLoadVersion = 0
const discussionRef = ref<InstanceType<typeof DiscussionSidebar> | null>(null)
const submitting = ref(false)
const runningTaskId = ref('')
const reportLoading = ref(false)
const report = ref<ClassroomReport | null>(null)
const reportAutoShown = ref(false)
const autoPlayEnabled = ref(true)
const discussionMessages = ref<ClassroomDiscussionMessage[]>([])
const discussionSubmitting = ref(false)
const multiAgentDiscussionEnabled = ref(localStorage.getItem('ai_creator.classroom_discussion.multi_agent') === 'true')
const visitedSceneIds = ref<Set<string>>(new Set())
const classroomCompletedEmitted = ref(false)
const isAudioPlaying = ref(false)
const currentAudioTime = ref(0)
const audioDuration = ref(0)
const audioVolume = ref(1)
const audioPlaybackRate = ref(1)
const playbackRateOptions = [0.75, 1, 1.25, 1.5, 2]
const speechTextRef = ref<HTMLElement | null>(null)
const svgStageRef = ref<HTMLElement | null>(null)
const svgBoxRef = ref<HTMLElement | null>(null)
const fallbackHighlightTargets = ref<HighlightTarget[]>([])
const measuredHighlightTargets = ref<HighlightTarget[]>([])
const svgMetrics = ref<{
  left: number
  top: number
  width: number
  height: number
  viewWidth: number
  viewHeight: number
} | null>(null)

function onAudioLoaded() {
  audioDuration.value = audioRef.value?.duration || 0
}

function onAudioTimeUpdate() {
  currentAudioTime.value = audioRef.value?.currentTime || 0
}

function onAudioVolumeChange() {
  audioVolume.value = audioRef.value?.volume ?? 1
}

function onAudioRateChange() {
  audioPlaybackRate.value = audioRef.value?.playbackRate || 1
}

function syncSpeechParagraphScroll() {
  const container = speechTextRef.value
  const activeIndex = activeSpeechParagraphIdx.value
  if (!container || activeIndex < 0) return

  const activeSegment = container.querySelector(`[data-speech-segment-index="${activeIndex}"]`) as HTMLElement | null
  if (!activeSegment) return

  const targetTop = computeSpeechAutoScrollTop({
    currentScrollTop: container.scrollTop,
    containerHeight: container.clientHeight,
    contentHeight: container.scrollHeight,
    segmentTop: activeSegment.offsetTop,
    segmentHeight: activeSegment.offsetHeight,
  })
  if (targetTop === null) return

  container.scrollTo({
    top: targetTop,
    behavior: 'smooth',
  })
}

function toggleAudioPlay() {
  const el = audioRef.value
  if (!el) return
  if (el.paused) {
    el.play().catch(() => {})
  } else {
    el.pause()
  }
}

function toggleAudioMute() {
  const el = audioRef.value
  if (!el) return
  el.volume = el.volume > 0 ? 0 : 1
}

function onAudioVolumeInput(event: Event) {
  const value = Number((event.target as HTMLInputElement).value)
  if (audioRef.value) audioRef.value.volume = value
}

function cyclePlaybackRate() {
  const el = audioRef.value
  if (!el) return
  const idx = playbackRateOptions.indexOf(audioPlaybackRate.value)
  const next = playbackRateOptions[(idx + 1) % playbackRateOptions.length]
  el.playbackRate = next
}

function formatAudioTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
const audioRef = ref<HTMLAudioElement | null>(null)
const advanceTimer = ref<number | null>(null)

const baseScenes = computed(() =>
  [...(classroom.value?.scenes || [])].sort((a, b) => (a.order || 0) - (b.order || 0)),
)

const reportScene = computed<InteractiveClassroomScene>(() => ({
  id: 'scene_report',
  type: 'report',
  title: '学习报告',
  order: baseScenes.value.length + 1,
  content: {},
  actions: [],
}))

const orderedScenes = computed(() => [...baseScenes.value, reportScene.value])

const currentScene = computed(() => orderedScenes.value[currentIndex.value] || null)
const playedSceneIds = computed(() => {
  const sceneCount = Math.min(currentIndex.value + 1, baseScenes.value.length)
  return baseScenes.value.slice(0, sceneCount).map((scene) => scene.id)
})

const sceneSvg = computed(() => {
  const content = currentScene.value?.content || {}
  return (content.svg as string) || ''
})

const sceneMarkdown = computed(() => {
  const content = currentScene.value?.content || {}
  return (content.markdown as string) || ''
})

const sceneMarkmapMd = computed(() => {
  const content = currentScene.value?.content || {}
  return (content.markmap_md as string) || ''
})

const questions = computed(() => {
  const content = currentScene.value?.content || {}
  return ((content.questions as InteractiveClassroomQuestion[]) || [])
})

const resultByQuestion = computed(() => {
  const rows: Record<string, QuizSubmitResult['results'][number]> = {}
  for (const row of currentQuizResult.value?.results || []) rows[row.question_id] = row
  return rows
})

const currentAnswers = computed(() => {
  const sceneId = currentScene.value?.id || ''
  return answersByScene.value[sceneId] || {}
})

const currentQuizResult = computed(() => {
  const sceneId = currentScene.value?.id || ''
  return quizResultsByScene.value[sceneId] || null
})

const allAnswered = computed(() => {
  if (!questions.value.length) return false
  return questions.value.every((q) => {
    const ans = currentAnswers.value[q.id] || []
    if (q.type === 'short_answer') {
      const text = ans[0] || ''
      return text.trim().length > 0
    }
    return ans.length > 0
  })
})

const feedbackText = computed(() => currentQuizResult.value?.feedback_action?.text || '')

const reportKnowledgeRows = computed(() => {
  const summary = report.value?.knowledge_summary || {}
  return Object.entries(summary).map(([name, row]) => ({ name, mastery: row.mastery }))
})

const reportRecommendedTasks = computed(() => report.value?.recommended_tasks || [])

const quizSceneIds = computed(() =>
  baseScenes.value.filter((scene) => scene.type === 'quiz').map((scene) => scene.id),
)

const answeredQuizCount = computed(() => {
  const localCount = quizSceneIds.value.filter((sceneId) => Boolean(quizResultsByScene.value[sceneId])).length
  return Math.max(localCount, report.value?.answered_quiz_count || 0)
})

const answeredSceneIds = computed(() => {
  const localIds = Object.keys(quizResultsByScene.value)
  const persistedIds = report.value?.answered_scene_ids || []
  return Array.from(new Set([...persistedIds, ...localIds]))
})

const isClassroomComplete = computed(() => {
  if (quizSceneIds.value.length === 0) return true
  return answeredQuizCount.value === quizSceneIds.value.length
})

const canOpenReportScene = computed(() => {
  if (quizSceneIds.value.length === 0) return true
  return answeredQuizCount.value === quizSceneIds.value.length
})

const discussionActive = computed(() => discussionSubmitting.value || discussionMessages.value.length > 0)

const lastContentSceneIndex = computed(() => Math.max(0, baseScenes.value.length - 1))

const sceneKindLabel = computed(() => {
  if (currentScene.value?.type === 'quiz') return '课堂互动'
  if (currentScene.value?.type === 'report') return '学习档案'
  return '教师讲解'
})

const playbackStatusText = computed(() => {
  if (discussionActive.value) return '讨论中，等待手动翻页'
  if (!autoPlayEnabled.value) return '手动播放'
  if (currentScene.value?.type === 'quiz') return currentQuizResult.value ? '反馈后自动继续' : '测验暂停'
  if (currentIndex.value >= orderedScenes.value.length - 1) return '最后一页'
  return '自动播放'
})

const currentSpeechText = computed(() => {
  return currentSpeechAction.value?.text || ''
})

const currentSpeechParagraphs = computed(() => buildSpeechParagraphs(currentSpeechText.value, sceneHighlightCues.value))

const activeSpeechParagraphIdx = computed(() => (
  activeSpeechParagraphIndex(currentSpeechParagraphs.value, currentAudioTime.value, audioDuration.value)
))

const currentAudioUrl = computed(() => {
  const audioUrl = currentSpeechAction.value?.audio_url || ''
  if (!audioUrl) return ''
  const joiner = audioUrl.includes('?') ? '&' : '?'
  return `${audioUrl}${joiner}user_id=${encodeURIComponent(getUserId())}`
})

const currentSpeechAction = computed(() => {
  const actions = currentScene.value?.actions || []
  return actions.find((a) => a.type === 'quiz_feedback') || actions.find((a) => a.type === 'speech') || null
})

const rawSceneHighlightTargets = computed<HighlightTarget[]>(() => {
  const rows = currentScene.value?.content?.highlight_targets
  if (Array.isArray(rows) && rows.length) {
    return rows
      .map((row): HighlightTarget | null => {
        if (!row || typeof row !== 'object') return null
        const item = row as Record<string, any>
        const box = item.bbox || {}
        const target = {
          id: String(item.id || ''),
          text: String(item.text || ''),
          kind: String(item.kind || 'text'),
          bbox: {
            x: Number(box.x),
            y: Number(box.y),
            width: Number(box.width),
            height: Number(box.height),
          },
        }
        if (!target.id || !Number.isFinite(target.bbox.x) || target.bbox.width <= 0 || target.bbox.height <= 0) return null
        return target
      })
      .filter((row): row is HighlightTarget => Boolean(row))
  }
  return []
})

const sceneHighlightTargets = computed<HighlightTarget[]>(() => {
  if (currentScene.value?.type !== 'slide') return []
  if (measuredHighlightTargets.value.length) return measuredHighlightTargets.value
  if (rawSceneHighlightTargets.value.length) return rawSceneHighlightTargets.value
  return fallbackHighlightTargets.value
})

const sceneHighlightCues = computed<HighlightCue[]>(() => {
  if (currentScene.value?.type !== 'slide') return []
  const payloadCues = currentSpeechAction.value?.payload?.highlight_cues
  const normalized = normalizeHighlightCues(payloadCues)
  if (normalized.length) return normalized
  if (!sceneHighlightTargets.value.length) return []
  const total = sceneHighlightTargets.value.length
  return sceneHighlightTargets.value.map((target, idx) => ({
    target_id: target.id,
    start_ratio: idx / total,
    end_ratio: (idx + 1) / total,
    mode: idx === 0 ? 'spotlight' : 'outline',
    label: target.text,
  }))
})

const activeHighlight = computed(() => {
  const cue = activeHighlightCue(sceneHighlightCues.value, currentAudioTime.value, audioDuration.value)
  if (!cue) return null
  const target = sceneHighlightTargets.value.find((item) => item.id === cue.target_id)
  if (!target) return null
  return {
    cue,
    target,
    mode: activeHighlightMode(cue, currentAudioTime.value, audioDuration.value),
  }
})

const highlightLayerStyle = computed<CSSProperties | null>(() => {
  const metrics = svgMetrics.value
  if (!metrics) return null
  return {
    left: `${metrics.left}px`,
    top: `${metrics.top}px`,
    width: `${metrics.width}px`,
    height: `${metrics.height}px`,
  }
})

const highlightBoxStyle = computed<CSSProperties | null>(() => {
  if (!activeHighlight.value || !svgMetrics.value) return null
  const { target } = activeHighlight.value
  const metrics = svgMetrics.value
  const scaleX = metrics.width / metrics.viewWidth
  const scaleY = metrics.height / metrics.viewHeight
  const pad = activeHighlight.value.mode === 'spotlight' ? 8 : 5
  const left = Math.max(0, target.bbox.x * scaleX - pad)
  const top = Math.max(0, target.bbox.y * scaleY - pad)
  const width = Math.min(metrics.width - left, target.bbox.width * scaleX + pad * 2)
  const height = Math.min(metrics.height - top, target.bbox.height * scaleY + pad * 2)
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.max(12, width)}px`,
    height: `${Math.max(12, height)}px`,
  }
})

function refreshSvgHighlightMetrics() {
  const stage = svgStageRef.value
  const svg = svgBoxRef.value?.querySelector('svg') as SVGSVGElement | null
  if (!stage || !svg) {
    fallbackHighlightTargets.value = []
    measuredHighlightTargets.value = []
    svgMetrics.value = null
    return
  }

  fallbackHighlightTargets.value = fallbackHighlightTargetsFromSvgElement(svg)
  measuredHighlightTargets.value = resolveHighlightTargetsFromSvgElement(rawSceneHighlightTargets.value, svg)

  const stageRect = stage.getBoundingClientRect()
  const svgRect = svg.getBoundingClientRect()
  const viewBox = svg.viewBox?.baseVal
  const viewWidth = viewBox?.width || Number(svg.getAttribute('width')) || svgRect.width
  const viewHeight = viewBox?.height || Number(svg.getAttribute('height')) || svgRect.height
  if (!svgRect.width || !svgRect.height || !viewWidth || !viewHeight) {
    svgMetrics.value = null
    return
  }

  svgMetrics.value = {
    left: svgRect.left - stageRect.left,
    top: svgRect.top - stageRect.top,
    width: svgRect.width,
    height: svgRect.height,
    viewWidth,
    viewHeight,
  }
}

function setAnswer(questionId: string, value: string) {
  const sceneId = currentScene.value?.id
  if (!sceneId) return
  const question = questions.value.find((item) => item.id === questionId)
  const prevAnswers = answersByScene.value[sceneId] || {}
  const prevValues = prevAnswers[questionId] || []
  // 简答题：value 就是用户输入的整段文本，覆盖式赋值
  if (question?.type === 'short_answer') {
    answersByScene.value = {
      ...answersByScene.value,
      [sceneId]: {
        ...prevAnswers,
        [questionId]: [value],
      },
    }
    return
  }
  const nextValues = question?.type === 'multiple'
    ? (
        prevValues.includes(value)
          ? prevValues.filter((item) => item !== value)
          : [...prevValues, value].sort()
      )
    : [value]
  answersByScene.value = {
    ...answersByScene.value,
    [sceneId]: {
      ...prevAnswers,
      [questionId]: nextValues,
    },
  }
}

function onShortAnswerInput(questionId: string, event: Event) {
  const value = (event.target as HTMLTextAreaElement).value
  setAnswer(questionId, value)
}

function optionClass(questionId: string, value: string) {
  const result = resultByQuestion.value[questionId]
  const selected = (currentAnswers.value[questionId] || []).includes(value)
  return {
    selected,
    correct: result?.correct_answer.includes(value),
    wrong: Boolean(result && selected && !result.correct_answer.includes(value)),
  }
}

function isCorrectOption(questionId: string, value: string) {
  return Boolean(resultByQuestion.value[questionId]?.correct_answer.includes(value))
}

function isWrongSelectedOption(questionId: string, value: string) {
  const result = resultByQuestion.value[questionId]
  return Boolean(result && (currentAnswers.value[questionId] || []).includes(value) && !result.correct_answer.includes(value))
}

function clearAdvanceTimer() {
  if (advanceTimer.value !== null) {
    window.clearTimeout(advanceTimer.value)
    advanceTimer.value = null
  }
}

function shouldAutoAdvance() {
  if (discussionActive.value) return false
  if (currentScene.value?.type === 'report') return false
  // 测验场景：答题结束后不再自动跳转，让用户自行查看解析后手动翻页
  if (currentScene.value?.type === 'quiz') return false

  return Boolean(
    autoPlayEnabled.value
      && currentIndex.value < lastContentSceneIndex.value,
  )
}

function sendQuestionToDiscussion(q: InteractiveClassroomQuestion) {
  if (!discussionRef.value) return
  const result = quizResultsByScene.value[currentScene.value?.id ?? '']?.results.find(
    (r) => r.question_id === q.id,
  )
  const analysis = result?.analysis || q.analysis || '（暂无解析）'
  const yourAnswer = result?.your_answer?.join('、') || '（未作答）'
  const correctAnswer = result?.correct_answer?.join('、') || q.answer?.join('、') || '（未知）'
  const text = [
    `题目：${q.question}`,
    `我的答案：${yourAnswer}`,
    `正确答案：${correctAnswer}`,
    `解析：${analysis}`,
    `能再详细讲讲吗？`,
  ].join('\n')
  discussionRef.value.submitDraft(text)
}

function syncDiscussionPersistence() {
  if (!classroom.value || !currentScene.value || currentScene.value.type === 'report') return
  savePersistedDiscussionMessages(classroom.value.id, currentScene.value.id, discussionMessages.value)
}

function clearDiscussionHistory() {
  if (!classroom.value || !currentScene.value || currentScene.value.type === 'report') return
  discussionMessages.value = []
  discussionSubmitting.value = false
  clearPersistedDiscussionMessages(classroom.value.id, currentScene.value.id)
}

function confirmClearDiscussionHistory() {
  if (!discussionMessages.value.length) return
  dialog.warning({
    title: '清空互动讨论记录',
    content: '只清除当前课堂当前场景的 AI 互动讨论记录，操作后无法恢复，是否继续？',
    positiveText: '确认清空',
    negativeText: '取消',
    onPositiveClick: () => {
      clearDiscussionHistory()
      message.success('已清空当前场景的讨论记录')
    },
  })
}

function restoreDiscussionForCurrentScene() {
  if (!classroom.value || !currentScene.value || currentScene.value.type === 'report') {
    discussionMessages.value = []
    discussionSubmitting.value = false
    return
  }
  discussionMessages.value = loadPersistedDiscussionMessages(classroom.value.id, currentScene.value.id) || []
  discussionSubmitting.value = false
}

function scheduleAutoAdvance(delay = 900) {
  clearAdvanceTimer()
  if (!shouldAutoAdvance()) return
  advanceTimer.value = window.setTimeout(() => {
    advanceTimer.value = null
    if (shouldAutoAdvance()) goNext()
  }, delay)
}

function selectScene(idx: number) {
  const target = orderedScenes.value[idx]
  if (target?.type === 'report' && !canOpenReportScene.value) {
    message.warning('完成所有随堂测验后才能查看学习报告')
    return
  }
  clearAdvanceTimer()
  currentIndex.value = idx
  if (target?.type === 'report') {
    showReport().catch(() => undefined)
  }
  // P7: 复听 — 用户重新进入已访问过的 slide 场景
  if (target && target.type === 'slide' && classroom.value) {
    if (visitedSceneIds.value.has(target.id)) {
      emitSceneReviewed(classroom.value.id, target).catch(() => undefined)
    }
    visitedSceneIds.value = new Set([...visitedSceneIds.value, target.id])
  }
}

function goPrev() {
  if (currentIndex.value > 0) selectScene(currentIndex.value - 1)
}

function goNext() {
  if (currentIndex.value < orderedScenes.value.length - 1) selectScene(currentIndex.value + 1)
}

function goBackToList() {
  router.push({ name: 'interactive-classroom-home' })
}

function toggleAutoPlay() {
  autoPlayEnabled.value = !autoPlayEnabled.value
  if (autoPlayEnabled.value) {
    // 开启自动播放时立即尝试播放当前音频（quiz 场景反馈也能播）
    audioRef.value?.play().catch(() => {})
  } else {
    audioRef.value?.pause()
  }
}

function handleAudioEnded() {
  if (discussionActive.value) return
  // 测验场景：音频播放完后不自动跳转，让用户自行查看解析
  if (currentScene.value?.type === 'quiz') return
  if (currentIndex.value === lastContentSceneIndex.value && isClassroomComplete.value && canOpenReportScene.value) {
    showReportAfterClassroomEnd()
    return
  }
  scheduleAutoAdvance()
}

async function requestDiscussion(trigger: string, payload: { content?: string; quickAction?: string }) {
  if (!classroom.value) return
  const nextMessages = [...discussionMessages.value]
  const requestNonce = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const userMessageId = `discussion_user_${requestNonce}`
  const singleAgentMessageId = `discussion_single_${requestNonce}`
  if (payload.content) {
    nextMessages.push({ role: 'user', content: payload.content, message_id: userMessageId })
  } else if (payload.quickAction) {
    nextMessages.push({ role: 'user', content: payload.quickAction, message_id: userMessageId })
  }

  const baseRequest = {
    played_scene_ids: playedSceneIds.value,
    current_scene_id: currentScene.value?.id,
    messages: nextMessages,
    trigger,
    quick_action: payload.quickAction,
    multi_agent: multiAgentDiscussionEnabled.value,
    ...buildClassroomDiscussionLlmPayload({
      settings: settingStore.settings,
      getEffectiveApiKey: () => settingStore.getEffectiveApiKey(),
      getEffectiveBaseUrl: () => settingStore.getEffectiveBaseUrl(),
      getProviderType: () => settingStore.getProviderType(),
    }),
  }

  // 不 upfront 推空 assistant — 让"正在思考"指示器独占显示，
  // 等第一个 chunk 到达时再推 assistant 消息（带内容推，避免出现空泡）
  discussionMessages.value = nextMessages
  discussionSubmitting.value = true

  function scopeAssistantMessage(message: ClassroomDiscussionMessage): ClassroomDiscussionMessage {
    return {
      ...message,
      message_id: scopeDiscussionMessageId(requestNonce, message.message_id),
    }
  }

  function pushOrReplaceAssistant(content: string) {
    discussionMessages.value = upsertDiscussionAssistantMessage(discussionMessages.value, {
      message_id: scopeDiscussionMessageId(requestNonce, singleAgentMessageId),
      content,
      trigger,
      agent_id: 'teacher',
      agent_name: 'AI 教师',
    })
  }

  let accumulated = ''
  try {
    for await (const ev of discussInteractiveClassroomStream(classroom.value.id, baseRequest)) {
      if (ev.error) throw new Error(ev.error)
      if (ev.done) break
      const scopedEvent = {
        ...ev,
        message_id: scopeDiscussionMessageId(requestNonce, ev.message_id),
      }
      if (ev.type === 'agent_start') {
        discussionMessages.value = applyDiscussionAgentEvent(discussionMessages.value, scopedEvent, trigger)
        continue
      }
      if (ev.type === 'agent_chunk' || ev.type === 'agent_done') {
        accumulated += ev.chunk || ev.content || ''
        discussionMessages.value = applyDiscussionAgentEvent(discussionMessages.value, scopedEvent, trigger)
        continue
      }
      if (ev.chunk) {
        accumulated += ev.chunk
        pushOrReplaceAssistant(accumulated)
      }
    }
    // 流结束但内容仍为空 → fallback 到非流式接口
    if (!accumulated) {
      const result = await discussInteractiveClassroom(classroom.value.id, baseRequest)
      if (result.assistant_messages?.length) {
        discussionMessages.value = [...nextMessages, ...result.assistant_messages.map(scopeAssistantMessage)]
      } else {
        pushOrReplaceAssistant(result.assistant_message.content)
      }
    }
  } catch (err) {
    // 异常时尝试降级到非流式接口
    try {
      const result = await discussInteractiveClassroom(classroom.value.id, baseRequest)
      if (result.assistant_messages?.length) {
        discussionMessages.value = [...nextMessages, ...result.assistant_messages.map(scopeAssistantMessage)]
      } else {
        pushOrReplaceAssistant(result.assistant_message.content)
      }
    } catch (fallbackErr) {
      message.error(fallbackErr instanceof Error ? fallbackErr.message : '讨论发起失败')
      // 失败时回滚到 user 消息的状态
      discussionMessages.value = [...nextMessages]
    }
  } finally {
    discussionSubmitting.value = false
  }
}

async function handleDiscussionSubmit(content: string) {
  await requestDiscussion('manual', { content })
}

async function handleDiscussionQuickAction(action: string) {
  await requestDiscussion('manual', { quickAction: action })
}

function resetQuiz() {
  const sceneId = currentScene.value?.id
  if (!sceneId) return
  const { [sceneId]: _answers, ...restAnswers } = answersByScene.value
  const { [sceneId]: _result, ...restResults } = quizResultsByScene.value
  answersByScene.value = restAnswers
  quizResultsByScene.value = restResults
  reportAutoShown.value = false
  report.value = null
}

function applyFeedbackAction(action?: InteractiveClassroomAction) {
  if (!action || !classroom.value || !currentScene.value) return
  const sceneId = currentScene.value.id
  // 必须替换 classroom 对象而不是深层次 mutate（classroom 是 ref，
  // 对嵌套属性赋值不触发响应式，会导致 currentAudioUrl 不会重算，
  // audio 元素继续显示原 speech URL 而非新反馈音频）
  classroom.value = {
    ...classroom.value,
    scenes: classroom.value.scenes.map((scene) => {
      if (scene.id !== sceneId) return scene
      return {
        ...scene,
        actions: [
          ...(scene.actions || []).filter((item) => item.type !== 'quiz_feedback'),
          action,
        ],
      }
    }),
  }
}

async function submitQuiz() {
  if (!classroom.value || !currentScene.value) return
  submitting.value = true
  try {
    const result = await submitInteractiveClassroomAnswer(
      classroom.value.id,
      currentScene.value.id,
      currentAnswers.value,
      {
        tts_provider: settingStore.settings.tts_provider,
        tts_model: settingStore.settings.tts_model,
        tts_voice: settingStore.settings.tts_voice,
        tts_api_key: settingStore.getEffectiveTTSApiKey(),
        tts_base_url: settingStore.getEffectiveTTSBaseUrl(),
        // P1-3: 简答题需要 content LLM 评分；后端只在含 short_answer 时才读
        content_model: settingStore.settings.content_model,
        content_api_key: settingStore.getEffectiveContentApiKey(),
        content_base_url: settingStore.getEffectiveContentBaseUrl(),
        content_provider_type: settingStore.getContentProviderType(),
      },
    )
    quizResultsByScene.value = {
      ...quizResultsByScene.value,
      [currentScene.value.id]: result,
    }
    applyFeedbackAction(result.feedback_action)
    if (result.feedback_action?.text) {
      message.success(result.feedback_action.text)
    }
    report.value = null
    // 不再自动跳转到报告，由用户手动控制翻页
  } catch (err) {
    message.error(err instanceof Error ? err.message : '提交失败')
  } finally {
    submitting.value = false
  }
}

async function loadReport(silent = false) {
  if (!classroom.value) return
  reportLoading.value = true
  try {
    report.value = await getInteractiveClassroomReport(classroom.value.id)
  } catch (err) {
    if (!silent) message.error(err instanceof Error ? err.message : '报告生成失败')
  } finally {
    reportLoading.value = false
  }
}

async function showReport() {
  if (!canOpenReportScene.value) {
    message.warning('完成所有随堂测验后才能查看学习报告')
    return
  }
  if (report.value) return
  await loadReport()
}

async function showReportAfterClassroomEnd() {
  if (reportAutoShown.value) return
  if (!canOpenReportScene.value) return
  reportAutoShown.value = true
  await showReport()
  const reportIndex = orderedScenes.value.findIndex((scene) => scene.type === 'report')
  if (reportIndex >= 0) selectScene(reportIndex)
}

async function loadClassroom() {
  const classroomId = String(route.params.classroomId || '')
  if (!classroomId) return
  const loadVersion = ++classroomLoadVersion
  clearAdvanceTimer()
  classroom.value = null
  currentIndex.value = 0
  report.value = null
  answersByScene.value = {}
  quizResultsByScene.value = {}
  reportAutoShown.value = false
  classroomCompletedEmitted.value = false
  visitedSceneIds.value = new Set()
  discussionMessages.value = []
  discussionSubmitting.value = false
  try {
    const loadedClassroom = await getInteractiveClassroom(classroomId)
    if (loadVersion !== classroomLoadVersion) return
    classroom.value = loadedClassroom
    const restored = buildPlayerAnswerState(classroom.value)
    answersByScene.value = restored.answersByScene
    quizResultsByScene.value = restored.quizResultsByScene
    // P7: 标记初始场景为已访问
    const initialScene = orderedScenes.value[0]
    if (initialScene) visitedSceneIds.value = new Set([initialScene.id])
    await loadReport(true)
    // P7: 恢复状态后检查课堂是否已完成（watch 只响应变化，不响应初始值）
    if (isClassroomComplete.value && !classroomCompletedEmitted.value) {
      classroomCompletedEmitted.value = true
      emitClassroomCompleted(
        classroom.value.id,
        quizSceneIds.value.length,
        answeredQuizCount.value,
      ).catch(() => undefined)
    }
    if (route.query.scene === 'report') {
      await showReport()
      if (loadVersion !== classroomLoadVersion) return
      const reportIndex = orderedScenes.value.findIndex((scene) => scene.type === 'report')
      if (canOpenReportScene.value && reportIndex >= 0) currentIndex.value = reportIndex
    }
  } catch (err) {
    if (loadVersion !== classroomLoadVersion) return
    message.error(err instanceof Error ? err.message : '加载失败')
  }
}

onMounted(() => {
  window.addEventListener('resize', refreshSvgHighlightMetrics)
})

onBeforeUnmount(() => {
  classroomLoadVersion += 1
  clearAdvanceTimer()
  window.removeEventListener('resize', refreshSvgHighlightMetrics)
})

watch(
  () => route.params.classroomId,
  () => {
    loadClassroom().catch(() => undefined)
  },
  { immediate: true },
)

watch(
  () => [currentScene.value?.id, sceneSvg.value],
  async () => {
    fallbackHighlightTargets.value = []
    measuredHighlightTargets.value = []
    svgMetrics.value = null
    await nextTick()
    refreshSvgHighlightMetrics()
  },
  { flush: 'post' },
)

watch(
  () => [classroom.value?.id, currentScene.value?.id],
  () => {
    restoreDiscussionForCurrentScene()
  },
  { immediate: true },
)

watch(
  () => [currentScene.value?.id, activeSpeechParagraphIdx.value],
  async () => {
    await nextTick()
    syncSpeechParagraphScroll()
  },
  { flush: 'post' },
)

// 直接 watch ref 本身（比 `() => [a, b, ref.value]` 数组源 + deep 更可靠）
// — 流式期间 discussionMessages.value 每次 chunk 重新赋值，
// 函数式数组源 + deep 在 Vue 3 中对内部 ref 重新赋值的追踪有概率丢失事件
watch(
  discussionMessages,
  () => {
    syncDiscussionPersistence()
  },
  { deep: true },
)

watch(
  multiAgentDiscussionEnabled,
  (enabled) => {
    localStorage.setItem('ai_creator.classroom_discussion.multi_agent', String(enabled))
  },
)

// P7: 课堂完成事件
watch(
  isClassroomComplete,
  (complete) => {
    if (complete && !classroomCompletedEmitted.value && classroom.value) {
      classroomCompletedEmitted.value = true
      emitClassroomCompleted(
        classroom.value.id,
        quizSceneIds.value.length,
        answeredQuizCount.value,
      ).catch(() => undefined)
    }
  },
)

watch(
  () => [currentScene.value?.id, currentAudioUrl.value, autoPlayEnabled.value, currentQuizResult.value?.score],
  async () => {
    clearAdvanceTimer()
    if (!autoPlayEnabled.value) return

    const isQuiz = currentScene.value?.type === 'quiz'

    if (!currentAudioUrl.value) {
      // 无音频：只有非 quiz 场景才自动跳转
      if (isQuiz) return
      if (currentIndex.value === lastContentSceneIndex.value && isClassroomComplete.value && canOpenReportScene.value) {
        window.setTimeout(() => {
          showReportAfterClassroomEnd().catch(() => undefined)
        }, 3500)
        return
      }
      scheduleAutoAdvance(5000)
      return
    }

    // 有音频：尝试播放（包括 quiz 场景的反馈音频）
    await nextTick()
    try {
      await audioRef.value?.play()
    } catch {
      // 浏览器可能在首次用户交互前拦截自动播放，此时保留原生控件供手动播放。
    }
  },
  { flush: 'post' },
)

function formatSceneTitle(scene: InteractiveClassroomScene): string {
  const rawTitle = scene.title || ''
  // 跳过默认占位标题：page 1、slide 1、第 1 页、1 等
  if (rawTitle && !/^(page|slide|p|s)\s*\d+$/i.test(rawTitle) && !/^第\s*\d+\s*页?$/.test(rawTitle) && !/^\d+$/.test(rawTitle)) {
    return rawTitle
  }
  const speech = scene.actions?.find((a) => a.type === 'speech')?.text || ''
  if (speech) {
    const clean = speech.replace(/^这一页的主题是[“\"]/, '').replace(/[”\"]。.*/, '').trim()
    if (clean.length >= 2 && clean.length <= 20) return clean
    const firstSentence = speech.split(/[。.!?！？]/)[0].trim()
    if (firstSentence.length >= 2 && firstSentence.length <= 20) return firstSentence
    if (firstSentence.length > 20) return firstSentence.slice(0, 18) + '...'
  }
  const kp = scene.knowledge_points?.[0]
  if (kp && kp.length >= 2 && kp.length <= 20) return kp
  if (kp && kp.length > 20) return kp.slice(0, 18) + '...'
  return rawTitle || '课堂内容'
}

function sceneTypeLabel(type: string) {
  if (type === 'quiz') return '测验'
  if (type === 'mindmap') return '知识结构'
  if (type === 'report') return canOpenReportScene.value ? '报告' : '未解锁'
  return '讲解'
}

function taskPriorityLabel(priority: string) {
  if (priority === 'high') return '优先'
  if (priority === 'medium') return '建议'
  return '拓展'
}

function getTaskAction(task: ClassroomRecommendedTask) {
  return resolveReportTaskAction(task, {
    orderedScenes: orderedScenes.value.map((scene) => ({ id: scene.id, type: scene.type })),
    answeredSceneIds: answeredSceneIds.value,
    topic: classroom.value?.topic || '',
    course: classroom.value?.course || classroom.value?.topic || '',
    studentProfile: classroom.value?.student_profile || {},
    report: report.value,
  })
}

function canRunTask(task: ClassroomRecommendedTask) {
  return getTaskAction(task).kind !== 'none'
}

function taskButtonLabel(task: ClassroomRecommendedTask) {
  if (runningTaskId.value === task.id) return '正在生成...'
  return canRunTask(task) ? task.action_label : `${task.action_label}（待开放）`
}

async function runTask(task: ClassroomRecommendedTask) {
  // P7: 记录任务点击事件
  if (classroom.value) {
    emitRecommendedTaskOpened(
      classroom.value.id,
      task.id,
      task.type,
      task.knowledge_points,
    ).catch(() => undefined)
  }

  const action = getTaskAction(task)
  if (action.kind === 'scene') {
    const targetIndex = orderedScenes.value.findIndex((scene) => scene.id === action.sceneId)
    if (targetIndex >= 0) {
      selectScene(targetIndex)
      return
    }
    message.warning('目标课堂场景不存在')
    return
  }

  if (action.kind === 'ppt-studio') {
    await router.push({ name: 'ppt-studio', query: action.query })
    return
  }

  if (action.kind === 'practice' && classroom.value) {
    runningTaskId.value = task.id
    try {
      const practice = await createClassroomPractice(
        classroom.value.id,
        action.taskId,
        action.taskType,
      )
      await router.push({
        name: 'interactive-classroom-player',
        params: { classroomId: practice.id },
      })
    } catch (error) {
      message.error(error instanceof Error ? error.message : '练习生成失败')
    } finally {
      runningTaskId.value = ''
    }
    return
  }

  message.info('该学习任务的自动执行链路还未接入')
}
</script>

<style scoped>
.player {
  height: 100%;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 360px;
  min-height: 0;
  background: rgb(var(--bg-base-rgb));
}

.scene-list {
  border-right: 1px solid rgb(var(--line-rgb));
  padding: 12px;
  overflow: auto;
  background: rgb(var(--bg-surface-rgb));
}

.scene-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 2px 12px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 10px 0 6px;
  margin: -4px 0 6px;
  border: 0;
  background: transparent;
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 8px;
  transition: color 0.15s ease, background 0.15s ease;
}

.back-btn:hover {
  color: rgb(var(--ink-1-rgb));
  background: rgba(15, 23, 42, 0.05);
}

.back-icon {
  width: 16px;
  height: 16px;
}

.scene-list-title {
  font-size: 14px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}

.scene-list-meta {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.scene-btn {
  width: 100%;
  min-height: 56px;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 9px;
  background: transparent;
  margin-bottom: 6px;
  cursor: pointer;
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 8px;
  align-items: center;
}

.scene-btn:hover,
.scene-btn.active {
  background: rgb(var(--bg-subtle-rgb));
  border-color: rgb(var(--line-rgb));
}

.scene-btn.locked {
  opacity: 0.55;
}

.scene-btn.locked:hover {
  background: transparent;
}

.scene-index {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
}

.scene-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.scene-title {
  font-size: 13px;
  color: rgb(var(--ink-1-rgb));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-type {
  font-size: 11px;
  color: rgb(var(--ink-3-rgb));
}

.stage {
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
}

.stage-header {
  min-height: 70px;
  padding: 14px 18px;
  border-bottom: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.stage-header h1 {
  margin: 0;
  font-size: 20px;
}

.topic {
  margin-top: 4px;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
}

.stage-actions {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.text-btn {
  height: 36px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  padding: 0 12px;
  cursor: pointer;
}

.text-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-btn.active {
  border-color: rgb(16 185 129 / 0.5);
  background: rgb(16 185 129 / 0.08);
  color: rgb(5 150 105);
}

.icon {
  width: 16px;
  height: 16px;
}

.scene-body {
  flex: 1;
  overflow: auto;
  padding: 18px;
}

.svg-stage {
  position: relative;
  display: flex;
  justify-content: center;
  width: 100%;
  max-width: 100%;
}

.svg-box {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: min(100%, 920px);
  max-width: 100%;
  box-sizing: border-box;
}

.svg-box :deep(svg) {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: 56vh;
}

.highlight-layer {
  position: absolute;
  pointer-events: none;
  overflow: hidden;
}

.highlight-box,
.highlight-spotlight {
  position: absolute;
  border-radius: 7px;
  transition: left 220ms var(--ease-out), top 220ms var(--ease-out), width 220ms var(--ease-out), height 220ms var(--ease-out);
}

.highlight-box {
  border: 2px solid #2D5016;
  background: rgba(45, 80, 22, 0.08);
  box-shadow: 0 8px 22px rgba(45, 80, 22, 0.14);
  animation: highlight-breathe 1.9s ease-in-out infinite;
  transition:
    left 220ms var(--ease-out),
    top 220ms var(--ease-out),
    width 220ms var(--ease-out),
    height 220ms var(--ease-out),
    background-color 220ms ease-out,
    box-shadow 240ms ease-out,
    border-color 220ms ease-out;
}

.highlight-box.spotlight {
  background: rgba(255, 255, 255, 0.04);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.75), 0 10px 28px rgba(45, 80, 22, 0.22);
  animation: highlight-spotlight-enter 260ms ease-out;
}

.highlight-spotlight {
  box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.14);
  animation: highlight-spotlight-fade 320ms ease-out;
}

.spotlight-mask-enter-active,
.spotlight-mask-leave-active {
  transition: opacity 240ms ease-out;
}

.spotlight-mask-enter-from,
.spotlight-mask-leave-to {
  opacity: 0;
}

.spotlight-mask-enter-to,
.spotlight-mask-leave-from {
  opacity: 1;
}

@keyframes highlight-breathe {
  0%, 100% {
    border-color: rgba(45, 80, 22, 0.75);
    box-shadow: 0 6px 18px rgba(45, 80, 22, 0.10), 0 0 0 0 rgba(45, 80, 22, 0.14);
  }
  50% {
    border-color: rgba(45, 80, 22, 1);
    box-shadow: 0 10px 24px rgba(45, 80, 22, 0.16), 0 0 0 5px rgba(45, 80, 22, 0.08);
  }
}

@keyframes highlight-spotlight-enter {
  0% {
    transform: scale(0.985);
    opacity: 0.78;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes highlight-spotlight-fade {
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}

.md-box {
  margin: 0;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  padding: 14px;
  white-space: pre-wrap;
}

.mindmap-wrap {
  width: 100%;
  min-height: 360px;
  display: flex;
  flex-direction: column;
}

.quiz-wrap {
  max-width: 880px;
  display: grid;
  gap: 14px;
}

.question-card {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  padding: 14px;
  display: grid;
  gap: 12px;
}

.question-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.question-index {
  width: 34px;
  height: 24px;
  border-radius: 7px;
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-2-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.q-title {
  font-size: 15px;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.6;
}

.question-type-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  color: var(--nav-ppt, #4338ca);
  background: rgba(67, 56, 202, 0.08);
  vertical-align: middle;
}

.short-answer-area {
  display: grid;
  gap: 6px;
}

.short-answer-input {
  width: 100%;
  min-height: 120px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-1-rgb));
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.7;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 150ms var(--ease-out), box-shadow 150ms var(--ease-out);
}

.short-answer-input::placeholder {
  color: rgb(var(--ink-3-rgb));
}

.short-answer-input:focus {
  border-color: rgba(67, 56, 202, 0.45);
  box-shadow: 0 0 0 3px rgba(67, 56, 202, 0.08);
}

.short-answer-input:disabled {
  background: rgb(var(--bg-subtle-rgb));
  cursor: not-allowed;
  opacity: 0.9;
}

.short-answer-hint {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
  line-height: 1.5;
}

.option-list {
  display: grid;
  gap: 8px;
}

.option-btn {
  min-height: 42px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-2-rgb));
  padding: 9px 10px;
  text-align: left;
  display: grid;
  grid-template-columns: 28px 1fr 20px;
  gap: 9px;
  align-items: center;
  cursor: pointer;
}

.option-btn.selected {
  border-color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.option-btn.correct {
  border-color: rgb(16 185 129 / 0.55);
  background: rgb(16 185 129 / 0.08);
}

.option-btn.wrong {
  border-color: rgb(220 38 38 / 0.5);
  background: rgb(220 38 38 / 0.07);
}

.option-key {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: rgb(var(--bg-surface-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: rgb(var(--ink-2-rgb));
}

.option-text {
  min-width: 0;
  font-size: 14px;
  line-height: 1.5;
}

.option-icon.good {
  color: rgb(16 185 129);
}

.option-icon.bad {
  color: rgb(220 38 38);
}

.analysis-box,
.result-box {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  padding: 12px;
}

.analysis-title {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  margin-bottom: 5px;
}

.analysis-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.short-answer-score {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: rgb(15 118 110);
  background: rgba(15, 118, 110, 0.08);
  font-variant-numeric: tabular-nums;
}

.analysis-muted {
  color: rgb(var(--ink-3-rgb));
  font-size: 12.5px;
}

.analysis-copy,
.result-tip {
  font-size: 13px;
  line-height: 1.6;
  color: rgb(var(--ink-3-rgb));
}

.analysis-to-discussion {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  padding: 6px 10px;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
}

.analysis-to-discussion:hover {
  border-color: rgb(var(--nav-classroom-rgb, 15 118 110) / 0.4);
  color: #0f766e;
  background: var(--nav-classroom-bg, rgb(var(--bg-base-rgb)));
}

.analysis-to-discussion-icon {
  width: 14px;
  height: 14px;
}

.quiz-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}

.quiz-actions .primary-btn,
.quiz-actions .secondary-btn {
  padding: 0 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.primary-btn,
.secondary-btn {
  height: 38px;
  border-radius: 8px;
  padding: 0 14px;
  cursor: pointer;
}

.primary-btn {
  border: 0;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
}

.secondary-btn {
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  color: rgb(var(--ink-2-rgb));
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.result-box {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.score-ring {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
}

.result-summary {
  font-size: 14px;
  color: rgb(var(--ink-1-rgb));
  margin-bottom: 4px;
}

.narrator {
  padding: 8px 18px 12px;
  background: transparent;
}

.narrator-card {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04);
}

.narrator-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-page {
  width: min(1080px, 100%);
  margin: 0 auto;
}

.report-empty,
.report-sheet {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  padding: 18px;
}

.report-sheet {
  display: grid;
  gap: 16px;
}

.report-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 18px;
  align-items: stretch;
  border-bottom: 1px solid rgb(var(--line-rgb));
  padding-bottom: 16px;
}

.report-kicker {
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.report-hero h3,
.report-empty h3 {
  margin: 6px 0 0;
  color: rgb(var(--ink-1-rgb));
  font-size: 24px;
}

.report-hero p,
.muted-copy {
  margin: 8px 0 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
  line-height: 1.7;
}

.report-score-card {
  border-radius: 8px;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  padding: 16px;
  display: grid;
  align-content: center;
  gap: 4px;
}

.report-score-card span {
  font-size: 12px;
  opacity: 0.78;
}

.report-score-card strong {
  font-size: 36px;
  line-height: 1;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.report-metric {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  padding: 10px;
  display: grid;
  gap: 4px;
}

.report-metric span,
.report-label {
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
}

.report-metric strong {
  color: rgb(var(--ink-1-rgb));
  font-size: 16px;
}

.report-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.report-block {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-base-rgb));
  padding: 12px;
  display: grid;
  gap: 8px;
}

.tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tag {
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
}

.tag.weak {
  background: rgb(220 38 38 / 0.08);
  color: rgb(185 28 28);
}

.tag.strong {
  background: rgb(16 185 129 / 0.10);
  color: rgb(5 150 105);
}

.tag.task-point {
  background: rgb(15 23 42 / 0.06);
  color: rgb(var(--ink-2-rgb));
}

.mastery-list {
  display: grid;
  gap: 8px;
}

.mastery-row {
  display: grid;
  grid-template-columns: minmax(120px, 180px) 1fr 44px;
  gap: 10px;
  align-items: center;
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
}

.mastery-bar {
  height: 8px;
  border-radius: 999px;
  background: rgb(var(--bg-subtle-rgb));
  overflow: hidden;
}

.mastery-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: rgb(16 185 129);
}

.task-list {
  display: grid;
  gap: 10px;
}

.task-row {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  padding: 12px;
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}

.task-priority {
  border-radius: 8px;
  padding: 5px 8px;
  text-align: center;
  font-size: 12px;
  color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-subtle-rgb));
}

.task-priority.high {
  color: rgb(185 28 28);
  background: rgb(220 38 38 / 0.08);
}

.task-priority.medium {
  color: rgb(180 83 9);
  background: rgb(217 119 6 / 0.10);
}

.task-copy {
  min-width: 0;
  display: grid;
  gap: 7px;
}

.task-title {
  color: rgb(var(--ink-1-rgb));
  font-size: 14px;
  font-weight: 600;
}

.task-copy p {
  margin: 0;
  color: rgb(var(--ink-3-rgb));
  font-size: 13px;
  line-height: 1.7;
}

.task-action {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  padding: 6px 10px;
  color: rgb(var(--ink-2-rgb));
  background: rgb(var(--bg-base-rgb));
  font-size: 12px;
  white-space: nowrap;
}

.teacher-mark {
  display: flex;
  align-items: center;
  gap: 10px;
}

.teacher-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgb(var(--forest-pale-rgb));
  color: rgb(var(--forest-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 200ms var(--ease-out), transform 200ms var(--ease-out);
}

.teacher-avatar .icon {
  width: 16px;
  height: 16px;
}

.avatar-pulse {
  animation: avatarPulse 2s ease-in-out infinite;
}

@keyframes avatarPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(0.92); }
}

.teacher-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.teacher-name {
  font-size: 13px;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.2;
}

.play-status {
  align-self: flex-start;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 999px;
  padding: 2px 9px;
  color: rgb(var(--ink-3-rgb));
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  background: rgb(var(--bg-base-rgb));
}

.speech-text {
  position: relative;
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  line-height: 1.55;
  padding-left: 44px;
  max-height: 62px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: rgb(var(--line-rgb)) transparent;
}

.speech-segment {
  display: block;
  margin: 0 0 6px;
  padding: 4px 8px;
  border-radius: 8px;
  color: rgb(var(--ink-2-rgb));
  transition:
    background-color 220ms ease-out,
    color 220ms ease-out,
    opacity 220ms ease-out,
    transform 220ms ease-out;
}

.speech-segment:last-child {
  margin-bottom: 0;
}

.speech-segment.active {
  background: rgb(var(--nav-classroom-rgb, 15 118 110) / 0.12);
  color: rgb(var(--ink-1-rgb));
  transform: translateX(1px);
}

.speech-segment.inactive {
  opacity: 0.72;
}

.speech-text::after {
  content: "";
  position: sticky;
  display: block;
  bottom: 0;
  height: 16px;
  margin-top: -16px;
  background: linear-gradient(to bottom, transparent, rgb(var(--bg-surface-rgb)));
  pointer-events: none;
}

.audio-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: 44px;
  width: calc(100% - 44px);
  padding-top: 8px;
  border-top: 1px solid rgb(var(--line-rgb));
}

.audio-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.audio-play-btn {
  width: 32px;
  height: 28px;
  border-radius: 7px;
  border: none;
  background: rgb(var(--ink-1-rgb));
  color: rgb(var(--bg-surface-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 150ms var(--ease-out), transform 150ms var(--ease-out);
}

.audio-play-btn:hover {
  background: rgb(var(--ink-2-rgb));
  transform: scale(1.05);
}

.audio-play-btn:active {
  transform: scale(0.95);
}

.audio-play-icon {
  width: 14px;
  height: 14px;
}

.audio-time {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

.audio-time em {
  font-style: normal;
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
}

.audio-time i {
  font-style: normal;
  color: rgb(var(--ink-3-rgb));
  opacity: 0.5;
}

.audio-time span {
  color: rgb(var(--ink-3-rgb));
}

.audio-volume {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.audio-tool-btn {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-2-rgb));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 150ms var(--ease-out), color 150ms var(--ease-out), border-color 150ms var(--ease-out);
}

.audio-tool-btn:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--ink-3-rgb));
}

.audio-tool-icon {
  width: 13px;
  height: 13px;
}

.audio-slider {
  width: 60px;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgb(var(--line-rgb));
  border-radius: 999px;
  outline: none;
  cursor: pointer;
  padding: 0;
  margin: 0;
  flex-shrink: 0;
}

.audio-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: rgb(var(--ink-1-rgb));
  cursor: pointer;
  border: 2px solid rgb(var(--bg-surface-rgb));
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.audio-slider::-moz-range-thumb {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: rgb(var(--ink-1-rgb));
  cursor: pointer;
  border: 2px solid rgb(var(--bg-surface-rgb));
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.audio-rate {
  height: 28px;
  padding: 0 9px;
  border-radius: 7px;
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-base-rgb));
  color: rgb(var(--ink-2-rgb));
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  transition: background 150ms var(--ease-out), color 150ms var(--ease-out), border-color 150ms var(--ease-out);
}

.audio-rate:hover {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-1-rgb));
  border-color: rgb(var(--ink-3-rgb));
}

.loading {
  padding: 24px;
}

@media (max-width: 1480px) {
  .player {
    grid-template-columns: 220px minmax(0, 1fr) 320px;
  }
}

@media (max-width: 767px) {
  .player {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr auto;
  }

  .scene-list {
    border-right: 0;
    border-bottom: 1px solid rgb(var(--line-rgb));
    white-space: nowrap;
    overflow-x: auto;
  }

  .scene-list-head {
    display: none;
  }

  .scene-btn {
    display: inline-grid;
    width: min(240px, 78vw);
    margin-right: 8px;
    margin-bottom: 0;
  }

  .stage-header {
    align-items: flex-start;
  }

  .quiz-actions,
  .result-box {
    align-items: stretch;
    flex-direction: column;
  }

  .report-grid,
  .report-columns,
  .report-hero,
  .task-row,
  .mastery-row {
    grid-template-columns: 1fr;
  }

  .task-action {
    width: fit-content;
  }
}
</style>
