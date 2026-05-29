<template>
  <div class="quiz-player">
    <!-- Top bar -->
    <div class="qp-topbar">
      <div class="qp-progress-wrap">
        <div class="qp-progress-bar">
          <div class="qp-progress-fill" :style="{ width: progressPercent + '%' }" />
        </div>
        <span class="qp-progress-text">{{ answeredCount }}/{{ totalQuestions }}</span>
      </div>
      <button
        v-if="!submitted"
        class="qp-submit-btn"
        :disabled="answeredCount === 0"
        @click="submit"
      >
        提交答卷
      </button>
      <button v-else class="qp-reset-btn" @click="reset">
        重新作答
      </button>
    </div>

    <!-- Module tabs -->
    <div v-if="modules.length > 1" class="qp-tabs">
      <button
        v-for="(mod, idx) in modules"
        :key="idx"
        class="qp-tab"
        :class="{
          'is-active': currentModule === idx,
          'is-done': submitted && moduleScore(idx).total > 0
        }"
        @click="currentModule = idx"
      >
        <span class="qp-tab-label">{{ mod.title }}</span>
        <span v-if="submitted && moduleScore(idx).total > 0" class="qp-tab-score">
          {{ moduleScore(idx).correct }}/{{ moduleScore(idx).total }}
        </span>
      </button>
    </div>

    <!-- Questions -->
    <div class="qp-questions">
      <div
        v-for="q in currentQuestions"
        :key="q.num"
        class="qp-question"
        :class="{ 'is-submitted': submitted }"
      >
        <div class="qp-q-header">
          <span class="qp-q-num">{{ q.num }}</span>
          <span class="qp-q-type" :class="q.type === '多选题' ? 'multi' : 'single'">
            {{ q.type }}
          </span>
          <span class="qp-q-text">{{ q.text }}</span>
        </div>

        <div class="qp-options">
          <button
            v-for="opt in q.options"
            :key="opt"
            class="qp-option"
            :class="optionClass(q, opt)"
            :disabled="submitted"
            @click="selectOption(q, opt)"
          >
            <span class="qp-opt-letter">{{ opt.charAt(0) }}</span>
            <span class="qp-opt-text">{{ opt.length > 2 && opt.charAt(1) === '.' ? opt.substring(2).trim() : opt.substring(1).trim() }}</span>
            <Check v-if="submitted && isCorrectOption(q, opt)" class="qp-opt-icon correct" />
            <XIcon v-if="submitted && isUserWrong(q, opt)" class="qp-opt-icon wrong" />
          </button>
        </div>

        <!-- Answer reveal -->
        <div v-if="submitted" class="qp-answer-reveal">
          <span class="qp-answer-label">答案：</span>
          <span class="qp-answer-value">{{ q.answer }}</span>
        </div>
      </div>
    </div>

    <!-- Score summary -->
    <div v-if="submitted" class="qp-summary">
      <div class="qp-score-ring">
        <svg viewBox="0 0 80 80" class="qp-ring-svg">
          <circle cx="40" cy="40" r="34" class="qp-ring-bg" />
          <circle
            cx="40" cy="40" r="34"
            class="qp-ring-fill"
            :style="{ strokeDashoffset: ringOffset }"
          />
        </svg>
        <div class="qp-score-text">
          <span class="qp-score-num">{{ scorePercent }}</span>
          <span class="qp-score-unit">%</span>
        </div>
      </div>
      <div class="qp-score-detail">
        <div class="qp-score-line">
          <span class="qp-score-label">正确</span>
          <span class="qp-score-val correct">{{ correctCount }}</span>
        </div>
        <div class="qp-score-line">
          <span class="qp-score-label">错误</span>
          <span class="qp-score-val wrong">{{ totalQuestions - correctCount }}</span>
        </div>
        <div class="qp-score-line">
          <span class="qp-score-label">正确率</span>
          <span class="qp-score-val">{{ scorePercent }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Check, X as XIcon } from 'lucide-vue-next'

interface Question {
  num: string
  type: string
  text: string
  options: string[]
  answer: string
}

interface Module {
  title: string
  questions: Question[]
}

interface QuizData {
  title: string
  modules: Module[]
}

const props = defineProps<{ quizData: QuizData }>()

const currentModule = ref(0)
const userAnswers = ref<Record<string, string>>({})
const submitted = ref(false)

const modules = computed(() => props.quizData?.modules || [])
const totalQuestions = computed(() =>
  modules.value.reduce((sum, m) => sum + m.questions.length, 0)
)

const currentQuestions = computed(() => {
  const mod = modules.value[currentModule.value]
  return mod?.questions || []
})

const answeredCount = computed(() => Object.keys(userAnswers.value).length)
const progressPercent = computed(() =>
  totalQuestions.value > 0 ? Math.round((answeredCount.value / totalQuestions.value) * 100) : 0
)

const correctCount = computed(() => {
  let count = 0
  for (const mod of modules.value) {
    for (const q of mod.questions) {
      const ua = userAnswers.value[q.num]
      if (!ua) continue
      const normalized = ua.split('').sort().join('')
      const expected = q.answer.split('').sort().join('')
      if (normalized === expected) count++
    }
  }
  return count
})

const scorePercent = computed(() =>
  totalQuestions.value > 0 ? Math.round((correctCount.value / totalQuestions.value) * 100) : 0
)

const CIRCUMFERENCE = 2 * Math.PI * 34
const ringOffset = computed(() =>
  CIRCUMFERENCE - (scorePercent.value / 100) * CIRCUMFERENCE
)

function moduleScore(modIdx: number) {
  const mod = modules.value[modIdx]
  if (!mod) return { correct: 0, total: 0 }
  let correct = 0
  let total = 0
  for (const q of mod.questions) {
    const ua = userAnswers.value[q.num]
    if (!ua) continue
    total++
    const normalized = ua.split('').sort().join('')
    const expected = q.answer.split('').sort().join('')
    if (normalized === expected) correct++
  }
  return { correct, total }
}

function selectOption(q: Question, opt: string) {
  if (submitted.value) return
  const letter = opt.charAt(0)
  if (q.type === '多选题') {
    const current = userAnswers.value[q.num] || ''
    if (current.includes(letter)) {
      const next = current.replace(letter, '')
      if (next) userAnswers.value[q.num] = next.split('').sort().join('')
      else delete userAnswers.value[q.num]
    } else {
      userAnswers.value[q.num] = (current + letter).split('').sort().join('')
    }
  } else {
    userAnswers.value[q.num] = letter
  }
}

function isCorrectOption(q: Question, opt: string) {
  const letter = opt.charAt(0)
  return q.answer.includes(letter)
}

function isUserWrong(q: Question, opt: string) {
  const letter = opt.charAt(0)
  const ua = userAnswers.value[q.num]
  return ua?.includes(letter) && !q.answer.includes(letter)
}

function optionClass(q: Question, opt: string) {
  const letter = opt.charAt(0)
  const ua = userAnswers.value[q.num]
  const selected = ua?.includes(letter) || false
  const classes: Record<string, boolean> = {}
  if (selected) classes['is-selected'] = true
  if (submitted.value) {
    classes['is-submitted'] = true
    if (q.answer.includes(letter)) classes['is-correct'] = true
    if (ua?.includes(letter) && !q.answer.includes(letter)) classes['is-wrong'] = true
  }
  return classes
}

function submit() {
  submitted.value = true
}

function reset() {
  userAnswers.value = {}
  submitted.value = false
  currentModule.value = 0
}

// Reset module on quiz data change
watch(() => props.quizData, () => {
  currentModule.value = 0
  userAnswers.value = {}
  submitted.value = false
})
</script>

<style scoped>
.quiz-player {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 4px 0;
}

/* ── Top bar ── */
.qp-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.qp-progress-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.qp-progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgb(var(--bg-inset-rgb));
  overflow: hidden;
}

.qp-progress-fill {
  height: 100%;
  border-radius: 3px;
  background: rgb(var(--accent-rgb));
  transition: width 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-progress-text {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-3-rgb));
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.qp-submit-btn,
.qp-reset-btn {
  padding: 8px 20px;
  border-radius: var(--radius-control, 8px);
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-submit-btn {
  background: rgb(var(--accent-rgb));
  color: #fff;
}

.qp-submit-btn:hover:not(:disabled) {
  background: rgb(var(--accent-hover-rgb));
  transform: translateY(-1px);
}

.qp-submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.qp-reset-btn {
  background: rgb(var(--bg-subtle-rgb));
  color: rgb(var(--ink-2-rgb));
  border: 1px solid rgb(var(--line-rgb));
}

.qp-reset-btn:hover {
  background: rgb(var(--bg-inset-rgb));
}

/* ── Module tabs ── */
.qp-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.qp-tabs::-webkit-scrollbar {
  display: none;
}

.qp-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-control, 8px);
  border: 1px solid rgb(var(--line-rgb));
  background: rgb(var(--bg-surface-rgb));
  font-size: 12.5px;
  font-weight: 500;
  color: rgb(var(--ink-3-rgb));
  cursor: pointer;
  white-space: nowrap;
  transition: all 150ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-tab:hover {
  border-color: rgb(var(--accent-rgb) / 0.4);
  color: rgb(var(--ink-1-rgb));
}

.qp-tab.is-active {
  background: rgb(var(--accent-rgb) / 0.08);
  border-color: rgb(var(--accent-rgb) / 0.5);
  color: rgb(var(--accent-rgb));
}

.qp-tab.is-done {
  border-color: rgb(var(--success-rgb) / 0.4);
}

.qp-tab-score {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 9999px;
  background: rgb(var(--success-rgb) / 0.1);
  color: rgb(var(--success-rgb));
}

/* ── Questions ── */
.qp-questions {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.qp-question {
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  border-radius: var(--radius-card, 12px);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: border-color 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-question.is-submitted {
  border-color: rgb(var(--line-strong-rgb));
}

.qp-q-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.qp-q-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgb(var(--accent-rgb) / 0.1);
  color: rgb(var(--accent-rgb));
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.qp-q-type {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.qp-q-type.single {
  background: rgb(var(--accent-rgb) / 0.08);
  color: rgb(var(--accent-rgb));
}

.qp-q-type.multi {
  background: rgb(var(--warning-rgb) / 0.1);
  color: rgb(var(--warning-rgb));
}

.qp-q-text {
  font-size: 14px;
  font-weight: 500;
  color: rgb(var(--ink-1-rgb));
  line-height: 1.5;
}

/* ── Options ── */
.qp-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.qp-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-control, 8px);
  border: 1px solid rgb(var(--line-subtle-rgb));
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: 13.5px;
  color: rgb(var(--ink-2-rgb));
  transition: all 150ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-option:hover:not(:disabled):not(.is-submitted) {
  border-color: rgb(var(--accent-rgb) / 0.5);
  background: rgb(var(--accent-rgb) / 0.04);
}

.qp-option.is-selected:not(.is-submitted) {
  border-color: rgb(var(--accent-rgb));
  background: rgb(var(--accent-rgb) / 0.06);
  color: rgb(var(--ink-1-rgb));
}

.qp-option.is-submitted {
  cursor: default;
}

.qp-option.is-correct {
  border-color: rgb(var(--success-rgb) / 0.6);
  background: rgb(var(--success-rgb) / 0.06);
  color: rgb(var(--ink-1-rgb));
}

.qp-option.is-wrong {
  border-color: rgb(var(--danger-rgb) / 0.6);
  background: rgb(var(--danger-rgb) / 0.06);
  color: rgb(var(--danger-rgb));
}

.qp-opt-letter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1px solid rgb(var(--line-rgb));
  font-size: 11.5px;
  font-weight: 700;
  color: rgb(var(--ink-3-rgb));
  flex-shrink: 0;
  transition: all 150ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-option.is-selected:not(.is-submitted) .qp-opt-letter {
  background: rgb(var(--accent-rgb));
  border-color: rgb(var(--accent-rgb));
  color: #fff;
}

.qp-option.is-correct .qp-opt-letter {
  background: rgb(var(--success-rgb));
  border-color: rgb(var(--success-rgb));
  color: #fff;
}

.qp-option.is-wrong .qp-opt-letter {
  background: rgb(var(--danger-rgb));
  border-color: rgb(var(--danger-rgb));
  color: #fff;
}

.qp-opt-text {
  flex: 1;
  line-height: 1.45;
}

.qp-opt-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.qp-opt-icon.correct {
  color: rgb(var(--success-rgb));
}

.qp-opt-icon.wrong {
  color: rgb(var(--danger-rgb));
}

/* ── Answer reveal ── */
.qp-answer-reveal {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: var(--radius-control, 8px);
  background: rgb(var(--bg-inset-rgb));
  font-size: 12.5px;
  animation: fadeIn 250ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-answer-label {
  color: rgb(var(--ink-4-rgb));
  font-weight: 500;
}

.qp-answer-value {
  color: rgb(var(--ink-1-rgb));
  font-weight: 700;
  letter-spacing: 0.5px;
}

/* ── Score summary ── */
.qp-summary {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 24px;
  border-radius: var(--radius-card, 12px);
  background: rgb(var(--bg-surface-rgb));
  border: 1px solid rgb(var(--line-rgb));
  animation: fadeIn 400ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-score-ring {
  position: relative;
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}

.qp-ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.qp-ring-bg {
  fill: none;
  stroke: rgb(var(--bg-inset-rgb));
  stroke-width: 6;
}

.qp-ring-fill {
  fill: none;
  stroke: rgb(var(--accent-rgb));
  stroke-width: 6;
  stroke-linecap: round;
  stroke-dasharray: 213.628;
  transition: stroke-dashoffset 600ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.qp-score-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.qp-score-num {
  font-size: 22px;
  font-weight: 700;
  color: rgb(var(--ink-1-rgb));
  font-variant-numeric: tabular-nums;
}

.qp-score-unit {
  font-size: 12px;
  font-weight: 500;
  color: rgb(var(--ink-3-rgb));
  margin-top: 2px;
}

.qp-score-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.qp-score-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.qp-score-label {
  color: rgb(var(--ink-4-rgb));
  min-width: 48px;
}

.qp-score-val {
  font-weight: 600;
  color: rgb(var(--ink-1-rgb));
  font-variant-numeric: tabular-nums;
}

.qp-score-val.correct {
  color: rgb(var(--success-rgb));
}

.qp-score-val.wrong {
  color: rgb(var(--danger-rgb));
}

/* ── Animations ── */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
