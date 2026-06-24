import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type CSSProperties } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import { getUserId } from '@/composables/useUserId'
import {
  createClassroomPractice,
  discussInteractiveClassroom,
  discussInteractiveClassroomStream,
  getNextLessonPlan,
  isClassroomTerminalEvent,
  streamInteractiveClassroomGeneration,
  type ClassroomLearningPathStage,
  type ClassroomRecommendedTask,
  type ClassroomDiscussionMessage,
  getInteractiveClassroomGenerationStatus,
  getInteractiveClassroom,
  getInteractiveClassroomReport,
  submitInteractiveClassroomAnswer,
  type ClassroomReport,
  type InteractiveClassroomAction,
  type InteractiveClassroomPayload,
  type InteractiveClassroomQuestion,
  type InteractiveClassroomScene,
  type NextLessonPlan,
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
import { emitSceneReviewed, emitRecommendedTaskOpened, emitRecommendedTaskCompleted, emitClassroomCompleted } from '@/utils/classroomEvents'
import { saveNextLessonDraft } from '@/utils/classroomNextLessonDraft'
import { activeSpeechParagraphIndex, buildSpeechParagraphs } from '@/utils/classroomSpeechHighlight'
import { computeSpeechAutoScrollTop } from '@/utils/classroomSpeechScroll'
import { buildLockedPreviewScenes, mergePreviewScene } from '@/utils/classroomPreviewScenes'
import {
  activeHighlightCue,
  activeHighlightMode,
  fallbackHighlightTargetsFromSvgElement,
  normalizeHighlightCues,
  resolveHighlightTargetsFromSvgElement,
  type HighlightCue,
  type HighlightTarget,
} from '@/utils/classroomHighlight'
import { clearPersistedClassroomGeneration } from '@/utils/classroomGenerationState'
import { buildClassroomCriticPayload } from '@/utils/classroomCriticConfig'
import { useSettingStore } from '@/stores/settingStore'
import type DiscussionSidebar from '@/components/classroom/DiscussionSidebar.vue'

export function useInteractiveClassroomPlayer() {
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
  const previewExpectedSceneTotal = ref(0)
  const previewExpectedSlideTotal = ref(0)
  const previewGenerationStage = ref('')
  const discussionRef = ref<InstanceType<typeof DiscussionSidebar> | null>(null)
  const submitting = ref(false)
  const runningTaskId = ref('')
  const reportLoading = ref(false)
  const report = ref<ClassroomReport | null>(null)
  const nextLessonPlan = ref<NextLessonPlan | null>(null)
  const nextLessonLoading = ref(false)
  const nextLessonDraft = ref({
    topic: '',
    learningGoal: '',
    focusPoints: '',
  })
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
  let previewAbortCtrl: AbortController | null = null

  const isGeneratingPreview = computed(() => route.query.generating === '1' && Boolean(route.query.request_id))
  const canRecordLearningEvents = computed(() =>
    Boolean(classroom.value?.id) && classroom.value?.status !== 'generating' && !isGeneratingPreview.value,
  )

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

  const orderedScenes = computed(() => (isGeneratingPreview.value ? [...baseScenes.value] : [...baseScenes.value, reportScene.value]))

  const lockedPreviewScenes = computed(() => {
    if (!isGeneratingPreview.value) return []
    return buildLockedPreviewScenes(
      baseScenes.value.length,
      previewExpectedSceneTotal.value,
      previewExpectedSlideTotal.value || previewExpectedSceneTotal.value,
    )
  })

  const initialLockedPreviewScenes = computed(() => {
    if (lockedPreviewScenes.value.length) return lockedPreviewScenes.value
    return buildLockedPreviewScenes(0, 5)
  })

  const displaySceneTotal = computed(() => (
    isGeneratingPreview.value
      ? Math.max(orderedScenes.value.length + lockedPreviewScenes.value.length, orderedScenes.value.length)
      : orderedScenes.value.length
  ))

  const previewTailStatus = computed(() => {
    if (!isGeneratingPreview.value) return ''
    if (lockedPreviewScenes.value.length) return ''
    if (previewGenerationStage.value === 'insert_quizzes') return '正在生成随堂测验'
    if (previewGenerationStage.value === 'build_scenes' && baseScenes.value.length > 0) return '正在整理知识结构'
    if (previewGenerationStage.value === 'save') return '正在保存课堂'
    return ''
  })

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

  const ANIMATION_LAB_EMBED_CSS = `
  <style id="ai-creator-animation-lab-embed">
  html,
  body {
    width: 100% !important;
    min-height: 100% !important;
    margin: 0 !important;
    overflow: hidden !important;
    background: #ffffff !important;
  }
  body {
    box-sizing: border-box !important;
    padding: 10px !important;
    color: #0f172a !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
  }
  h1,
  h2 {
    margin: 0 0 8px !important;
    color: #2D5016 !important;
    font-size: clamp(18px, 2.3vw, 24px) !important;
    line-height: 1.25 !important;
    text-align: center !important;
  }
  body > h1:first-child,
  body > h2:first-child {
    display: none !important;
  }
  .container,
  main,
  .app,
  #app {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
    box-sizing: border-box !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    background: transparent !important;
  }
  canvas,
  svg {
    display: block !important;
    width: 100% !important;
    max-width: min(100%, calc(166.67vh - 226px)) !important;
    height: auto !important;
    max-height: calc(100vh - 136px) !important;
    margin: 0 auto !important;
  }
  .controls,
  form {
    margin-top: 8px !important;
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 8px 12px !important;
  }
  label,
  .info,
  p {
    margin-block: 4px !important;
    line-height: 1.38 !important;
  }
  input[type="range"] {
    width: min(520px, 58vw) !important;
  }
  button {
    min-height: 32px !important;
  }
  </style>
  `

  function withAnimationLabEmbedCss(html: string): string {
    if (!html) return ''
    if (html.includes('ai-creator-animation-lab-embed')) return html
    if (/<\/head>/i.test(html)) {
      return html.replace(/<\/head>/i, `${ANIMATION_LAB_EMBED_CSS}</head>`)
    }
    return `${ANIMATION_LAB_EMBED_CSS}${html}`
  }

  const animationLabHtml = computed(() => {
    const content = currentScene.value?.content || {}
    return withAnimationLabEmbedCss((content.html as string) || '')
  })

  const animationLabSummary = computed(() => {
    const content = currentScene.value?.content || {}
    return (content.summary as string) || ''
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

  const reportKnowledgeEvidence = computed(() => report.value?.knowledge_evidence || [])

  const reportRecommendedTasks = computed(() => report.value?.recommended_tasks || [])
  const reportLearningPath = computed(() => report.value?.learning_path || [])
  const reportTaskById = computed(() => {
    const rows = new Map<string, ClassroomRecommendedTask>()
    for (const task of reportRecommendedTasks.value) {
      rows.set(task.id, task)
    }
    return rows
  })

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
    if (isGeneratingPreview.value) return false
    if (quizSceneIds.value.length === 0) return true
    return answeredQuizCount.value === quizSceneIds.value.length
  })

  const canOpenReportScene = computed(() => {
    if (isGeneratingPreview.value) return false
    if (quizSceneIds.value.length === 0) return true
    return answeredQuizCount.value === quizSceneIds.value.length
  })

  const discussionActive = computed(() => discussionSubmitting.value || discussionMessages.value.length > 0)

  const lastContentSceneIndex = computed(() => Math.max(0, baseScenes.value.length - 1))

  const sceneKindLabel = computed(() => {
    if (currentScene.value?.type === 'quiz') return '课堂互动'
    if (currentScene.value?.type === 'report') return '学习档案'
    if (currentScene.value?.type === 'animation_lab') return '动画实验'
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

  /**
   * 生成预览阶段用 requestId 作为 classroom ID，最终课堂用实际 classroomId。
   * localStorage 键包含 classroom ID，因此需要把预览阶段的讨论数据
   * 从旧键迁移到新键，否则刷新后讨论记录会丢失。
   */
  function migrateDiscussionStorage(
    fromClassroomId: string,
    toClassroomId: string,
    finalScenes: InteractiveClassroomScene[],
  ) {
    for (const scene of finalScenes) {
      const persisted = loadPersistedDiscussionMessages(fromClassroomId, scene.id)
      if (persisted && persisted.length > 0) {
        savePersistedDiscussionMessages(toClassroomId, scene.id, persisted)
      }
      clearPersistedDiscussionMessages(fromClassroomId, scene.id)
    }
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
    if (target && target.type === 'slide' && classroom.value && canRecordLearningEvents.value) {
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
          ...buildClassroomCriticPayload(settingStore.settings),
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
      nextLessonPlan.value = null
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
      await loadNextLessonPlan()
    } catch (err) {
      if (!silent) message.error(err instanceof Error ? err.message : '报告生成失败')
    } finally {
      reportLoading.value = false
    }
  }

  async function loadNextLessonPlan(overrides: Partial<Pick<NextLessonPlan, 'topic' | 'learning_goal' | 'focus_points'>> = {}) {
    if (!classroom.value) return
    nextLessonLoading.value = true
    try {
      const plan = await getNextLessonPlan(classroom.value.id, overrides)
      nextLessonPlan.value = plan
      nextLessonDraft.value = {
        topic: plan.topic,
        learningGoal: plan.learning_goal,
        focusPoints: plan.focus_points.join('、'),
      }
    } catch {
      nextLessonPlan.value = null
    } finally {
      nextLessonLoading.value = false
    }
  }

  function splitDraftPoints(value: string) {
    return value
      .split(/[、,，;；\n]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  }

  async function openNextLessonInPptStudio() {
    if (!classroom.value) return
    const focusPoints = splitDraftPoints(nextLessonDraft.value.focusPoints)
    nextLessonLoading.value = true
    try {
      const plan = await getNextLessonPlan(classroom.value.id, {
        topic: nextLessonDraft.value.topic,
        learning_goal: nextLessonDraft.value.learningGoal,
        focus_points: focusPoints,
      })
      nextLessonPlan.value = plan
      saveNextLessonDraft({
        topic: plan.topic,
        course: plan.course,
        weakPoints: plan.weak_points,
        strongPoints: plan.strong_points,
        nextRecommendation: plan.rationale,
        nextLessonNotes: plan.ppt_notes,
        courseRootId: plan.course_root_id,
        parentClassroomId: plan.parent_classroom_id,
        lessonDepth: plan.lesson_depth,
        lessonIndex: plan.lesson_index,
        lessonKind: plan.lesson_kind,
      })
      await router.push({
        name: 'ppt-studio',
        query: {
          from: 'interactive-classroom',
          topic: plan.topic,
          course: plan.course,
          weak_points: plan.weak_points.join('||'),
          strong_points: plan.strong_points.join('||'),
          next_recommendation: plan.rationale,
          next_lesson_notes: plan.ppt_notes,
          course_root_id: plan.course_root_id,
          parent_classroom_id: plan.parent_classroom_id,
          lesson_depth: String(plan.lesson_depth),
          lesson_index: String(plan.lesson_index),
          lesson_kind: plan.lesson_kind,
        },
      })
    } catch (error) {
      message.error(error instanceof Error ? error.message : '下一课生成失败')
    } finally {
      nextLessonLoading.value = false
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
    if (isGeneratingPreview.value) {
      await loadGeneratingClassroom()
      return
    }
    const classroomId = String(route.params.classroomId || '')
    if (!classroomId) return
    if (classroom.value?.id === classroomId && classroom.value.status !== 'generating') {
      stopGeneratingPreview()
      return
    }
    stopGeneratingPreview()
    const loadVersion = ++classroomLoadVersion
    clearAdvanceTimer()
    classroom.value = null
    currentIndex.value = 0
    previewExpectedSceneTotal.value = 0
    previewExpectedSlideTotal.value = 0
    previewGenerationStage.value = ''
    report.value = null
    nextLessonPlan.value = null
    nextLessonDraft.value = { topic: '', learningGoal: '', focusPoints: '' }
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

  function stopGeneratingPreview() {
    if (previewAbortCtrl) {
      try {
        previewAbortCtrl.abort()
      } catch {
        /* ignore */
      }
      previewAbortCtrl = null
    }
  }

  function buildPreviewClassroom(requestId: string, topic: string): InteractiveClassroomPayload {
    return {
      id: requestId,
      title: `${topic || '生成中课堂'}（生成中）`,
      topic: topic || '生成中课堂',
      course: '',
      status: 'generating',
      scenes: [],
      source: { type: 'generation_preview', request_id: requestId },
    }
  }

  function upsertPreviewScene(scene: InteractiveClassroomScene) {
    if (!classroom.value) return
    const wasEmpty = !classroom.value.scenes?.length
    const result = mergePreviewScene(classroom.value.scenes || [], scene, currentIndex.value)
    classroom.value = {
      ...classroom.value,
      scenes: result.scenes,
    }
    currentIndex.value = result.currentIndex
    if (wasEmpty && result.scenes.length === 1) {
      visitedSceneIds.value = new Set([scene.id])
    }
  }

  async function loadGeneratingClassroom() {
    const requestId = String(route.query.request_id || '')
    if (!requestId) return
    const topic = String(route.query.topic || '生成中课堂')
    const loadVersion = ++classroomLoadVersion
    stopGeneratingPreview()
    clearAdvanceTimer()
    currentIndex.value = 0
    previewExpectedSceneTotal.value = 0
    previewExpectedSlideTotal.value = 0
    previewGenerationStage.value = ''
    report.value = null
    nextLessonPlan.value = null
    nextLessonDraft.value = { topic: '', learningGoal: '', focusPoints: '' }
    answersByScene.value = {}
    quizResultsByScene.value = {}
    reportAutoShown.value = false
    classroomCompletedEmitted.value = false
    visitedSceneIds.value = new Set()
    discussionMessages.value = []
    discussionSubmitting.value = false
    classroom.value = buildPreviewClassroom(requestId, topic)
    previewAbortCtrl = new AbortController()

    try {
      for await (const ev of streamInteractiveClassroomGeneration(requestId, previewAbortCtrl.signal)) {
        if (loadVersion !== classroomLoadVersion) return
        if (ev.type === 'classroom_progress') {
          previewGenerationStage.value = ev.stage || previewGenerationStage.value
          if (ev.scene_total && ev.scene_total > previewExpectedSceneTotal.value) {
            previewExpectedSceneTotal.value = ev.scene_total
          }
          if (ev.expected_scene_total && ev.expected_scene_total > previewExpectedSceneTotal.value) {
            previewExpectedSceneTotal.value = ev.expected_scene_total
          }
          if (ev.expected_slide_total && ev.expected_slide_total > previewExpectedSlideTotal.value) {
            previewExpectedSlideTotal.value = ev.expected_slide_total
          }
        }
        if (ev.type === 'classroom_progress' && ev.scene_payload) {
          upsertPreviewScene(ev.scene_payload)
        }
        if (ev.type === 'classroom_done') {
          const activeSceneId = currentScene.value?.id || ''
          const previewClassroomId = classroom.value?.id || ''
          const finalClassroom = await getInteractiveClassroom(ev.classroom_id)
          if (loadVersion !== classroomLoadVersion) return

          // 生成预览阶段的 classroom ID（requestId）与最终课堂 ID 不同，
          // localStorage 键包含 classroom ID，需要把预览阶段的讨论数据迁移过去，
          // 否则刷新后讨论记录会丢失。
          if (previewClassroomId && previewClassroomId !== ev.classroom_id) {
            syncDiscussionPersistence()
            migrateDiscussionStorage(previewClassroomId, ev.classroom_id, finalClassroom.scenes || [])
          }

          classroom.value = finalClassroom
          previewExpectedSceneTotal.value = 0
          previewExpectedSlideTotal.value = 0
          previewGenerationStage.value = ''
          if (activeSceneId) {
            const nextIndex = [...finalClassroom.scenes]
              .sort((a, b) => (a.order || 0) - (b.order || 0))
              .findIndex((scene) => scene.id === activeSceneId)
            if (nextIndex >= 0) currentIndex.value = nextIndex
          }
          stopGeneratingPreview()
          clearPersistedClassroomGeneration()
          await router.replace({
            name: 'interactive-classroom-player',
            params: { classroomId: ev.classroom_id },
          })
          return
        }
        if (ev.type === 'classroom_cancelled') {
          message.info('课堂生成已停止')
          clearPersistedClassroomGeneration()
          await router.replace({ name: 'interactive-classroom-home' })
          return
        }
        if (ev.type === 'classroom_error') {
          message.error(ev.error || '课堂生成失败')
          clearPersistedClassroomGeneration()
          await router.replace({ name: 'interactive-classroom-home' })
          return
        }
        if (isClassroomTerminalEvent(ev)) return
      }
      await settleGeneratingPreview(requestId, loadVersion)
    } catch (err) {
      if (loadVersion !== classroomLoadVersion) return
      const text = err instanceof Error ? err.message : '生成进度连接失败'
      const settled = await settleGeneratingPreview(requestId, loadVersion, text)
      if (!settled) message.error(text)
    }
  }

  async function settleGeneratingPreview(
    requestId: string,
    loadVersion: number,
    streamError = '',
  ) {
    try {
      const job = await getInteractiveClassroomGenerationStatus(requestId)
      if (loadVersion !== classroomLoadVersion) return true
      if (job.status === 'done' && job.classroom_id) {
        clearPersistedClassroomGeneration()
        await router.replace({
          name: 'interactive-classroom-player',
          params: { classroomId: job.classroom_id },
        })
        return true
      }
      if (job.status === 'cancelled') {
        message.info('课堂生成已停止')
        clearPersistedClassroomGeneration()
        await router.replace({ name: 'interactive-classroom-home' })
        return true
      }
      if (job.status === 'error') {
        message.error(job.error || '课堂生成失败')
        clearPersistedClassroomGeneration()
        await router.replace({ name: 'interactive-classroom-home' })
        return true
      }
      return false
    } catch (err) {
      if (loadVersion !== classroomLoadVersion) return true
      const text = err instanceof Error ? err.message : streamError
      if (text.includes('404') || text.includes('生成任务不存在')) {
        clearPersistedClassroomGeneration()
        await router.replace({ name: 'interactive-classroom-home' })
        return true
      }
      return false
    }
  }

  onMounted(() => {
    window.addEventListener('resize', refreshSvgHighlightMetrics)
  })

  onBeforeUnmount(() => {
    classroomLoadVersion += 1
    stopGeneratingPreview()
    clearAdvanceTimer()
    window.removeEventListener('resize', refreshSvgHighlightMetrics)
  })

  watch(
    () => [route.params.classroomId, route.query.request_id, route.query.generating],
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
      if (complete && !classroomCompletedEmitted.value && classroom.value && canRecordLearningEvents.value) {
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
      if (isGeneratingPreview.value) return
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
    const cleanTitleText = (value: string) => value
      .replace(/^\s{0,3}#{1,6}\s*/gm, '')
      .replace(/^\s*[-*+]\s+/gm, '')
      .replace(/\s+/g, ' ')
      .trim()
    const rawTitle = cleanTitleText(scene.title || '')
    // 跳过默认占位标题：page 1、slide 1、第 1 页、1 等
    if (rawTitle && !/^(page|slide|p|s)\s*\d+$/i.test(rawTitle) && !/^第\s*\d+\s*页?$/.test(rawTitle) && !/^\d+$/.test(rawTitle)) {
      return rawTitle
    }
    const speech = cleanTitleText(scene.actions?.find((a) => a.type === 'speech')?.text || '')
    if (speech) {
      const clean = speech.replace(/^这一页的主题是[“\"]/, '').replace(/[”\"]。.*/, '').trim()
      if (clean.length >= 2 && clean.length <= 20) return clean
      const firstSentence = speech.split(/[。.!?！？]/)[0].trim()
      if (firstSentence.length >= 2 && firstSentence.length <= 20) return firstSentence
      if (firstSentence.length > 20) return firstSentence.slice(0, 18) + '...'
    }
    const kp = cleanTitleText(scene.knowledge_points?.[0] || '')
    if (kp && kp.length >= 2 && kp.length <= 20) return kp
    if (kp && kp.length > 20) return kp.slice(0, 18) + '...'
    return rawTitle || '课堂内容'
  }

  function sceneTypeLabel(type: string) {
    if (type === 'quiz') return '测验'
    if (type === 'mindmap') return '知识结构'
    if (type === 'animation_lab') return '动画实验'
    if (type === 'report') return canOpenReportScene.value ? '报告' : '未解锁'
    return '讲解'
  }

  function taskPriorityLabel(priority: string) {
    if (priority === 'high') return '优先'
    if (priority === 'medium') return '建议'
    return '拓展'
  }

  function learningPathStatusLabel(status: string) {
    if (status === 'active') return '进行中'
    if (status === 'pending') return '待执行'
    if (status === 'completed') return '已完成'
    if (status === 'locked') return '待解锁'
    if (status === 'needs_attention') return '需关注'
    return status || '待执行'
  }

  function learningPathActionTask(stage: ClassroomLearningPathStage) {
    if (!stage.task_id) return null
    return reportTaskById.value.get(stage.task_id) || null
  }

  function canRunLearningPathStage(stage: ClassroomLearningPathStage) {
    return Boolean(stage.generated_classroom_id || stage.type === 'next_lesson' || learningPathActionTask(stage))
  }

  function learningPathButtonLabel(stage: ClassroomLearningPathStage) {
    if (stage.type === 'next_lesson') return stage.action_label || '规划下一课'
    if (stage.generated_classroom_id) return stage.action_label || '查看练习'
    const task = learningPathActionTask(stage)
    return task ? taskButtonLabel(task) : stage.action_label || '查看'
  }

  function isLearningPathStageRunning(stage: ClassroomLearningPathStage) {
    if (stage.type === 'next_lesson') return nextLessonLoading.value
    return Boolean(stage.task_id && runningTaskId.value === stage.task_id)
  }

  async function runLearningPathStage(stage: ClassroomLearningPathStage) {
    if (stage.type === 'next_lesson') {
      await openNextLessonInPptStudio()
      return
    }
    if (stage.generated_classroom_id) {
      await router.push({
        name: 'interactive-classroom-player',
        params: { classroomId: stage.generated_classroom_id },
      })
      return
    }
    const task = learningPathActionTask(stage)
    if (task) await runTask(task)
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

    if (task.type === 'next_lesson') {
      await openNextLessonInPptStudio()
      return
    }

    const action = getTaskAction(task)
    if (action.kind === 'scene') {
      const targetIndex = orderedScenes.value.findIndex((scene) => scene.id === action.sceneId)
      if (targetIndex >= 0) {
        selectScene(targetIndex)
        if (task.type === 'review_weak_points' && classroom.value) {
          await emitRecommendedTaskCompleted(
            classroom.value.id,
            task.id,
            task.type,
            task.knowledge_points,
            { status: 'reviewed' },
          )
          await loadReport(true)
        }
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

  return {
    route,
    router,
    dialog,
    message,
    settingStore,
    classroom,
    currentIndex,
    answersByScene,
    quizResultsByScene,
    classroomLoadVersion,
    previewExpectedSceneTotal,
    previewExpectedSlideTotal,
    previewGenerationStage,
    discussionRef,
    submitting,
    runningTaskId,
    reportLoading,
    report,
    nextLessonPlan,
    nextLessonLoading,
    nextLessonDraft,
    reportAutoShown,
    autoPlayEnabled,
    discussionMessages,
    discussionSubmitting,
    multiAgentDiscussionEnabled,
    visitedSceneIds,
    classroomCompletedEmitted,
    isAudioPlaying,
    currentAudioTime,
    audioDuration,
    audioVolume,
    audioPlaybackRate,
    playbackRateOptions,
    speechTextRef,
    svgStageRef,
    svgBoxRef,
    fallbackHighlightTargets,
    measuredHighlightTargets,
    svgMetrics,
    previewAbortCtrl,
    isGeneratingPreview,
    canRecordLearningEvents,
    onAudioLoaded,
    onAudioTimeUpdate,
    onAudioVolumeChange,
    onAudioRateChange,
    syncSpeechParagraphScroll,
    toggleAudioPlay,
    toggleAudioMute,
    onAudioVolumeInput,
    cyclePlaybackRate,
    formatAudioTime,
    audioRef,
    advanceTimer,
    baseScenes,
    reportScene,
    orderedScenes,
    lockedPreviewScenes,
    initialLockedPreviewScenes,
    displaySceneTotal,
    previewTailStatus,
    currentScene,
    playedSceneIds,
    sceneSvg,
    sceneMarkdown,
    sceneMarkmapMd,
    ANIMATION_LAB_EMBED_CSS,
    withAnimationLabEmbedCss,
    animationLabHtml,
    animationLabSummary,
    questions,
    resultByQuestion,
    currentAnswers,
    currentQuizResult,
    allAnswered,
    feedbackText,
    reportKnowledgeRows,
    reportKnowledgeEvidence,
    reportRecommendedTasks,
    reportLearningPath,
    reportTaskById,
    quizSceneIds,
    answeredQuizCount,
    answeredSceneIds,
    isClassroomComplete,
    canOpenReportScene,
    discussionActive,
    lastContentSceneIndex,
    sceneKindLabel,
    playbackStatusText,
    currentSpeechText,
    currentSpeechParagraphs,
    activeSpeechParagraphIdx,
    currentAudioUrl,
    currentSpeechAction,
    rawSceneHighlightTargets,
    sceneHighlightTargets,
    sceneHighlightCues,
    activeHighlight,
    highlightLayerStyle,
    highlightBoxStyle,
    refreshSvgHighlightMetrics,
    setAnswer,
    onShortAnswerInput,
    optionClass,
    isCorrectOption,
    isWrongSelectedOption,
    clearAdvanceTimer,
    shouldAutoAdvance,
    sendQuestionToDiscussion,
    syncDiscussionPersistence,
    migrateDiscussionStorage,
    clearDiscussionHistory,
    confirmClearDiscussionHistory,
    restoreDiscussionForCurrentScene,
    scheduleAutoAdvance,
    selectScene,
    goPrev,
    goNext,
    goBackToList,
    toggleAutoPlay,
    handleAudioEnded,
    requestDiscussion,
    handleDiscussionSubmit,
    handleDiscussionQuickAction,
    resetQuiz,
    applyFeedbackAction,
    submitQuiz,
    loadReport,
    loadNextLessonPlan,
    splitDraftPoints,
    openNextLessonInPptStudio,
    showReport,
    showReportAfterClassroomEnd,
    loadClassroom,
    stopGeneratingPreview,
    buildPreviewClassroom,
    upsertPreviewScene,
    loadGeneratingClassroom,
    settleGeneratingPreview,
    formatSceneTitle,
    sceneTypeLabel,
    taskPriorityLabel,
    learningPathStatusLabel,
    learningPathActionTask,
    canRunLearningPathStage,
    learningPathButtonLabel,
    isLearningPathStageRunning,
    runLearningPathStage,
    getTaskAction,
    canRunTask,
    taskButtonLabel,
    runTask,
  }
}
