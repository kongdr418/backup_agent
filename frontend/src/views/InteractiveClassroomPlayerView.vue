<template>
  <div v-if="classroom && currentScene" class="player">
    <aside class="scene-list">
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
      <header class="stage-header">
        <div>
          <h1>{{ classroom.title }}</h1>
          <div class="topic">{{ classroom.topic }}</div>
        </div>
        <div class="stage-actions">
          <button
            class="icon-btn"
            :class="{ active: autoPlayEnabled }"
            :title="autoPlayEnabled ? '关闭自动播放' : '开启自动播放'"
            @click="toggleAutoPlay"
          >
            <PauseCircle v-if="autoPlayEnabled" class="icon" />
            <PlayCircle v-else class="icon" />
          </button>
          <button class="icon-btn" :disabled="currentIndex === 0" title="上一页" @click="goPrev">
            <ChevronLeft class="icon" />
          </button>
          <button
            class="icon-btn"
            :disabled="currentIndex >= orderedScenes.length - 1"
            title="下一页"
            @click="goNext"
          >
            <ChevronRight class="icon" />
          </button>
        </div>
      </header>

      <section class="scene-body">
        <div class="scene-title-row">
          <span class="scene-kind">{{ sceneKindLabel }}</span>
          <h2>{{ currentScene.title }}</h2>
        </div>

        <div v-if="currentScene.type === 'slide'" class="slide-wrap">
          <div v-if="sceneSvg" class="svg-box" v-html="sceneSvg" />
          <pre v-else class="md-box">{{ sceneMarkdown || '本页暂无内容' }}</pre>
        </div>

        <div v-else-if="currentScene.type === 'quiz'" class="quiz-wrap">
          <div v-for="(q, qIndex) in questions" :key="q.id" class="question-card">
            <div class="question-head">
              <span class="question-index">Q{{ qIndex + 1 }}</span>
              <div class="q-title">{{ q.question }}</div>
            </div>

            <div class="option-list">
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
              <div class="analysis-title">
                {{ resultByQuestion[q.id].correct ? '回答正确' : '还需要巩固' }}
              </div>
              <div class="analysis-copy">{{ resultByQuestion[q.id].analysis || '暂无解析' }}</div>
            </div>
          </div>

          <div class="quiz-actions">
            <button class="primary-btn" :disabled="submitting || !allAnswered" @click="submitQuiz">
              {{ submitting ? '提交中...' : '提交答案' }}
            </button>
            <button class="secondary-btn" :disabled="submitting" @click="resetQuiz">重做</button>
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
            <div class="speech-text">{{ currentSpeechText || '当前场景暂无讲解词' }}</div>
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
                  class="audio-play-btn"
                  :title="isAudioPlaying ? '暂停' : '播放'"
                  @click="toggleAudioPlay"
                >
                  <Pause v-if="isAudioPlaying" class="audio-play-icon" />
                  <Play v-else class="audio-play-icon" />
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
  </div>

  <div v-else class="loading">加载课堂中...</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { CheckCircle, ChevronLeft, ChevronRight, Pause, PauseCircle, Play, PlayCircle, Volume2, VolumeX, XCircle } from 'lucide-vue-next'
import { getUserId } from '@/composables/useUserId'
import {
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

const route = useRoute()
const message = useMessage()

const classroom = ref<InteractiveClassroomPayload | null>(null)
const currentIndex = ref(0)
const answersByScene = ref<Record<string, Record<string, string[]>>>({})
const quizResultsByScene = ref<Record<string, QuizSubmitResult | null>>({})
const submitting = ref(false)
const reportLoading = ref(false)
const report = ref<ClassroomReport | null>(null)
const reportAutoShown = ref(false)
const autoPlayEnabled = ref(true)
const isAudioPlaying = ref(false)
const currentAudioTime = ref(0)
const audioDuration = ref(0)
const audioVolume = ref(1)
const audioPlaybackRate = ref(1)
const playbackRateOptions = [0.75, 1, 1.25, 1.5, 2]

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

const sceneSvg = computed(() => {
  const content = currentScene.value?.content || {}
  return (content.svg as string) || ''
})

const sceneMarkdown = computed(() => {
  const content = currentScene.value?.content || {}
  return (content.markdown as string) || ''
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
  return questions.value.every((q) => (currentAnswers.value[q.id] || []).length > 0)
})

const feedbackText = computed(() => currentQuizResult.value?.feedback_action?.text || '')

const reportKnowledgeRows = computed(() => {
  const summary = report.value?.knowledge_summary || {}
  return Object.entries(summary).map(([name, row]) => ({ name, mastery: row.mastery }))
})

const quizSceneIds = computed(() =>
  baseScenes.value.filter((scene) => scene.type === 'quiz').map((scene) => scene.id),
)

const answeredQuizCount = computed(() => {
  const localCount = quizSceneIds.value.filter((sceneId) => Boolean(quizResultsByScene.value[sceneId])).length
  return Math.max(localCount, report.value?.answered_quiz_count || 0)
})

const isClassroomComplete = computed(() => {
  if (quizSceneIds.value.length === 0) return true
  return answeredQuizCount.value === quizSceneIds.value.length
})

const canOpenReportScene = computed(() => {
  if (quizSceneIds.value.length === 0) return true
  return answeredQuizCount.value === quizSceneIds.value.length
})

const lastContentSceneIndex = computed(() => Math.max(0, baseScenes.value.length - 1))

const sceneKindLabel = computed(() => {
  if (currentScene.value?.type === 'quiz') return '课堂互动'
  if (currentScene.value?.type === 'report') return '学习档案'
  return '教师讲解'
})

const playbackStatusText = computed(() => {
  if (!autoPlayEnabled.value) return '手动播放'
  if (currentScene.value?.type === 'quiz') return currentQuizResult.value ? '反馈后自动继续' : '测验暂停'
  if (currentIndex.value >= orderedScenes.value.length - 1) return '最后一页'
  return '自动播放'
})

const currentSpeechText = computed(() => {
  const actions = currentScene.value?.actions || []
  const speech = actions.find((a) => a.type === 'quiz_feedback') || actions.find((a) => a.type === 'speech')
  return speech?.text || ''
})

const currentAudioUrl = computed(() => {
  const actions = currentScene.value?.actions || []
  const speech = actions.find((a) => a.type === 'quiz_feedback') || actions.find((a) => a.type === 'speech')
  const audioUrl = speech?.audio_url || ''
  if (!audioUrl) return ''
  const joiner = audioUrl.includes('?') ? '&' : '?'
  return `${audioUrl}${joiner}user_id=${encodeURIComponent(getUserId())}`
})

function setAnswer(questionId: string, value: string) {
  const sceneId = currentScene.value?.id
  if (!sceneId) return
  const question = questions.value.find((item) => item.id === questionId)
  const prevAnswers = answersByScene.value[sceneId] || {}
  const prevValues = prevAnswers[questionId] || []
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
  if (currentScene.value?.type === 'report') return false

  if (currentScene.value?.type === 'quiz') {
    return Boolean(
      autoPlayEnabled.value
        && currentQuizResult.value
        && currentIndex.value < lastContentSceneIndex.value,
    )
  }

  return Boolean(
    autoPlayEnabled.value
      && currentScene.value?.type !== 'quiz'
      && currentIndex.value < lastContentSceneIndex.value,
  )
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
}

function goPrev() {
  if (currentIndex.value > 0) selectScene(currentIndex.value - 1)
}

function goNext() {
  if (currentIndex.value < orderedScenes.value.length - 1) selectScene(currentIndex.value + 1)
}

function toggleAutoPlay() {
  autoPlayEnabled.value = !autoPlayEnabled.value
  if (!autoPlayEnabled.value) {
    audioRef.value?.pause()
  }
}

function handleAudioEnded() {
  if (currentIndex.value === lastContentSceneIndex.value && isClassroomComplete.value && canOpenReportScene.value) {
    showReportAfterClassroomEnd()
    return
  }
  scheduleAutoAdvance()
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
  const scene = classroom.value.scenes.find((item) => item.id === currentScene.value?.id)
  if (!scene) return
  scene.actions = [
    ...(scene.actions || []).filter((item) => item.type !== 'quiz_feedback'),
    action,
  ]
}

async function submitQuiz() {
  if (!classroom.value || !currentScene.value) return
  submitting.value = true
  try {
    const result = await submitInteractiveClassroomAnswer(
      classroom.value.id,
      currentScene.value.id,
      currentAnswers.value,
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
    if (isClassroomComplete.value) {
      if (currentIndex.value === lastContentSceneIndex.value && !currentAudioUrl.value && canOpenReportScene.value) {
        await showReportAfterClassroomEnd()
      } else {
        scheduleAutoAdvance(1200)
      }
    }
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
  try {
    classroom.value = await getInteractiveClassroom(classroomId)
    await loadReport(true)
    if (route.query.scene === 'report') {
      await showReport()
      const reportIndex = orderedScenes.value.findIndex((scene) => scene.type === 'report')
      if (canOpenReportScene.value && reportIndex >= 0) currentIndex.value = reportIndex
    }
  } catch (err) {
    message.error(err instanceof Error ? err.message : '加载失败')
  }
}

onMounted(() => {
  loadClassroom().catch(() => undefined)
})

onBeforeUnmount(() => {
  clearAdvanceTimer()
})

watch(
  () => [currentScene.value?.id, currentAudioUrl.value, autoPlayEnabled.value, currentQuizResult.value?.score],
  async () => {
    clearAdvanceTimer()
    if (!autoPlayEnabled.value) return
    if (currentScene.value?.type === 'quiz' && !currentQuizResult.value) return

    if (!currentAudioUrl.value) {
      if (currentIndex.value === lastContentSceneIndex.value && isClassroomComplete.value && canOpenReportScene.value) {
        window.setTimeout(() => {
          showReportAfterClassroomEnd().catch(() => undefined)
        }, currentScene.value?.type === 'quiz' ? 1200 : 3500)
        return
      }
      scheduleAutoAdvance(currentScene.value?.type === 'quiz' ? 1800 : 5000)
      return
    }

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
  if (type === 'report') return canOpenReportScene.value ? '报告' : '未解锁'
  return '讲解'
}
</script>

<style scoped>
.player {
  height: 100%;
  display: grid;
  grid-template-columns: 260px 1fr;
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

.scene-title-row {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.scene-kind {
  font-size: 12px;
  color: rgb(var(--ink-3-rgb));
}

.scene-body h2 {
  margin: 0;
  font-size: 20px;
}

.svg-box {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
}

.svg-box :deep(svg) {
  display: block;
  width: auto;
  height: auto;
  max-width: 900px;
  max-height: 56vh;
}

.md-box {
  margin: 0;
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 8px;
  background: rgb(var(--bg-surface-rgb));
  padding: 14px;
  white-space: pre-wrap;
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

.analysis-copy,
.result-tip {
  font-size: 13px;
  line-height: 1.6;
  color: rgb(var(--ink-3-rgb));
}

.quiz-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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
  padding: 12px 18px 16px;
  background: transparent;
}

.narrator-card {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 14px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
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
  color: rgb(var(--ink-2-rgb));
  font-size: 13.5px;
  line-height: 1.7;
  padding-left: 44px;
}

.audio-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: 44px;
  width: calc(100% - 44px);
  padding-top: 10px;
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

@media (max-width: 767px) {
  .player {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
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
  .mastery-row {
    grid-template-columns: 1fr;
  }
}
</style>
