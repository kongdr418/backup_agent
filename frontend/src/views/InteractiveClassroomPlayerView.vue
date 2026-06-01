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
        :class="{ active: idx === currentIndex }"
        @click="selectScene(idx)"
      >
        <span class="scene-index">{{ idx + 1 }}</span>
        <span class="scene-copy">
          <span class="scene-title">{{ scene.title }}</span>
          <span class="scene-type">{{ scene.type === 'quiz' ? '测验' : '讲解' }}</span>
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
          <span class="scene-kind">{{ currentScene.type === 'quiz' ? '课堂互动' : '教师讲解' }}</span>
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
            <div class="score-ring">{{ currentQuizResult.score }}</div>
            <div>
              <div class="result-summary">
                完成 {{ currentQuizResult.total }} 题，答对 {{ currentQuizResult.correct }} 题
              </div>
              <div class="result-tip">{{ feedbackText || '系统已记录本次答题结果。' }}</div>
            </div>
          </div>
        </div>
      </section>

      <footer class="narrator">
        <div class="teacher-mark">
          <Volume2 class="icon" />
          <span>AI 教师</span>
          <span class="play-status">{{ playbackStatusText }}</span>
        </div>
        <div class="speech-text">{{ currentSpeechText || '当前场景暂无讲解词' }}</div>
        <audio
          v-if="currentAudioUrl"
          ref="audioRef"
          :key="currentAudioUrl"
          :src="currentAudioUrl"
          controls
          :autoplay="autoPlayEnabled && currentScene.type !== 'quiz'"
          @ended="handleAudioEnded"
        />
      </footer>
    </main>
  </div>

  <div v-else class="loading">加载课堂中...</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { CheckCircle, ChevronLeft, ChevronRight, PauseCircle, PlayCircle, Volume2, XCircle } from 'lucide-vue-next'
import { getUserId } from '@/composables/useUserId'
import {
  getInteractiveClassroom,
  submitInteractiveClassroomAnswer,
  type InteractiveClassroomAction,
  type InteractiveClassroomPayload,
  type InteractiveClassroomQuestion,
  type QuizSubmitResult,
} from '@/api/interactiveClassroom'

const route = useRoute()
const message = useMessage()

const classroom = ref<InteractiveClassroomPayload | null>(null)
const currentIndex = ref(0)
const answersByScene = ref<Record<string, Record<string, string[]>>>({})
const quizResultsByScene = ref<Record<string, QuizSubmitResult | null>>({})
const submitting = ref(false)
const autoPlayEnabled = ref(true)
const audioRef = ref<HTMLAudioElement | null>(null)
const advanceTimer = ref<number | null>(null)

const orderedScenes = computed(() =>
  [...(classroom.value?.scenes || [])].sort((a, b) => (a.order || 0) - (b.order || 0)),
)

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

const playbackStatusText = computed(() => {
  if (!autoPlayEnabled.value) return '手动播放'
  if (currentScene.value?.type === 'quiz') return currentQuizResult.value ? '测验已完成，手动继续' : '测验暂停'
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
  answersByScene.value = {
    ...answersByScene.value,
    [sceneId]: {
      ...(answersByScene.value[sceneId] || {}),
      [questionId]: [value],
    },
  }
}

function optionClass(questionId: string, value: string) {
  const result = resultByQuestion.value[questionId]
  const selected = currentAnswers.value[questionId]?.[0] === value
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
  return Boolean(result && currentAnswers.value[questionId]?.[0] === value && !result.correct_answer.includes(value))
}

function clearAdvanceTimer() {
  if (advanceTimer.value !== null) {
    window.clearTimeout(advanceTimer.value)
    advanceTimer.value = null
  }
}

function shouldAutoAdvance() {
  return Boolean(
    autoPlayEnabled.value
      && currentScene.value?.type !== 'quiz'
      && currentIndex.value < orderedScenes.value.length - 1,
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
  clearAdvanceTimer()
  currentIndex.value = idx
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
  scheduleAutoAdvance()
}

function resetQuiz() {
  const sceneId = currentScene.value?.id
  if (!sceneId) return
  const { [sceneId]: _answers, ...restAnswers } = answersByScene.value
  const { [sceneId]: _result, ...restResults } = quizResultsByScene.value
  answersByScene.value = restAnswers
  quizResultsByScene.value = restResults
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
  } catch (err) {
    message.error(err instanceof Error ? err.message : '提交失败')
  } finally {
    submitting.value = false
  }
}

async function loadClassroom() {
  const classroomId = String(route.params.classroomId || '')
  if (!classroomId) return
  try {
    classroom.value = await getInteractiveClassroom(classroomId)
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
  () => [currentScene.value?.id, currentAudioUrl.value, autoPlayEnabled.value],
  async () => {
    clearAdvanceTimer()
    if (!autoPlayEnabled.value || currentScene.value?.type === 'quiz') return

    if (!currentAudioUrl.value) {
      scheduleAutoAdvance(5000)
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
  overflow: auto;
}

.svg-box :deep(svg) {
  width: 100%;
  height: auto;
  max-height: calc(100vh - 250px);
  display: block;
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
  border-top: 1px solid rgb(var(--line-rgb));
  padding: 12px 18px;
  background: rgb(var(--bg-surface-rgb));
  display: grid;
  gap: 8px;
}

.teacher-mark {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgb(var(--ink-2-rgb));
  font-size: 13px;
  font-weight: 600;
}

.play-status {
  border: 1px solid rgb(var(--line-rgb));
  border-radius: 999px;
  padding: 2px 8px;
  color: rgb(var(--ink-3-rgb));
  font-size: 12px;
  font-weight: 500;
}

.speech-text {
  color: rgb(var(--ink-2-rgb));
  font-size: 14px;
  line-height: 1.7;
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
}
</style>
